"""SQLAlchemy ORM models for the Career Intelligence Knowledge Graph
(CIKG) bounded context.

Every table here is **global reference data**: no `tenant_id`, no RLS —
the same shape as `prompt_versions`/`model_versions`
(app/adapters/db/models/ai_platform.py), not the tenant-owned pattern
career_profile.py uses. Tenant-private extensions (an opt-in enterprise
feature described in cikg-content-governance.md) are explicitly out of
scope for this slice; adding a nullable `tenant_id` + RLS policy later is
additive, not a redesign, per cikg-ddd.md's one-directional dependency
design.

`content_status` is CHECK-constrained to `('approved', 'deprecated')` —
narrowed in Phase 4.5.1 MVP 2B from MVP 1's `('draft', 'approved')`.
Nothing writes to a live node/edge row anymore except an approved
`ContentRevision` being applied (see
app/application/career_intelligence/content_revision_service.py) —
`draft`/`in_review` now live exclusively on `content_revisions.status`
(app/adapters/db/models/governance.py), never on these tables.

The job-role node table is named `cikg_roles`, not `roles` — this
codebase's RBAC `roles` table (app/adapters/db/models/identity.py)
already owns that name for a completely unrelated concept.

Edge tables follow cikg-knowledge-graph-model.md's per-edge-type-table
design: each is its own row with its own id, `source_attribution`, and
`content_status` (edges are governed content too, per
cikg-content-governance.md's Edge Governance section) — never a bare
join table. `prerequisite_of`/`specializes` (directed, DAG-required —
cycle-checked at approval via app/domain/career_intelligence/graph_validation.py)
and `synonym_of` (symmetric, same canonical-ordering/self-loop rule as
`related_to`) were added in MVP 2B, unlocked by the governance workflow
they depend on.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    Computed,
    DateTime,
    Float,
    ForeignKey,
    JSON,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import TSVECTOR
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.adapters.db.base import Base

_CONTENT_STATUS_VALUES = "('approved', 'deprecated')"

#: search_vector on Competency/Skill/CikgRole (Phase 4.5.1 MVP 2A) is a
#: DB-generated STORED column (`GENERATED ALWAYS AS (to_tsvector(...))
#: STORED`, created via raw SQL in that feature's migration — see
#: cikg-semantic-search.md's full-text half of hybrid search). Declared
#: here with `Computed(...)` — matching the migration's actual
#: expression, but its only real job is telling the ORM this column is
#: server-generated so it's excluded from INSERT/UPDATE statements; a
#: real bug caught live in MVP 2B (batch-approving a brand-new
#: Competency raised `psycopg.errors.GeneratedAlways`, since without
#: this marker the ORM tried to INSERT an explicit NULL into it) — MVP
#: 2A's own seed data never hit this path because it was written before
#: this column existed, so no fresh INSERT through the ORM had exercised
#: it until MVP 2B's revision-approval flow did. SkillCategory
#: deliberately has no
#: search_vector: it's a purely structural node (just a name), the same
#: carve-out cikg-semantic-search.md makes for "no free-text worth
#: embedding" nodes, and it's already browsable via GET /categories.


class SkillCategoryModel(Base):
    __tablename__ = "skill_categories"
    __table_args__ = (
        CheckConstraint(f"content_status IN {_CONTENT_STATUS_VALUES}", name="status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    #: Deliberately NOT globally unique: cikg-mvp1-seed-data.md's own
    #: seed content reuses generic category names across unrelated
    #: domains (e.g. "Regulatory" under both Healthcare's Health
    #: Information & Compliance and Finance's Risk & Compliance) —
    #: these are legitimately different nodes that happen to share an
    #: English label. Disambiguation is by hierarchy position
    #: (category_parents), not by name.
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    content_status: Mapped[str] = mapped_column(String(20), nullable=False, default="approved")
    source_attribution: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class CompetencyModel(Base):
    __tablename__ = "competencies"
    __table_args__ = (
        CheckConstraint(f"content_status IN {_CONTENT_STATUS_VALUES}", name="status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    content_status: Mapped[str] = mapped_column(String(20), nullable=False, default="approved")
    source_attribution: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    search_vector: Mapped[str] = mapped_column(
        TSVECTOR,
        Computed("to_tsvector('english', name || ' ' || coalesce(description, ''))", persisted=True),
        nullable=False,
    )


class SkillModel(Base):
    __tablename__ = "skills"
    __table_args__ = (
        CheckConstraint(f"content_status IN {_CONTENT_STATUS_VALUES}", name="status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    ats_keywords: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    proficiency_level_definitions: Mapped[dict[str, str] | None] = mapped_column(
        JSON, nullable=True
    )
    content_status: Mapped[str] = mapped_column(String(20), nullable=False, default="approved")
    source_attribution: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    search_vector: Mapped[str] = mapped_column(
        TSVECTOR,
        Computed("to_tsvector('english', name || ' ' || coalesce(description, ''))", persisted=True),
        nullable=False,
    )


class CikgRoleModel(Base):
    """A job role/title node. Named `cikg_roles` — not `roles`, which is
    already the RBAC roles table (see module docstring).
    """

    __tablename__ = "cikg_roles"
    __table_args__ = (
        CheckConstraint(f"content_status IN {_CONTENT_STATUS_VALUES}", name="status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    experience_level: Mapped[str | None] = mapped_column(String(100), nullable=True)
    content_status: Mapped[str] = mapped_column(String(20), nullable=False, default="approved")
    source_attribution: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    search_vector: Mapped[str] = mapped_column(
        TSVECTOR,
        Computed("to_tsvector('english', title || ' ' || coalesce(description, ''))", persisted=True),
        nullable=False,
    )


# --- Edge tables ---


class CategoryParentModel(Base):
    """Hierarchy edge: child_category -> parent_category. A DAG, not a
    tree — see cikg-skill-ontology.md.
    """

    __tablename__ = "category_parents"
    __table_args__ = (
        CheckConstraint(
            f"content_status IN {_CONTENT_STATUS_VALUES}", name="status"
        ),
        UniqueConstraint(
            "child_category_id", "parent_category_id", name="uq_category_parents_pair"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    child_category_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("skill_categories.id"), nullable=False
    )
    parent_category_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("skill_categories.id"), nullable=False
    )
    content_status: Mapped[str] = mapped_column(String(20), nullable=False, default="approved")
    source_attribution: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class SkillCategoryMembershipModel(Base):
    """A skill belongs to a category — many-to-many (e.g. "SQL" under
    both Programming Languages and Data Analysis)."""

    __tablename__ = "skill_category_memberships"
    __table_args__ = (
        CheckConstraint(
            f"content_status IN {_CONTENT_STATUS_VALUES}",
            name="status",
        ),
        UniqueConstraint("skill_id", "category_id", name="uq_skill_category_memberships_pair"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    skill_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("skills.id"), nullable=False
    )
    category_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("skill_categories.id"), nullable=False
    )
    content_status: Mapped[str] = mapped_column(String(20), nullable=False, default="approved")
    source_attribution: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class SkillCompetencyMembershipModel(Base):
    """The `member_of` edge: Skill -> Competency."""

    __tablename__ = "skill_competency_memberships"
    __table_args__ = (
        CheckConstraint(
            f"content_status IN {_CONTENT_STATUS_VALUES}",
            name="status",
        ),
        UniqueConstraint(
            "skill_id", "competency_id", name="uq_skill_competency_memberships_pair"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    skill_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("skills.id"), nullable=False
    )
    competency_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("competencies.id"), nullable=False
    )
    content_status: Mapped[str] = mapped_column(String(20), nullable=False, default="approved")
    source_attribution: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class RelatedSkillModel(Base):
    """The `related_to` edge: Skill <-> Skill, symmetric, carries
    `strength`. Stored once per unordered pair — the application layer
    canonicalizes ordering (lower id as skill_a_id) and rejects
    self-loops before insert, per cikg-content-governance.md's Edge
    Governance constraint table.
    """

    __tablename__ = "related_skills"
    __table_args__ = (
        CheckConstraint(
            f"content_status IN {_CONTENT_STATUS_VALUES}", name="status"
        ),
        CheckConstraint(
            "strength IN ('weak', 'moderate', 'strong')", name="strength"
        ),
        CheckConstraint("skill_a_id != skill_b_id", name="no_self_loop"),
        UniqueConstraint("skill_a_id", "skill_b_id", name="uq_related_skills_pair"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    skill_a_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("skills.id"), nullable=False
    )
    skill_b_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("skills.id"), nullable=False
    )
    strength: Mapped[str] = mapped_column(String(20), nullable=False)
    content_status: Mapped[str] = mapped_column(String(20), nullable=False, default="approved")
    source_attribution: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class RoleRequiredSkillModel(Base):
    """The `requires` edge: CikgRole -> Skill, carries
    `requirement_level`."""

    __tablename__ = "role_required_skills"
    __table_args__ = (
        CheckConstraint(
            f"content_status IN {_CONTENT_STATUS_VALUES}", name="status"
        ),
        CheckConstraint(
            "requirement_level IN ('required', 'preferred')",
            name="level",
        ),
        UniqueConstraint("role_id", "skill_id", name="uq_role_required_skills_pair"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    role_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("cikg_roles.id"), nullable=False
    )
    skill_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("skills.id"), nullable=False
    )
    requirement_level: Mapped[str] = mapped_column(String(20), nullable=False)
    content_status: Mapped[str] = mapped_column(String(20), nullable=False, default="approved")
    source_attribution: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class SkillAliasModel(Base):
    """Free-text -> canonical Skill resolution (ADR-006 §3). Not
    content_status-governed — see the domain entity's docstring."""

    __tablename__ = "skill_aliases"
    __table_args__ = (
        CheckConstraint(
            "source IN ('curated', 'ai_suggested', 'user_confirmed')",
            name="source",
        ),
        UniqueConstraint("normalized_text", name="uq_skill_aliases_normalized_text"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    skill_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("skills.id"), nullable=False
    )
    alias_text: Mapped[str] = mapped_column(String(255), nullable=False)
    normalized_text: Mapped[str] = mapped_column(String(255), nullable=False)
    source: Mapped[str] = mapped_column(String(20), nullable=False)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PrerequisiteOfEdgeModel(Base):
    """Directed: source_skill_id is reasonable to learn before
    target_skill_id. DAG-required (Phase 4.5.1 MVP 2B) — cycle-checked
    at approval, never at proposal creation."""

    __tablename__ = "prerequisite_of_edges"
    __table_args__ = (
        CheckConstraint(f"content_status IN {_CONTENT_STATUS_VALUES}", name="status"),
        CheckConstraint("source_skill_id != target_skill_id", name="no_self_loop"),
        UniqueConstraint("source_skill_id", "target_skill_id", name="uq_prerequisite_of_edges_pair"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    source_skill_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("skills.id"), nullable=False
    )
    target_skill_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("skills.id"), nullable=False
    )
    content_status: Mapped[str] = mapped_column(String(20), nullable=False, default="approved")
    source_attribution: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class SpecializesEdgeModel(Base):
    """Directed: source_skill_id is a narrower, more specific form of
    target_skill_id. DAG-required, same cycle check as
    PrerequisiteOfEdgeModel."""

    __tablename__ = "specializes_edges"
    __table_args__ = (
        CheckConstraint(f"content_status IN {_CONTENT_STATUS_VALUES}", name="status"),
        CheckConstraint("source_skill_id != target_skill_id", name="no_self_loop"),
        UniqueConstraint("source_skill_id", "target_skill_id", name="uq_specializes_edges_pair"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    source_skill_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("skills.id"), nullable=False
    )
    target_skill_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("skills.id"), nullable=False
    )
    content_status: Mapped[str] = mapped_column(String(20), nullable=False, default="approved")
    source_attribution: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class SynonymOfEdgeModel(Base):
    """Symmetric: two skills that should probably be merged or are
    interchangeable in practice. Same canonical-ordering/self-loop rule
    as RelatedSkillModel, no cycle check (not directed) — elevated
    scrutiny at proposal review is a documented reviewer expectation
    (cikg-content-governance.md), not a schema-level flag."""

    __tablename__ = "synonym_of_edges"
    __table_args__ = (
        CheckConstraint(f"content_status IN {_CONTENT_STATUS_VALUES}", name="status"),
        CheckConstraint("skill_a_id != skill_b_id", name="no_self_loop"),
        UniqueConstraint("skill_a_id", "skill_b_id", name="uq_synonym_of_edges_pair"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    skill_a_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("skills.id"), nullable=False
    )
    skill_b_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("skills.id"), nullable=False
    )
    content_status: Mapped[str] = mapped_column(String(20), nullable=False, default="approved")
    source_attribution: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
