"""cikg mvp2b governance expansion

Revision ID: e333def9cd81
Revises: 074666e62403
Create Date: 2026-07-29 17:45:20.573851

Phase 4.5.1 MVP 2B per docs/architecture/cikg-mvp-roadmap.md /
cikg-versioning-confidence.md / cikg-content-governance.md: the real
draft->in_review->approved->rejected content_revision workflow, with
content_history as its audit trail, plus the three new Skill<->Skill
ontology edges (prerequisite_of, specializes, synonym_of) that need
this workflow's DAG cycle-detection to exist safely.

**Nothing writes directly to a live node/edge table anymore except an
approved revision being applied** (ContentRevisionService replaces
MVP 1's ContentGovernanceService). Consequence: `content_status` on
every existing MVP 1 table no longer needs `'draft'` as a live value —
`draft`/`in_review` live exclusively on `content_revisions.status` now.
This migration narrows those 9 tables' CHECK constraints from
`('draft', 'approved')` to `('approved', 'deprecated')` accordingly,
guarded by an assertion that zero rows currently sit at
`content_status='draft'` (verified true before this migration was
written — MVP 1's seed script and MVP 2A's embedding script both write
directly at `'approved'`, and every temporary draft row created during
MVP 1/2A live-testing was already cleaned up).

The new edge tables (`prerequisite_of_edges`, `specializes_edges`,
`synonym_of_edges`) start with that same narrowed `('approved',
'deprecated')` constraint from day one, for the same reason — nothing
ever creates a live row for them except an approved revision.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'e333def9cd81'
down_revision: str | None = '074666e62403'
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

_NARROWED_STATUS_VALUES = "('approved', 'deprecated')"

_GOVERNED_TABLES = (
    "skill_categories",
    "competencies",
    "skills",
    "cikg_roles",
    "category_parents",
    "skill_category_memberships",
    "skill_competency_memberships",
    "related_skills",
    "role_required_skills",
)


def upgrade() -> None:
    connection = op.get_bind()
    for table in _GOVERNED_TABLES:
        draft_count = connection.execute(
            sa.text(f"SELECT count(*) FROM {table} WHERE content_status = 'draft'")  # noqa: S608
        ).scalar_one()
        if draft_count:
            raise RuntimeError(
                f"Refusing to narrow {table}.content_status's CHECK constraint: "
                f"{draft_count} row(s) still at 'draft'. This migration assumes "
                "content_revisions now owns the draft/in_review lifecycle — "
                "resolve those rows (approve or delete) before re-running."
            )
        op.execute(f"ALTER TABLE {table} DROP CONSTRAINT ck_{table}_status")
        op.execute(
            f"ALTER TABLE {table} ADD CONSTRAINT ck_{table}_status "
            f"CHECK (content_status IN {_NARROWED_STATUS_VALUES})"
        )

    op.create_table(
        'content_revisions',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('entity_type', sa.String(length=50), nullable=False),
        sa.Column('entity_id', sa.UUID(), nullable=True),
        sa.Column('proposed_data', sa.JSON(), nullable=False),
        sa.Column('revision_number', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='draft'),
        sa.Column('confidence', sa.Numeric(3, 2), nullable=True),
        sa.Column('source_attribution', sa.String(length=20), nullable=False),
        sa.Column('import_batch_id', sa.UUID(), nullable=True),
        sa.Column('reviewed_by', sa.UUID(), nullable=True),
        sa.Column('review_notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('draft', 'in_review', 'approved', 'rejected')",
            name=op.f('ck_content_revisions_status'),
        ),
        sa.CheckConstraint(
            "source_attribution IN ('curated', 'ai_suggested', 'bulk_import')",
            name=op.f('ck_content_revisions_source_attribution'),
        ),
        sa.ForeignKeyConstraint(
            ['reviewed_by'], ['users.id'], name=op.f('fk_content_revisions_reviewed_by_users')
        ),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_content_revisions')),
    )
    op.create_index(
        "ix_content_revisions_entity_type_entity_id",
        "content_revisions",
        ["entity_type", "entity_id"],
    )
    op.create_index("ix_content_revisions_status", "content_revisions", ["status"])
    op.create_index(
        "ix_content_revisions_import_batch_id", "content_revisions", ["import_batch_id"]
    )

    op.create_table(
        'content_history',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('entity_type', sa.String(length=50), nullable=False),
        sa.Column('entity_id', sa.UUID(), nullable=False),
        sa.Column('version_number', sa.Integer(), nullable=False),
        sa.Column('snapshot', sa.JSON(), nullable=False),
        sa.Column('change_reason', sa.Text(), nullable=True),
        sa.Column('revision_id', sa.UUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(
            ['revision_id'], ['content_revisions.id'],
            name=op.f('fk_content_history_revision_id_content_revisions'),
        ),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_content_history')),
    )
    op.create_index(
        "ix_content_history_entity_type_entity_id", "content_history", ["entity_type", "entity_id"]
    )

    op.create_table(
        'prerequisite_of_edges',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('source_skill_id', sa.UUID(), nullable=False),
        sa.Column('target_skill_id', sa.UUID(), nullable=False),
        sa.Column('content_status', sa.String(length=20), nullable=False, server_default='approved'),
        sa.Column('source_attribution', sa.String(length=255), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.CheckConstraint(
            f"content_status IN {_NARROWED_STATUS_VALUES}", name=op.f('ck_prerequisite_of_edges_status')
        ),
        sa.CheckConstraint(
            "source_skill_id != target_skill_id", name=op.f('ck_prerequisite_of_edges_no_self_loop')
        ),
        sa.ForeignKeyConstraint(
            ['source_skill_id'], ['skills.id'],
            name=op.f('fk_prerequisite_of_edges_source_skill_id_skills'),
        ),
        sa.ForeignKeyConstraint(
            ['target_skill_id'], ['skills.id'],
            name=op.f('fk_prerequisite_of_edges_target_skill_id_skills'),
        ),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_prerequisite_of_edges')),
        sa.UniqueConstraint(
            'source_skill_id', 'target_skill_id', name='uq_prerequisite_of_edges_pair'
        ),
    )
    op.create_index(
        "ix_prerequisite_of_edges_target_skill_id", "prerequisite_of_edges", ["target_skill_id"]
    )

    op.create_table(
        'specializes_edges',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('source_skill_id', sa.UUID(), nullable=False),
        sa.Column('target_skill_id', sa.UUID(), nullable=False),
        sa.Column('content_status', sa.String(length=20), nullable=False, server_default='approved'),
        sa.Column('source_attribution', sa.String(length=255), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.CheckConstraint(
            f"content_status IN {_NARROWED_STATUS_VALUES}", name=op.f('ck_specializes_edges_status')
        ),
        sa.CheckConstraint(
            "source_skill_id != target_skill_id", name=op.f('ck_specializes_edges_no_self_loop')
        ),
        sa.ForeignKeyConstraint(
            ['source_skill_id'], ['skills.id'], name=op.f('fk_specializes_edges_source_skill_id_skills')
        ),
        sa.ForeignKeyConstraint(
            ['target_skill_id'], ['skills.id'], name=op.f('fk_specializes_edges_target_skill_id_skills')
        ),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_specializes_edges')),
        sa.UniqueConstraint('source_skill_id', 'target_skill_id', name='uq_specializes_edges_pair'),
    )
    op.create_index(
        "ix_specializes_edges_target_skill_id", "specializes_edges", ["target_skill_id"]
    )

    op.create_table(
        'synonym_of_edges',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('skill_a_id', sa.UUID(), nullable=False),
        sa.Column('skill_b_id', sa.UUID(), nullable=False),
        sa.Column('content_status', sa.String(length=20), nullable=False, server_default='approved'),
        sa.Column('source_attribution', sa.String(length=255), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.CheckConstraint(
            f"content_status IN {_NARROWED_STATUS_VALUES}", name=op.f('ck_synonym_of_edges_status')
        ),
        sa.CheckConstraint("skill_a_id != skill_b_id", name=op.f('ck_synonym_of_edges_no_self_loop')),
        sa.ForeignKeyConstraint(
            ['skill_a_id'], ['skills.id'], name=op.f('fk_synonym_of_edges_skill_a_id_skills')
        ),
        sa.ForeignKeyConstraint(
            ['skill_b_id'], ['skills.id'], name=op.f('fk_synonym_of_edges_skill_b_id_skills')
        ),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_synonym_of_edges')),
        sa.UniqueConstraint('skill_a_id', 'skill_b_id', name='uq_synonym_of_edges_pair'),
    )
    op.create_index("ix_synonym_of_edges_skill_b_id", "synonym_of_edges", ["skill_b_id"])


def downgrade() -> None:
    op.drop_table('synonym_of_edges')
    op.drop_table('specializes_edges')
    op.drop_table('prerequisite_of_edges')
    op.drop_table('content_history')
    op.drop_table('content_revisions')

    for table in _GOVERNED_TABLES:
        op.execute(f"ALTER TABLE {table} DROP CONSTRAINT ck_{table}_status")
        op.execute(
            f"ALTER TABLE {table} ADD CONSTRAINT ck_{table}_status "
            "CHECK (content_status IN ('draft', 'approved'))"
        )
