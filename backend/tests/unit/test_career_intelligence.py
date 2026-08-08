"""Unit tests for the Career Intelligence Knowledge Graph (CIKG) domain
and application layer.

Fakes return copies on fetch, not live object references — the same
discipline test_career_profile_service.py's FakeCareerProfileRepository
docstring documents (two sequential updates otherwise appear to collapse
into one against a fake that hands back the same mutable object).

Phase 4.5.1 MVP 2B: fakes mirror the current repository Protocols —
`create`/`update` (no `approve`, per ContentRevisionService's docstring)
for node repositories; `create` only for edge repositories.
"""

from __future__ import annotations

import uuid
from dataclasses import replace
from datetime import UTC, datetime

import pytest

from app.application.career_intelligence.content_revision_service import ContentRevisionService
from app.application.career_intelligence.skill_alias_admin_service import SkillAliasAdminService
from app.application.career_intelligence.skill_alias_resolution_service import (
    SkillAliasResolutionService,
)
from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.domain.career_intelligence.aliasing import normalize_alias_text
from app.domain.career_intelligence.entities import (
    CategoryParent,
    CikgRole,
    Competency,
    ContentHistoryEntry,
    ContentRevision,
    PrerequisiteOfEdge,
    RelatedSkill,
    RoleRequiredSkill,
    Skill,
    SkillAlias,
    SkillCategory,
    SkillCategoryMembership,
    SkillCompetencyMembership,
    SpecializesEdge,
    SynonymOfEdge,
)


class FakeSkillCategoryRepository:
    def __init__(self) -> None:
        self.rows: dict[uuid.UUID, SkillCategory] = {}

    async def create(self, category: SkillCategory) -> SkillCategory:
        self.rows[category.id] = category
        return replace(category)

    async def update(self, category: SkillCategory) -> SkillCategory:
        if category.id not in self.rows:
            raise NotFoundError("Skill category not found.", code="SKILL_CATEGORY_NOT_FOUND")
        self.rows[category.id] = category
        return replace(category)

    async def get_by_id(self, category_id: uuid.UUID) -> SkillCategory | None:
        row = self.rows.get(category_id)
        return replace(row) if row else None

    async def list_approved(self) -> list[SkillCategory]:
        return [replace(r) for r in self.rows.values() if r.content_status == "approved"]


class FakeCompetencyRepository:
    def __init__(self) -> None:
        self.rows: dict[uuid.UUID, Competency] = {}

    async def create(self, competency: Competency) -> Competency:
        self.rows[competency.id] = competency
        return replace(competency)

    async def update(self, competency: Competency) -> Competency:
        if competency.id not in self.rows:
            raise NotFoundError("Competency not found.", code="COMPETENCY_NOT_FOUND")
        self.rows[competency.id] = competency
        return replace(competency)

    async def get_by_id(self, competency_id: uuid.UUID) -> Competency | None:
        row = self.rows.get(competency_id)
        return replace(row) if row else None

    async def get_by_name(self, name: str) -> Competency | None:
        for row in self.rows.values():
            if row.name == name:
                return replace(row)
        return None

    async def list_approved(self) -> list[Competency]:
        return [replace(r) for r in self.rows.values() if r.content_status == "approved"]


class FakeSkillRepository:
    def __init__(self) -> None:
        self.rows: dict[uuid.UUID, Skill] = {}

    async def create(self, skill: Skill) -> Skill:
        self.rows[skill.id] = skill
        return replace(skill)

    async def update(self, skill: Skill) -> Skill:
        if skill.id not in self.rows:
            raise NotFoundError("Skill not found.", code="SKILL_NOT_FOUND")
        self.rows[skill.id] = skill
        return replace(skill)

    async def get_by_id(self, skill_id: uuid.UUID) -> Skill | None:
        row = self.rows.get(skill_id)
        return replace(row) if row else None

    async def get_by_name(self, name: str) -> Skill | None:
        for row in self.rows.values():
            if row.name == name:
                return replace(row)
        return None

    async def list_approved(self) -> list[Skill]:
        return [replace(r) for r in self.rows.values() if r.content_status == "approved"]


