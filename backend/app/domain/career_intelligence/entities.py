"""Career Intelligence Knowledge Graph (CIKG) domain entities.

Plain dataclasses — no SQLAlchemy, no Pydantic, no FastAPI. Mirrors the
pattern established in app/domain/career_profile/entities.py.

Phase 4.5.1 (MVP 1) scope only, per docs/architecture/cikg-mvp-roadmap.md:
Skill, Role, Competency, SkillCategory + the `member_of` (skill-competency),
`requires` (role-skill), and `related_to` (skill-skill) edges, plus the
`skill_alias` soft-linking table. `prerequisite_of`/`specializes`/
`synonym_of` and their DAG-validation rules are deliberately deferred to
MVP 2B, per the explicit roadmap-vs-seed-data scope decision made when
this slice was started — see CLAUDE.md's Phase 4.5.1 status entry.

Every node and edge type here follows cikg-ddd.md's "thin aggregate"
rule: an entity owns only its own scalar attributes; relationships are
separate edge dataclasses referenced by id, never embedded.

`Role` here is a job role/title (e.g. "Software Engineer II") — named
`CikgRole` to avoid any confusion with app.domain.identity.entities.Role
(an RBAC role), which is an entirely unrelated concept that happens to
share the English word "role."
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal
from uuid import UUID

#: Phase 4.5.1 MVP 2B: narrowed from ("draft", "approved") — nothing
#: writes to a live node/edge row anymore except an approved
#: ContentRevision being applied (see content_revision_service.py), so
#: draft/in_review now live exclusively on ContentRevision.status.
#: A live row is only ever "approved" or "deprecated".
ContentStatus = Literal["approved", "deprecated"]
AliasSource = Literal["curated", "ai_suggested", "user_confirmed"]
RelationshipStrength = Literal["weak", "moderate", "strong"]
RevisionStatus = Literal["draft", "in_review", "approved", "rejected"]
RevisionSourceAttribution = Literal["curated", "ai_suggested", "bulk_import"]
RequirementLevel = Literal["required", "preferred"]


@dataclass(slots=True)
class SkillCategory:
    id: UUID
    name: str
    description: str | None
    content_status: ContentStatus
    source_attribution: str | None
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None = None


@dataclass(slots=True)
class Competency:
    id: UUID
    name: str
    description: str | None
    content_status: ContentStatus
    source_attribution: str | None
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None = None


@dataclass(slots=True)
class Skill:
    id: UUID
    name: str
    description: str | None
    content_status: ContentStatus
    source_attribution: str | None
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None = None
    #: Scalar attributes per cikg-skill-ontology.md's "Skill Attributes"
    #: table — genuinely belong to the skill itself, not a relationship.
    ats_keywords: list[str] = field(default_factory=list)
    #: e.g. {"intermediate": "...", "advanced": "..."} — text specific to
    #: this one skill, not a separate graph entity.
    proficiency_level_definitions: dict[str, str] | None = None


@dataclass(slots=True)
class CikgRole:
    """A job role/title node (e.g. "Enterprise Agile Coach"). Distinct
    from app.domain.identity.entities.Role (an RBAC role) — see module
    docstring.
    """

    id: UUID
    title: str
    description: str | None
    experience_level: str | None
    content_status: ContentStatus
    source_attribution: str | None
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None = None


# --- Edge records: each a first-class row with its own id, per
# cikg-ddd.md's "Edge Records Are Their Own First-Class Rows" and
# cikg-knowledge-graph-model.md's per-edge-type-table design. ---


@dataclass(slots=True)
class CategoryParent:
    """Hierarchy edge: `child` belongs under `parent` (a DAG, not a tree
    — a category may have more than one parent). Structural placement,
    not an ontology relationship — see cikg-skill-ontology.md.
    """

    id: UUID
    child_category_id: UUID
    parent_category_id: UUID
    content_status: ContentStatus
    source_attribution: str | None
    created_at: datetime


@dataclass(slots=True)
class SkillCategoryMembership:
    """A skill belongs to a category — many-to-many (e.g. "SQL" belongs
    under both Programming Languages and Data Analysis)."""

    id: UUID
    skill_id: UUID
    category_id: UUID
    content_status: ContentStatus
    source_attribution: str | None
    created_at: datetime


@dataclass(slots=True)
class SkillCompetencyMembership:
    """The `member_of` edge: Skill -> Competency."""

    id: UUID
    skill_id: UUID
    competency_id: UUID
    content_status: ContentStatus
    source_attribution: str | None
    created_at: datetime


@dataclass(slots=True)
class RelatedSkill:
    """The `related_to` edge: Skill <-> Skill, symmetric, carries
    `strength`. Stored once per unordered pair — canonical ordering is
    enforced by the application layer (lower id as skill_a_id), and
    self-loops are rejected there too, per cikg-content-governance.md's
    "Edge Governance" constraint table.
    """

    id: UUID
    skill_a_id: UUID
    skill_b_id: UUID
    strength: RelationshipStrength
    content_status: ContentStatus
    source_attribution: str | None
    created_at: datetime


@dataclass(slots=True)
class RoleRequiredSkill:
    """The `requires` edge: CikgRole -> Skill, carries
    `requirement_level` (required vs. preferred)."""

    id: UUID
    role_id: UUID
    skill_id: UUID
    requirement_level: RequirementLevel
    content_status: ContentStatus
    source_attribution: str | None
    created_at: datetime


@dataclass(slots=True)
class SkillAlias:
    """Free-text -> canonical Skill resolution (ADR-006 §3). Not
    governed by content_status — trust is carried by `source` instead
    (an `ai_suggested` alias is only ever surfaced as a suggestion by
    the resolution service, never silently treated as `curated`).
    """

    id: UUID
    skill_id: UUID
    alias_text: str
    normalized_text: str
    source: AliasSource
    confidence: float | None
    created_at: datetime


# --- Search (Phase 4.5.1 MVP 2A) ---

EmbeddableEntityType = Literal["skill", "cikg_role", "competency"]


@dataclass(slots=True)
class EmbeddingModel:
    """Mirrors app.ai_platform.models.registry.ModelVersion's role for
    chat models — the catalog of embedding models, exactly one of which
    is `is_default`."""

    id: UUID
    provider: str
    model_name: str
    dimensions: int
    is_default: bool
    created_at: datetime


@dataclass(slots=True)
class ContentEmbedding:
    """One embedding vector for one (entity_type, entity_id) pair under
    one embedding_model. `source_text_hash` (sha256 of the exact text
    embedded) lets EmbeddingIndexingService detect staleness cheaply —
    see cikg-semantic-search.md's re-embedding-trigger section.
    """

    id: UUID
    entity_type: EmbeddableEntityType
    entity_id: UUID
    embedding_model_id: UUID
    embedding: list[float]
    source_text_hash: str
    generated_at: datetime


@dataclass(slots=True)
class SearchResult:
    """One ranked hit from SearchService. `matched_via` names which of
    the hybrid signals contributed (e.g. `["graph", "fulltext"]`) —
    surfaced for debugging fusion behavior, not shown to end users as
    raw internals."""

    entity_type: EmbeddableEntityType
    entity_id: UUID
    name: str
    description: str | None
    score: float
    matched_via: list[str]


# --- Governance (Phase 4.5.1 MVP 2B) ---


@dataclass(slots=True)
class ContentRevision:
    """The staging area for every CIKG write — nothing here is live
    until `status` reaches `"approved"` (cikg-versioning-confidence.md).

    `entity_type` is either a bare node type (`"skill"`, `"cikg_role"`,
    `"competency"`, `"skill_category"`) or an edge type prefixed
    `"edge:"` (e.g. `"edge:prerequisite_of"`) — the convention
    cikg-versioning-confidence.md's own schema comment specifies.
    `entity_id` is `None` for a proposal that creates a brand-new
    entity; set to the stable existing id for a proposed edit.
    """

    id: UUID
    entity_type: str
    entity_id: UUID | None
    proposed_data: dict[str, object]
    revision_number: int
    status: RevisionStatus
    confidence: float | None
    source_attribution: RevisionSourceAttribution
    import_batch_id: UUID | None
    reviewed_by: UUID | None
    review_notes: str | None
    created_at: datetime
    reviewed_at: datetime | None = None


@dataclass(slots=True)
class ContentHistoryEntry:
    """Append-only snapshot of an entity's state immediately before an
    approved revision changed it — "supersedes, doesn't delete"
    (cikg-content-governance.md) made concrete. Never written for a
    revision that created a brand-new entity (nothing existed before).
    """

    id: UUID
    entity_type: str
    entity_id: UUID
    version_number: int
    snapshot: dict[str, object]
    change_reason: str | None
    revision_id: UUID
    created_at: datetime


@dataclass(slots=True)
class PrerequisiteOfEdge:
    """Directed: `source_skill_id` is reasonable to learn before
    `target_skill_id`. DAG-required — cycle-checked at approval via
    graph_validation.would_create_cycle."""

    id: UUID
    source_skill_id: UUID
    target_skill_id: UUID
    content_status: ContentStatus
    source_attribution: str | None
    created_at: datetime


@dataclass(slots=True)
class SpecializesEdge:
    """Directed: `source_skill_id` is a narrower, more specific form of
    `target_skill_id` (e.g. "ICU Nursing" specializes "Registered
    Nursing"). DAG-required — same cycle check as PrerequisiteOfEdge."""

    id: UUID
    source_skill_id: UUID
    target_skill_id: UUID
    content_status: ContentStatus
    source_attribution: str | None
    created_at: datetime


@dataclass(slots=True)
class SynonymOfEdge:
    """Symmetric: two skills that should probably be merged or are
    interchangeable in practice — same canonical-ordering/self-loop
    rule as RelatedSkill, no cycle check (it's not directed). Elevated
    scrutiny applies at proposal review (cikg-content-governance.md) —
    a documented reviewer expectation, not a schema-level flag, since
    no review UI exists yet to surface one."""

    id: UUID
    skill_a_id: UUID
    skill_b_id: UUID
    content_status: ContentStatus
    source_attribution: str | None
    created_at: datetime
