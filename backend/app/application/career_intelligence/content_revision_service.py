"""ContentRevisionService — the draft→in_review→approved→rejected
workflow (Phase 4.5.1 MVP 2B) that replaces MVP 1's
ContentGovernanceService. One-class-per-verb (per
cikg-api-boundaries.md's suggested shape): propose/submit_for_review/
approve/reject/mark_rejected/list_by_batch/batch_approve.

Nothing writes to a live node/edge row except `approve()` applying a
revision's `proposed_data` — via each entity type's `_apply_*` method,
dispatched by `entity_type` (a bare node type or an `"edge:"`-prefixed
edge type, per cikg-versioning-confidence.md's own schema comment).

**Validation timing follows cikg-content-governance.md's Edge
Governance table exactly**: self-loop/canonical-ordering checks for
symmetric and directed Skill-Skill edges happen at `propose()` (cheap,
no traversal needed); DAG cycle-detection for `edge:category_parent`/
`edge:prerequisite_of`/`edge:specializes` happens at `approve()` only,
against the currently-*approved* edges of that type — a cycle-blocked
approval raises `ValidationError` (code
`EDGE_APPROVAL_WOULD_CREATE_CYCLE`) and leaves the revision at
`in_review`, untouched, so a curator can revise or reject it.

**Known limitation, not solved in this slice**: `batch_approve` catches
failures per-revision so one blocked edge doesn't block the rest of the
batch — true for `ValidationError`-style failures (caught in Python
before any DB write, e.g. the cycle check). A genuine DB-level
constraint violation (a duplicate edge slipping past `propose()`'s
checks) aborts the whole Postgres transaction, which would fail every
subsequent revision in the same batch too, since there's no
per-revision SAVEPOINT here — that would need the service to reach
into the raw session, breaking the repository-Protocol layering this
codebase otherwise holds to. Acceptable for now: the literal MVP 2B
exit criterion (a cycle-blocked proposal) never hits this path at all.

`skill_alias` is explicitly outside this system — unchanged from MVP 1,
never `content_status`-governed to begin with.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.exc import IntegrityError

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.domain.career_intelligence.entities import (
    CategoryParent,
    CikgRole,
    Competency,
    ContentHistoryEntry,
    ContentRevision,
    PrerequisiteOfEdge,
    RelatedSkill,
    RequirementLevel,
    RevisionSourceAttribution,
    RoleRequiredSkill,
    Skill,
    SkillCategory,
    SkillCategoryMembership,
    SkillCompetencyMembership,
    SpecializesEdge,
    SynonymOfEdge,
)
from app.domain.career_intelligence.graph_validation import would_create_cycle
from app.domain.career_intelligence.repositories import (
    CategoryParentRepository,
    CikgRoleRepository,
    CompetencyRepository,
    ContentHistoryRepository,
    ContentRevisionRepository,
    PrerequisiteOfEdgeRepository,
    RelatedSkillRepository,
    RoleRequiredSkillRepository,
    SkillCategoryMembershipRepository,
    SkillCategoryRepository,
    SkillCompetencyMembershipRepository,
    SkillRepository,
    SpecializesEdgeRepository,
    SynonymOfEdgeRepository,
)

_DAG_EDGE_TYPES = {"edge:category_parent", "edge:prerequisite_of", "edge:specializes"}
_SYMMETRIC_EDGE_TYPES = {"edge:related_to", "edge:synonym_of"}
_DIRECTED_SKILL_EDGE_TYPES = {"edge:prerequisite_of", "edge:specializes"}


@dataclass(slots=True)
class BatchApprovalResult:
    approved: list[UUID] = field(default_factory=list)
    failed: list[tuple[UUID, str]] = field(default_factory=list)


def _uuid(data: dict[str, object], key: str) -> UUID:
    value = data.get(key)
    if value is None:
        raise ValidationError(f"'{key}' is required.", code="REVISION_MISSING_FIELDS")
    return UUID(str(value))


class ContentRevisionService:
    def __init__(
        self,
        categories: SkillCategoryRepository,
        competencies: CompetencyRepository,
        skills: SkillRepository,
        roles: CikgRoleRepository,
        category_parents: CategoryParentRepository,
        skill_category_memberships: SkillCategoryMembershipRepository,
        skill_competency_memberships: SkillCompetencyMembershipRepository,
        related_skills: RelatedSkillRepository,
        role_required_skills: RoleRequiredSkillRepository,
        prerequisite_of_edges: PrerequisiteOfEdgeRepository,
        specializes_edges: SpecializesEdgeRepository,
        synonym_of_edges: SynonymOfEdgeRepository,
        revisions: ContentRevisionRepository,
        history: ContentHistoryRepository,
    ) -> None:
        self._categories = categories
        self._competencies = competencies
        self._skills = skills
        self._roles = roles
        self._category_parents = category_parents
        self._skill_category_memberships = skill_category_memberships
        self._skill_competency_memberships = skill_competency_memberships
        self._related_skills = related_skills
        self._role_required_skills = role_required_skills
        self._prerequisite_of_edges = prerequisite_of_edges
        self._specializes_edges = specializes_edges
        self._synonym_of_edges = synonym_of_edges
        self._revisions = revisions
        self._history = history

    # --- Verbs ---

    async def propose(
        self,
        *,
        entity_type: str,
        entity_id: UUID | None,
        proposed_data: dict[str, object],
        source_attribution: RevisionSourceAttribution,
        confidence: float | None = None,
        import_batch_id: UUID | None = None,
    ) -> ContentRevision:
        proposed_data = self._validate_and_normalize(entity_type, proposed_data)
        revision_number = (
            await self._revisions.count_for_entity(entity_type, entity_id) + 1
            if entity_id is not None
            else 1
        )
        return await self._revisions.create(
            ContentRevision(
                id=uuid.uuid4(),
                entity_type=entity_type,
                entity_id=entity_id,
                proposed_data=proposed_data,
                revision_number=revision_number,
                status="draft",
                confidence=confidence,
                source_attribution=source_attribution,
                import_batch_id=import_batch_id,
                reviewed_by=None,
                review_notes=None,
                created_at=datetime.now(UTC),
            )
        )

    async def submit_for_review(self, revision_id: UUID) -> ContentRevision:
        revision = await self._get_or_raise(revision_id)
        if revision.status != "draft":
            raise ValidationError(
                f"Only a draft revision can be submitted for review (current status: "
                f"{revision.status}).",
                code="REVISION_NOT_DRAFT",
            )
        revision.status = "in_review"
        return await self._revisions.update(revision)

    async def approve(self, revision_id: UUID, *, reviewed_by: UUID) -> ContentRevision:
        revision = await self._get_or_raise(revision_id)
        if revision.status != "in_review":
            raise ValidationError(
                f"Only an in_review revision can be approved (current status: "
                f"{revision.status}).",
                code="REVISION_NOT_IN_REVIEW",
            )

        if revision.entity_type in _DAG_EDGE_TYPES:
            await self._check_no_cycle(revision.entity_type, revision.proposed_data)

        try:
            applied_entity_id = await self._apply(revision)
        except IntegrityError as exc:
            raise ConflictError(
                "This content conflicts with something already approved "
                "(likely a duplicate edge).",
                code="REVISION_APPLY_CONFLICT",
            ) from exc

        revision.entity_id = applied_entity_id
        revision.status = "approved"
        revision.reviewed_by = reviewed_by
        revision.reviewed_at = datetime.now(UTC)
        return await self._revisions.update(revision)

    async def reject(self, revision_id: UUID, *, review_notes: str) -> ContentRevision:
        """The routine 'send back for revision' workflow —
        cikg-content-governance.md's literal wording: "Rejected -> back
        to draft with a review comment for revision."""
        revision = await self._get_or_raise(revision_id)
        if revision.status != "in_review":
            raise ValidationError(
                f"Only an in_review revision can be rejected (current status: "
                f"{revision.status}).",
                code="REVISION_NOT_IN_REVIEW",
            )
        revision.status = "draft"
        revision.review_notes = review_notes
        revision.reviewed_at = datetime.now(UTC)
        return await self._revisions.update(revision)

    async def mark_rejected(self, revision_id: UUID, *, review_notes: str) -> ContentRevision:
        """The conflict-resolution 'losing proposal' case
        (cikg-versioning-confidence.md's Conflict Resolution section) —
        terminal, distinct from the routine `reject` above."""
        revision = await self._get_or_raise(revision_id)
        if revision.status not in ("draft", "in_review"):
            raise ValidationError(
                f"Cannot mark a {revision.status} revision as rejected.",
                code="REVISION_CANNOT_MARK_REJECTED",
            )
        revision.status = "rejected"
        revision.review_notes = review_notes
        revision.reviewed_at = datetime.now(UTC)
        return await self._revisions.update(revision)

    async def list_by_batch(self, import_batch_id: UUID) -> list[ContentRevision]:
        return await self._revisions.list_by_batch(import_batch_id)

    async def list_by_status(self, status: str) -> list[ContentRevision]:
        return await self._revisions.list_by_status(status)

    async def batch_approve(
        self, import_batch_id: UUID, *, reviewed_by: UUID
    ) -> BatchApprovalResult:
        result = BatchApprovalResult()
        for revision in await self._revisions.list_by_batch(import_batch_id):
            if revision.status != "in_review":
                continue
            try:
                await self.approve(revision.id, reviewed_by=reviewed_by)
                result.approved.append(revision.id)
            except (ValidationError, ConflictError, NotFoundError) as exc:
                result.failed.append((revision.id, exc.message))
        return result

    async def _get_or_raise(self, revision_id: UUID) -> ContentRevision:
        revision = await self._revisions.get_by_id(revision_id)
        if revision is None:
            raise NotFoundError("Content revision not found.", code="CONTENT_REVISION_NOT_FOUND")
        return revision

    # --- Propose-time validation (self-loop / canonical ordering) ---

    def _validate_and_normalize(
        self, entity_type: str, data: dict[str, object]
    ) -> dict[str, object]:
        if entity_type in _SYMMETRIC_EDGE_TYPES:
            a, b = _uuid(data, "skill_a_id"), _uuid(data, "skill_b_id")
            if a == b:
                raise ValidationError("A skill cannot be related to itself.", code="EDGE_SELF_LOOP")
            lower, higher = sorted((a, b))
            return {**data, "skill_a_id": str(lower), "skill_b_id": str(higher)}

        if entity_type in _DIRECTED_SKILL_EDGE_TYPES:
            source, target = _uuid(data, "source_skill_id"), _uuid(data, "target_skill_id")
            if source == target:
                raise ValidationError(
                    "A skill cannot be its own prerequisite/specialization.",
                    code="EDGE_SELF_LOOP",
                )
            return data

        if entity_type == "edge:category_parent":
            child, parent = _uuid(data, "child_category_id"), _uuid(data, "parent_category_id")
            if child == parent:
                raise ValidationError(
                    "A category cannot be its own parent.", code="EDGE_SELF_LOOP"
                )
            return data

        return data

    # --- Approve-time cycle check (DAG-required edges only) ---

    async def _check_no_cycle(self, entity_type: str, data: dict[str, object]) -> None:
        if entity_type == "edge:category_parent":
            existing = await self._category_parents.list_all_approved()
            edges = [(e.child_category_id, e.parent_category_id) for e in existing]
            new_source, new_target = _uuid(data, "child_category_id"), _uuid(data, "parent_category_id")
        elif entity_type == "edge:prerequisite_of":
            existing_p = await self._prerequisite_of_edges.list_all_approved()
            edges = [(e.source_skill_id, e.target_skill_id) for e in existing_p]
            new_source, new_target = _uuid(data, "source_skill_id"), _uuid(data, "target_skill_id")
        else:  # edge:specializes
            existing_s = await self._specializes_edges.list_all_approved()
            edges = [(e.source_skill_id, e.target_skill_id) for e in existing_s]
            new_source, new_target = _uuid(data, "source_skill_id"), _uuid(data, "target_skill_id")

        if would_create_cycle(edges, new_source, new_target):
            raise ValidationError(
                "Approving this edge would create a cycle in the graph.",
                code="EDGE_APPROVAL_WOULD_CREATE_CYCLE",
            )

    # --- Apply dispatch ---

    async def _apply(self, revision: ContentRevision) -> UUID:
        entity_type, entity_id, data = revision.entity_type, revision.entity_id, revision.proposed_data
        if entity_type == "skill_category":
            return await self._apply_skill_category(revision.id, entity_id, data)
        if entity_type == "competency":
            return await self._apply_competency(revision.id, entity_id, data)
        if entity_type == "skill":
            return await self._apply_skill(revision.id, entity_id, data)
        if entity_type == "cikg_role":
            return await self._apply_cikg_role(revision.id, entity_id, data)
        if entity_type == "edge:category_parent":
            return await self._apply_category_parent(data)
        if entity_type == "edge:skill_category_membership":
            return await self._apply_skill_category_membership(data)
        if entity_type == "edge:skill_competency_membership":
            return await self._apply_skill_competency_membership(data)
        if entity_type == "edge:related_to":
            return await self._apply_related_to(data)
        if entity_type == "edge:role_required_skill":
            return await self._apply_role_required_skill(data)
        if entity_type == "edge:prerequisite_of":
            return await self._apply_prerequisite_of(data)
        if entity_type == "edge:specializes":
            return await self._apply_specializes(data)
        if entity_type == "edge:synonym_of":
            return await self._apply_synonym_of(data)
        raise ValidationError(
            f"Unknown entity_type '{entity_type}'.", code="REVISION_UNKNOWN_ENTITY_TYPE"
        )

    async def _snapshot(
        self, *, entity_type: str, entity_id: UUID, revision_id: UUID, snapshot: dict[str, object]
    ) -> None:
        existing_history = await self._history.list_for_entity(entity_type, entity_id)
        await self._history.create(
            ContentHistoryEntry(
                id=uuid.uuid4(),
                entity_type=entity_type,
                entity_id=entity_id,
                version_number=len(existing_history) + 1,
                snapshot=snapshot,
                change_reason=None,
                revision_id=revision_id,
                created_at=datetime.now(UTC),
            )
        )

    # --- Node appliers (insert if entity_id is None, else edit-with-history) ---

    async def _apply_skill_category(
        self, revision_id: UUID, entity_id: UUID | None, data: dict[str, object]
    ) -> UUID:
        name = str(data["name"])
        description = data.get("description")
        description = str(description) if description is not None else None
        now = datetime.now(UTC)

        if entity_id is None:
            created = await self._categories.create(
                SkillCategory(
                    id=uuid.uuid4(), name=name, description=description,
                    content_status="approved", source_attribution=None,
                    created_at=now, updated_at=now,
                )
            )
            return created.id

        existing = await self._categories.get_by_id(entity_id)
        if existing is None:
            raise NotFoundError("Skill category not found.", code="SKILL_CATEGORY_NOT_FOUND")
        await self._snapshot(
            entity_type="skill_category", entity_id=entity_id, revision_id=revision_id,
            snapshot={"name": existing.name, "description": existing.description},
        )
        existing.name = name
        existing.description = description
        updated = await self._categories.update(existing)
        return updated.id

    async def _apply_competency(
        self, revision_id: UUID, entity_id: UUID | None, data: dict[str, object]
    ) -> UUID:
        name = str(data["name"])
        description = data.get("description")
        description = str(description) if description is not None else None
        now = datetime.now(UTC)

        if entity_id is None:
            created = await self._competencies.create(
                Competency(
                    id=uuid.uuid4(), name=name, description=description,
                    content_status="approved", source_attribution=None,
                    created_at=now, updated_at=now,
                )
            )
            return created.id

        existing = await self._competencies.get_by_id(entity_id)
        if existing is None:
            raise NotFoundError("Competency not found.", code="COMPETENCY_NOT_FOUND")
        await self._snapshot(
            entity_type="competency", entity_id=entity_id, revision_id=revision_id,
            snapshot={"name": existing.name, "description": existing.description},
        )
        existing.name = name
        existing.description = description
        updated = await self._competencies.update(existing)
        return updated.id

    async def _apply_skill(
        self, revision_id: UUID, entity_id: UUID | None, data: dict[str, object]
    ) -> UUID:
        name = str(data["name"])
        description = data.get("description")
        description = str(description) if description is not None else None
        raw_ats_keywords = data.get("ats_keywords")
        ats_keywords = (
            [str(k) for k in raw_ats_keywords] if isinstance(raw_ats_keywords, list) else []
        )
        proficiency = data.get("proficiency_level_definitions")
        proficiency_dict = dict(proficiency) if isinstance(proficiency, dict) else None
        now = datetime.now(UTC)

        if entity_id is None:
            created = await self._skills.create(
                Skill(
                    id=uuid.uuid4(), name=name, description=description,
                    content_status="approved", source_attribution=None,
                    created_at=now, updated_at=now,
                    ats_keywords=ats_keywords, proficiency_level_definitions=proficiency_dict,
                )
            )
            return created.id

        existing = await self._skills.get_by_id(entity_id)
        if existing is None:
            raise NotFoundError("Skill not found.", code="SKILL_NOT_FOUND")
        await self._snapshot(
            entity_type="skill", entity_id=entity_id, revision_id=revision_id,
            snapshot={
                "name": existing.name, "description": existing.description,
                "ats_keywords": existing.ats_keywords,
                "proficiency_level_definitions": existing.proficiency_level_definitions,
            },
        )
        existing.name = name
        existing.description = description
        existing.ats_keywords = ats_keywords
        existing.proficiency_level_definitions = proficiency_dict
        updated = await self._skills.update(existing)
        return updated.id

    async def _apply_cikg_role(
        self, revision_id: UUID, entity_id: UUID | None, data: dict[str, object]
    ) -> UUID:
        title = str(data["title"])
        description = data.get("description")
        description = str(description) if description is not None else None
        experience_level = data.get("experience_level")
        experience_level = str(experience_level) if experience_level is not None else None
        now = datetime.now(UTC)

        if entity_id is None:
            created = await self._roles.create(
                CikgRole(
                    id=uuid.uuid4(), title=title, description=description,
                    experience_level=experience_level, content_status="approved",
                    source_attribution=None, created_at=now, updated_at=now,
                )
            )
            return created.id

        existing = await self._roles.get_by_id(entity_id)
        if existing is None:
            raise NotFoundError("Role not found.", code="CIKG_ROLE_NOT_FOUND")
        await self._snapshot(
            entity_type="cikg_role", entity_id=entity_id, revision_id=revision_id,
            snapshot={
                "title": existing.title, "description": existing.description,
                "experience_level": existing.experience_level,
            },
        )
        existing.title = title
        existing.description = description
        existing.experience_level = experience_level
        updated = await self._roles.update(existing)
        return updated.id

    # --- Edge appliers (create-only — editing an existing edge isn't
    # supported in this slice; a materially different edge is a new
    # proposal, not an edit) ---

    async def _apply_category_parent(self, data: dict[str, object]) -> UUID:
        edge = await self._category_parents.create(
            CategoryParent(
                id=uuid.uuid4(),
                child_category_id=_uuid(data, "child_category_id"),
                parent_category_id=_uuid(data, "parent_category_id"),
                content_status="approved", source_attribution=None,
                created_at=datetime.now(UTC),
            )
        )
        return edge.id

    async def _apply_skill_category_membership(self, data: dict[str, object]) -> UUID:
        edge = await self._skill_category_memberships.create(
            SkillCategoryMembership(
                id=uuid.uuid4(),
                skill_id=_uuid(data, "skill_id"),
                category_id=_uuid(data, "category_id"),
                content_status="approved", source_attribution=None,
                created_at=datetime.now(UTC),
            )
        )
        return edge.id

    async def _apply_skill_competency_membership(self, data: dict[str, object]) -> UUID:
        edge = await self._skill_competency_memberships.create(
            SkillCompetencyMembership(
                id=uuid.uuid4(),
                skill_id=_uuid(data, "skill_id"),
                competency_id=_uuid(data, "competency_id"),
                content_status="approved", source_attribution=None,
                created_at=datetime.now(UTC),
            )
        )
        return edge.id

    async def _apply_related_to(self, data: dict[str, object]) -> UUID:
        strength = data.get("strength", "moderate")
        edge = await self._related_skills.create(
            RelatedSkill(
                id=uuid.uuid4(),
                skill_a_id=_uuid(data, "skill_a_id"),
                skill_b_id=_uuid(data, "skill_b_id"),
                strength=str(strength),  # type: ignore[arg-type]
                content_status="approved", source_attribution=None,
                created_at=datetime.now(UTC),
            )
        )
        return edge.id

    async def _apply_role_required_skill(self, data: dict[str, object]) -> UUID:
        requirement_level: RequirementLevel = data.get("requirement_level", "required")  # type: ignore[assignment]
        edge = await self._role_required_skills.create(
            RoleRequiredSkill(
                id=uuid.uuid4(),
                role_id=_uuid(data, "role_id"),
                skill_id=_uuid(data, "skill_id"),
                requirement_level=requirement_level,
                content_status="approved", source_attribution=None,
                created_at=datetime.now(UTC),
            )
        )
        return edge.id

    async def _apply_prerequisite_of(self, data: dict[str, object]) -> UUID:
        edge = await self._prerequisite_of_edges.create(
            PrerequisiteOfEdge(
                id=uuid.uuid4(),
                source_skill_id=_uuid(data, "source_skill_id"),
                target_skill_id=_uuid(data, "target_skill_id"),
                content_status="approved", source_attribution=None,
                created_at=datetime.now(UTC),
            )
        )
        return edge.id

    async def _apply_specializes(self, data: dict[str, object]) -> UUID:
        edge = await self._specializes_edges.create(
            SpecializesEdge(
                id=uuid.uuid4(),
                source_skill_id=_uuid(data, "source_skill_id"),
                target_skill_id=_uuid(data, "target_skill_id"),
                content_status="approved", source_attribution=None,
                created_at=datetime.now(UTC),
            )
        )
        return edge.id

    async def _apply_synonym_of(self, data: dict[str, object]) -> UUID:
        edge = await self._synonym_of_edges.create(
            SynonymOfEdge(
                id=uuid.uuid4(),
                skill_a_id=_uuid(data, "skill_a_id"),
                skill_b_id=_uuid(data, "skill_b_id"),
                content_status="approved", source_attribution=None,
                created_at=datetime.now(UTC),
            )
        )
        return edge.id