class FakeCikgRoleRepository:
    def __init__(self) -> None:
        self.rows: dict[uuid.UUID, CikgRole] = {}

    async def create(self, role: CikgRole) -> CikgRole:
        self.rows[role.id] = role
        return replace(role)

    async def update(self, role: CikgRole) -> CikgRole:
        if role.id not in self.rows:
            raise NotFoundError("Role not found.", code="CIKG_ROLE_NOT_FOUND")
        self.rows[role.id] = role
        return replace(role)

    async def get_by_id(self, role_id: uuid.UUID) -> CikgRole | None:
        row = self.rows.get(role_id)
        return replace(row) if row else None

    async def get_by_title(self, title: str) -> CikgRole | None:
        for row in self.rows.values():
            if row.title == title:
                return replace(row)
        return None

    async def list_approved(self) -> list[CikgRole]:
        return [replace(r) for r in self.rows.values() if r.content_status == "approved"]


class FakeCategoryParentRepository:
    def __init__(self) -> None:
        self.rows: dict[uuid.UUID, CategoryParent] = {}

    async def create(self, edge: CategoryParent) -> CategoryParent:
        self.rows[edge.id] = edge
        return replace(edge)

    async def list_all_approved(self) -> list[CategoryParent]:
        return [replace(r) for r in self.rows.values() if r.content_status == "approved"]

    async def list_parents(self, child_category_id: uuid.UUID) -> list[CategoryParent]:
        return [replace(r) for r in self.rows.values() if r.child_category_id == child_category_id]

    async def list_children(self, parent_category_id: uuid.UUID) -> list[CategoryParent]:
        return [
            replace(r) for r in self.rows.values() if r.parent_category_id == parent_category_id
        ]


class FakeSkillCategoryMembershipRepository:
    def __init__(self) -> None:
        self.rows: dict[uuid.UUID, SkillCategoryMembership] = {}

    async def create(self, edge: SkillCategoryMembership) -> SkillCategoryMembership:
        self.rows[edge.id] = edge
        return replace(edge)

    async def list_for_skill(self, skill_id: uuid.UUID) -> list[SkillCategoryMembership]:
        return [replace(r) for r in self.rows.values() if r.skill_id == skill_id]

    async def list_for_category(self, category_id: uuid.UUID) -> list[SkillCategoryMembership]:
        return [replace(r) for r in self.rows.values() if r.category_id == category_id]


class FakeSkillCompetencyMembershipRepository:
    def __init__(self) -> None:
        self.rows: dict[uuid.UUID, SkillCompetencyMembership] = {}

    async def create(self, edge: SkillCompetencyMembership) -> SkillCompetencyMembership:
        self.rows[edge.id] = edge
        return replace(edge)

    async def list_for_skill(self, skill_id: uuid.UUID) -> list[SkillCompetencyMembership]:
        return [replace(r) for r in self.rows.values() if r.skill_id == skill_id]

    async def list_for_competency(
        self, competency_id: uuid.UUID
    ) -> list[SkillCompetencyMembership]:
        return [replace(r) for r in self.rows.values() if r.competency_id == competency_id]


class FakeRelatedSkillRepository:
    def __init__(self) -> None:
        self.rows: dict[uuid.UUID, RelatedSkill] = {}

    async def create(self, edge: RelatedSkill) -> RelatedSkill:
        self.rows[edge.id] = edge
        return replace(edge)

    async def get_by_pair(
        self, skill_a_id: uuid.UUID, skill_b_id: uuid.UUID
    ) -> RelatedSkill | None:
        for row in self.rows.values():
            if row.skill_a_id == skill_a_id and row.skill_b_id == skill_b_id:
                return replace(row)
        return None

    async def list_for_skill(self, skill_id: uuid.UUID) -> list[RelatedSkill]:
        return [
            replace(r)
            for r in self.rows.values()
            if r.skill_a_id == skill_id or r.skill_b_id == skill_id
        ]


class FakeRoleRequiredSkillRepository:
    def __init__(self) -> None:
        self.rows: dict[uuid.UUID, RoleRequiredSkill] = {}

    async def create(self, edge: RoleRequiredSkill) -> RoleRequiredSkill:
        self.rows[edge.id] = edge
        return replace(edge)

    async def list_for_role(self, role_id: uuid.UUID) -> list[RoleRequiredSkill]:
        return [replace(r) for r in self.rows.values() if r.role_id == role_id]

    async def list_for_skill(self, skill_id: uuid.UUID) -> list[RoleRequiredSkill]:
        return [replace(r) for r in self.rows.values() if r.skill_id == skill_id]


class FakePrerequisiteOfEdgeRepository:
    def __init__(self) -> None:
        self.rows: dict[uuid.UUID, PrerequisiteOfEdge] = {}

    async def create(self, edge: PrerequisiteOfEdge) -> PrerequisiteOfEdge:
        self.rows[edge.id] = edge
        return replace(edge)

    async def get_by_pair(
        self, source_skill_id: uuid.UUID, target_skill_id: uuid.UUID
    ) -> PrerequisiteOfEdge | None:
        for row in self.rows.values():
            if row.source_skill_id == source_skill_id and row.target_skill_id == target_skill_id:
                return replace(row)
        return None

    async def list_all_approved(self) -> list[PrerequisiteOfEdge]:
        return [replace(r) for r in self.rows.values() if r.content_status == "approved"]

    async def list_for_skill(self, skill_id: uuid.UUID) -> list[PrerequisiteOfEdge]:
        return [
            replace(r)
            for r in self.rows.values()
            if r.source_skill_id == skill_id or r.target_skill_id == skill_id
        ]


class FakeSpecializesEdgeRepository:
    def __init__(self) -> None:
        self.rows: dict[uuid.UUID, SpecializesEdge] = {}

    async def create(self, edge: SpecializesEdge) -> SpecializesEdge:
        self.rows[edge.id] = edge
        return replace(edge)

    async def get_by_pair(
        self, source_skill_id: uuid.UUID, target_skill_id: uuid.UUID
    ) -> SpecializesEdge | None:
        for row in self.rows.values():
            if row.source_skill_id == source_skill_id and row.target_skill_id == target_skill_id:
                return replace(row)
        return None

    async def list_all_approved(self) -> list[SpecializesEdge]:
        return [replace(r) for r in self.rows.values() if r.content_status == "approved"]

    async def list_for_skill(self, skill_id: uuid.UUID) -> list[SpecializesEdge]:
        return [
            replace(r)
            for r in self.rows.values()
            if r.source_skill_id == skill_id or r.target_skill_id == skill_id
        ]


class FakeSynonymOfEdgeRepository:
    def __init__(self) -> None:
        self.rows: dict[uuid.UUID, SynonymOfEdge] = {}

    async def create(self, edge: SynonymOfEdge) -> SynonymOfEdge:
        self.rows[edge.id] = edge
        return replace(edge)

    async def get_by_pair(self, skill_a_id: uuid.UUID, skill_b_id: uuid.UUID) -> SynonymOfEdge | None:
        for row in self.rows.values():
            if row.skill_a_id == skill_a_id and row.skill_b_id == skill_b_id:
                return replace(row)
        return None

    async def list_for_skill(self, skill_id: uuid.UUID) -> list[SynonymOfEdge]:
        return [
            replace(r)
            for r in self.rows.values()
            if r.skill_a_id == skill_id or r.skill_b_id == skill_id
        ]


class FakeSkillAliasRepository:
    def __init__(self) -> None:
        self.rows: dict[uuid.UUID, SkillAlias] = {}

    async def create(self, alias: SkillAlias) -> SkillAlias:
        self.rows[alias.id] = alias
        return replace(alias)

    async def get_by_normalized_text(self, normalized_text: str) -> SkillAlias | None:
        for row in self.rows.values():
            if row.normalized_text == normalized_text:
                return replace(row)
        return None

    async def list_for_skill(self, skill_id: uuid.UUID) -> list[SkillAlias]:
        return [replace(r) for r in self.rows.values() if r.skill_id == skill_id]


class FakeContentRevisionRepository:
    def __init__(self) -> None:
        self.rows: dict[uuid.UUID, ContentRevision] = {}

    async def create(self, revision: ContentRevision) -> ContentRevision:
        self.rows[revision.id] = revision
        return replace(revision)

    async def update(self, revision: ContentRevision) -> ContentRevision:
        if revision.id not in self.rows:
            raise NotFoundError("Content revision not found.", code="CONTENT_REVISION_NOT_FOUND")
        self.rows[revision.id] = revision
        return replace(revision)

    async def get_by_id(self, revision_id: uuid.UUID) -> ContentRevision | None:
        row = self.rows.get(revision_id)
        return replace(row) if row else None

    async def list_by_batch(self, import_batch_id: uuid.UUID) -> list[ContentRevision]:
        return [replace(r) for r in self.rows.values() if r.import_batch_id == import_batch_id]

    async def list_by_status(self, status: str) -> list[ContentRevision]:
        return [replace(r) for r in self.rows.values() if r.status == status]

    async def count_for_entity(self, entity_type: str, entity_id: uuid.UUID) -> int:
        return sum(
            1
            for r in self.rows.values()
            if r.entity_type == entity_type and r.entity_id == entity_id
        )


class FakeContentHistoryRepository:
    def __init__(self) -> None:
        self.rows: dict[uuid.UUID, ContentHistoryEntry] = {}

    async def create(self, entry: ContentHistoryEntry) -> ContentHistoryEntry:
        self.rows[entry.id] = entry
        return replace(entry)

    async def list_for_entity(
        self, entity_type: str, entity_id: uuid.UUID
    ) -> list[ContentHistoryEntry]:
        return [
            replace(r)
            for r in self.rows.values()
            if r.entity_type == entity_type and r.entity_id == entity_id
        ]


def _make_service() -> ContentRevisionService:
    return ContentRevisionService(
        categories=FakeSkillCategoryRepository(),
        competencies=FakeCompetencyRepository(),
        skills=FakeSkillRepository(),
        roles=FakeCikgRoleRepository(),
        category_parents=FakeCategoryParentRepository(),
        skill_category_memberships=FakeSkillCategoryMembershipRepository(),
        skill_competency_memberships=FakeSkillCompetencyMembershipRepository(),
        related_skills=FakeRelatedSkillRepository(),
        role_required_skills=FakeRoleRequiredSkillRepository(),
        prerequisite_of_edges=FakePrerequisiteOfEdgeRepository(),
        specializes_edges=FakeSpecializesEdgeRepository(),
        synonym_of_edges=FakeSynonymOfEdgeRepository(),
        revisions=FakeContentRevisionRepository(),
        history=FakeContentHistoryRepository(),
    )


async def _propose_submit_approve_skill(service: ContentRevisionService, name: str) -> Skill:
    """Convenience: propose a brand-new skill through the full lifecycle
    and return the resulting live Skill."""
    revision = await service.propose(
        entity_type="skill",
        entity_id=None,
        proposed_data={"name": name, "description": None},
        source_attribution="curated",
    )
    await service.submit_for_review(revision.id)
    approved = await service.approve(revision.id, reviewed_by=uuid.uuid4())
    assert approved.entity_id is not None
    skill = await service._skills.get_by_id(approved.entity_id)  # noqa: SLF001 (test-only reach)
    assert skill is not None
    return skill


@pytest.mark.unit
class TestAliasNormalization:
    def test_lowercases_and_collapses_whitespace(self) -> None:
        assert normalize_alias_text("  Product   Management ") == "product management"

    def test_strips_punctuation_but_keeps_hyphens(self) -> None:
        assert normalize_alias_text("co-founder") == "co-founder"

    def test_periods_are_stripped_not_treated_as_word_boundaries(self) -> None:
        # "Node.js" and "Node js" resolve distinctly, per
        # cikg-skill-ontology.md's normalization rule.
        assert normalize_alias_text("Node.js") == "nodejs"
        assert normalize_alias_text("Node js") == "node js"
        assert normalize_alias_text("Node.js") != normalize_alias_text("Node js")


@pytest.mark.unit
class TestProposeSubmitApproveLifecycle:
    async def test_propose_creates_a_draft_revision(self) -> None:
        service = _make_service()

        revision = await service.propose(
            entity_type="skill",
            entity_id=None,
            proposed_data={"name": "Python Programming", "description": None},
            source_attribution="curated",
        )

        assert revision.status == "draft"
        assert revision.entity_id is None
        assert revision.revision_number == 1

    async def test_approve_requires_in_review_status(self) -> None:
        service = _make_service()
        revision = await service.propose(
            entity_type="skill",
            entity_id=None,
            proposed_data={"name": "Python Programming", "description": None},
            source_attribution="curated",
        )

        with pytest.raises(ValidationError) as exc_info:
            await service.approve(revision.id, reviewed_by=uuid.uuid4())

        assert exc_info.value.code == "REVISION_NOT_IN_REVIEW"

    async def test_approving_a_new_entity_creates_it_and_backfills_entity_id(self) -> None:
        service = _make_service()
        revision = await service.propose(
            entity_type="skill",
            entity_id=None,
            proposed_data={"name": "Python Programming", "description": "desc"},
            source_attribution="curated",
        )
        await service.submit_for_review(revision.id)

        approved = await service.approve(revision.id, reviewed_by=uuid.uuid4())

        assert approved.status == "approved"
        assert approved.entity_id is not None
        created = await service._skills.get_by_id(approved.entity_id)  # noqa: SLF001
        assert created is not None
        assert created.name == "Python Programming"
        assert created.content_status == "approved"

    async def test_approving_an_edit_snapshots_prior_state_to_history(self) -> None:
        service = _make_service()
        skill = await _propose_submit_approve_skill(service, "Python Programming")

        edit_revision = await service.propose(
            entity_type="skill",
            entity_id=skill.id,
            proposed_data={"name": "Python Programming", "description": "updated description"},
            source_attribution="curated",
        )
        await service.submit_for_review(edit_revision.id)
        await service.approve(edit_revision.id, reviewed_by=uuid.uuid4())

        updated = await service._skills.get_by_id(skill.id)  # noqa: SLF001
        assert updated is not None
        assert updated.description == "updated description"

        history = await service._history.list_for_entity("skill", skill.id)  # noqa: SLF001
        assert len(history) == 1
        assert history[0].snapshot["description"] is None  # the state *before* the edit

    async def test_reject_sends_an_in_review_revision_back_to_draft(self) -> None:
        service = _make_service()
        revision = await service.propose(
            entity_type="skill",
            entity_id=None,
            proposed_data={"name": "Python Programming", "description": None},
            source_attribution="curated",
        )
        await service.submit_for_review(revision.id)

        rejected = await service.reject(revision.id, review_notes="needs more detail")

        assert rejected.status == "draft"
        assert rejected.review_notes == "needs more detail"

    async def test_mark_rejected_is_terminal(self) -> None:
        service = _make_service()
        revision = await service.propose(
            entity_type="skill",
            entity_id=None,
            proposed_data={"name": "Python Programming", "description": None},
            source_attribution="curated",
        )
        await service.submit_for_review(revision.id)

        rejected = await service.mark_rejected(revision.id, review_notes="superseded by another proposal")

        assert rejected.status == "rejected"


@pytest.mark.unit
class TestRelatedToEdgeValidation:
    async def test_rejects_self_loop_at_propose_time(self) -> None:
        service = _make_service()
        skill = await _propose_submit_approve_skill(service, "Python Programming")

        with pytest.raises(ValidationError) as exc_info:
            await service.propose(
                entity_type="edge:related_to",
                entity_id=None,
                proposed_data={
                    "skill_a_id": str(skill.id), "skill_b_id": str(skill.id), "strength": "moderate"
                },
                source_attribution="curated",
            )

        assert exc_info.value.code == "EDGE_SELF_LOOP"

    async def test_canonicalizes_ordering_regardless_of_argument_order(self) -> None:
        service = _make_service()
        skill_a = await _propose_submit_approve_skill(service, "Python Programming")
        skill_b = await _propose_submit_approve_skill(service, "Data Analysis")
        lower_id, higher_id = sorted((skill_a.id, skill_b.id))

        revision = await service.propose(
            entity_type="edge:related_to",
            entity_id=None,
            proposed_data={
                "skill_a_id": str(higher_id), "skill_b_id": str(lower_id), "strength": "moderate"
            },
            source_attribution="curated",
        )

        assert revision.proposed_data["skill_a_id"] == str(lower_id)
        assert revision.proposed_data["skill_b_id"] == str(higher_id)


@pytest.mark.unit
class TestCycleDetectionAtApproval:
    async def test_prerequisite_of_reverse_edge_is_blocked_at_approval(self) -> None:
        service = _make_service()
        a = await _propose_submit_approve_skill(service, "Data Analysis")
        b = await _propose_submit_approve_skill(service, "Machine Learning")

        forward = await service.propose(
            entity_type="edge:prerequisite_of", entity_id=None,
            proposed_data={"source_skill_id": str(a.id), "target_skill_id": str(b.id)},
            source_attribution="curated",
        )
        await service.submit_for_review(forward.id)
        await service.approve(forward.id, reviewed_by=uuid.uuid4())

        reverse = await service.propose(
            entity_type="edge:prerequisite_of", entity_id=None,
            proposed_data={"source_skill_id": str(b.id), "target_skill_id": str(a.id)},
            source_attribution="ai_suggested", confidence=0.8,
        )
        await service.submit_for_review(reverse.id)

        with pytest.raises(ValidationError) as exc_info:
            await service.approve(reverse.id, reviewed_by=uuid.uuid4())

        assert exc_info.value.code == "EDGE_APPROVAL_WOULD_CREATE_CYCLE"
        # left untouched for a curator to revise or reject — not silently
        # dropped or auto-rejected
        still_in_review = await service._revisions.get_by_id(reverse.id)  # noqa: SLF001
        assert still_in_review is not None
        assert still_in_review.status == "in_review"


@pytest.mark.unit
class TestBatchApprove:
    async def test_batch_approve_processes_each_revision_independently(self) -> None:
        service = _make_service()
        a = await _propose_submit_approve_skill(service, "Data Analysis")
        b = await _propose_submit_approve_skill(service, "Machine Learning")
        c = await _propose_submit_approve_skill(service, "Statistical Modeling")
        batch_id = uuid.uuid4()

        # a -> b already exists (approved above via helper's own path is
        # irrelevant here); create the real forward edge first via a
        # separate, already-approved revision outside the batch.
        forward = await service.propose(
            entity_type="edge:prerequisite_of", entity_id=None,
            proposed_data={"source_skill_id": str(a.id), "target_skill_id": str(b.id)},
            source_attribution="curated",
        )
        await service.submit_for_review(forward.id)
        await service.approve(forward.id, reviewed_by=uuid.uuid4())

        blocked = await service.propose(
            entity_type="edge:prerequisite_of", entity_id=None,
            proposed_data={"source_skill_id": str(b.id), "target_skill_id": str(a.id)},
            source_attribution="ai_suggested", confidence=0.7, import_batch_id=batch_id,
        )
        await service.submit_for_review(blocked.id)
        fine = await service.propose(
            entity_type="edge:prerequisite_of", entity_id=None,
            proposed_data={"source_skill_id": str(b.id), "target_skill_id": str(c.id)},
            source_attribution="ai_suggested", confidence=0.7, import_batch_id=batch_id,
        )
        await service.submit_for_review(fine.id)

        result = await service.batch_approve(batch_id, reviewed_by=uuid.uuid4())

        assert result.approved == [fine.id]
        assert len(result.failed) == 1
        assert result.failed[0][0] == blocked.id


@pytest.mark.unit
class TestSkillAliasAdminService:
    async def test_rejects_alias_text_already_claimed_by_another_skill(self) -> None:
        aliases = FakeSkillAliasRepository()
        service = SkillAliasAdminService(aliases)
        skill_a_id, skill_b_id = uuid.uuid4(), uuid.uuid4()
        await service.create(skill_id=skill_a_id, alias_text="python", source="curated")

        with pytest.raises(ConflictError) as exc_info:
            await service.create(skill_id=skill_b_id, alias_text="Python", source="curated")

        assert exc_info.value.code == "SKILL_ALIAS_DUPLICATE"


@pytest.mark.unit
class TestSkillAliasResolutionService:
    async def test_resolves_a_free_text_entry_to_its_canonical_skill(self) -> None:
        aliases = FakeSkillAliasRepository()
        skills = FakeSkillRepository()
        now = datetime.now(UTC)
        skill = Skill(
            id=uuid.uuid4(), name="Python Programming", description=None,
            content_status="approved", source_attribution="seed_script",
            created_at=now, updated_at=now,
        )
        skills.rows[skill.id] = skill
        aliases.rows[uuid.uuid4()] = SkillAlias(
            id=uuid.uuid4(), skill_id=skill.id, alias_text="python",
            normalized_text="python", source="curated", confidence=None, created_at=now,
        )
        resolver = SkillAliasResolutionService(aliases, skills)

        resolved = await resolver.resolve("Python")

        assert resolved is not None
        assert resolved.name == "Python Programming"

    async def test_returns_none_for_unmatched_free_text(self) -> None:
        resolver = SkillAliasResolutionService(FakeSkillAliasRepository(), FakeSkillRepository())

        resolved = await resolver.resolve("not a real skill")

        assert resolved is None

    async def test_resolves_an_exact_canonical_name_with_no_alias_row(self) -> None:
        # Regression: a query matching a skill's own name (not one of
        # its registered aliases) must still resolve — caught live via
        # CIKG MVP 2A's search endpoint, where "Data Analysis" (a real
        # skill name, never seeded as an alias of itself) silently
        # failed to resolve and skipped the graph-traversal step.
        skills = FakeSkillRepository()
        now = datetime.now(UTC)
        skill = Skill(
            id=uuid.uuid4(), name="Data Analysis", description=None,
            content_status="approved", source_attribution="seed_script",
            created_at=now, updated_at=now,
        )
        skills.rows[skill.id] = skill
        resolver = SkillAliasResolutionService(FakeSkillAliasRepository(), skills)

        resolved = await resolver.resolve("Data Analysis")

        assert resolved is not None
        assert resolved.id == skill.id
