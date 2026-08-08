"""cikg mvp1 core graph foundation

Revision ID: e8e87feda0bd
Revises: 65b85da50536
Create Date: 2026-07-29 14:32:40.713513

Phase 4.5.1 (MVP 1) per docs/architecture/cikg-mvp-roadmap.md: Skill,
Competency, SkillCategory, CikgRole (a job-role node, not the RBAC
`roles` table) + the `member_of` (skill_competency_memberships),
`requires` (role_required_skills), and `related_to` (related_skills)
edges, the category hierarchy (category_parents,
skill_category_memberships), and the skill_alias soft-linking table.
All reference data — no tenant_id, no RLS, same shape as
prompt_versions/model_versions. `content_status` is CHECK-constrained
to ('draft', 'approved') only; widening to add 'in_review'/'deprecated'
is deliberately left to MVP 2B.

This revision was produced via `alembic revision --autogenerate`; the
autogenerate diff also picked up a number of pre-existing indexes/unique
constraints that were created via raw `op.execute`/hand-written DDL in
earlier migrations without a matching SQLAlchemy-level Index/
UniqueConstraint object on the model — autogenerate proposed dropping
them as drift. Those are unrelated to this change and have been
stripped from this migration; only the new CIKG tables are created here.
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e8e87feda0bd'
down_revision: str | None = '65b85da50536'
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table('cikg_roles',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('title', sa.String(length=255), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('experience_level', sa.String(length=100), nullable=True),
    sa.Column('content_status', sa.String(length=20), nullable=False),
    sa.Column('source_attribution', sa.String(length=255), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
    sa.CheckConstraint("content_status IN ('draft', 'approved')", name=op.f('ck_cikg_roles_status')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_cikg_roles')),
    sa.UniqueConstraint('title', name=op.f('uq_cikg_roles_title'))
    )
    op.create_table('competencies',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('name', sa.String(length=255), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('content_status', sa.String(length=20), nullable=False),
    sa.Column('source_attribution', sa.String(length=255), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
    sa.CheckConstraint("content_status IN ('draft', 'approved')", name=op.f('ck_competencies_status')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_competencies')),
    sa.UniqueConstraint('name', name=op.f('uq_competencies_name'))
    )
    op.create_table('skill_categories',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('name', sa.String(length=255), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('content_status', sa.String(length=20), nullable=False),
    sa.Column('source_attribution', sa.String(length=255), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
    sa.CheckConstraint("content_status IN ('draft', 'approved')", name=op.f('ck_skill_categories_status')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_skill_categories')),
    sa.UniqueConstraint('name', name=op.f('uq_skill_categories_name'))
    )
    op.create_table('skills',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('name', sa.String(length=255), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('ats_keywords', sa.JSON(), nullable=False),
    sa.Column('proficiency_level_definitions', sa.JSON(), nullable=True),
    sa.Column('content_status', sa.String(length=20), nullable=False),
    sa.Column('source_attribution', sa.String(length=255), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
    sa.CheckConstraint("content_status IN ('draft', 'approved')", name=op.f('ck_skills_status')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_skills')),
    sa.UniqueConstraint('name', name=op.f('uq_skills_name'))
    )
    op.create_table('category_parents',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('child_category_id', sa.UUID(), nullable=False),
    sa.Column('parent_category_id', sa.UUID(), nullable=False),
    sa.Column('content_status', sa.String(length=20), nullable=False),
    sa.Column('source_attribution', sa.String(length=255), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("content_status IN ('draft', 'approved')", name=op.f('ck_category_parents_status')),
    sa.ForeignKeyConstraint(['child_category_id'], ['skill_categories.id'], name=op.f('fk_category_parents_child_category_id_skill_categories')),
    sa.ForeignKeyConstraint(['parent_category_id'], ['skill_categories.id'], name=op.f('fk_category_parents_parent_category_id_skill_categories')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_category_parents')),
    sa.UniqueConstraint('child_category_id', 'parent_category_id', name='uq_category_parents_pair')
    )
    op.create_table('related_skills',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('skill_a_id', sa.UUID(), nullable=False),
    sa.Column('skill_b_id', sa.UUID(), nullable=False),
    sa.Column('strength', sa.String(length=20), nullable=False),
    sa.Column('content_status', sa.String(length=20), nullable=False),
    sa.Column('source_attribution', sa.String(length=255), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("content_status IN ('draft', 'approved')", name=op.f('ck_related_skills_status')),
    sa.CheckConstraint("strength IN ('weak', 'moderate', 'strong')", name=op.f('ck_related_skills_strength')),
    sa.CheckConstraint('skill_a_id != skill_b_id', name=op.f('ck_related_skills_no_self_loop')),
    sa.ForeignKeyConstraint(['skill_a_id'], ['skills.id'], name=op.f('fk_related_skills_skill_a_id_skills')),
    sa.ForeignKeyConstraint(['skill_b_id'], ['skills.id'], name=op.f('fk_related_skills_skill_b_id_skills')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_related_skills')),
    sa.UniqueConstraint('skill_a_id', 'skill_b_id', name='uq_related_skills_pair')
    )
    op.create_table('role_required_skills',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('role_id', sa.UUID(), nullable=False),
    sa.Column('skill_id', sa.UUID(), nullable=False),
    sa.Column('requirement_level', sa.String(length=20), nullable=False),
    sa.Column('content_status', sa.String(length=20), nullable=False),
    sa.Column('source_attribution', sa.String(length=255), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("content_status IN ('draft', 'approved')", name=op.f('ck_role_required_skills_status')),
    sa.CheckConstraint("requirement_level IN ('required', 'preferred')", name=op.f('ck_role_required_skills_level')),
    sa.ForeignKeyConstraint(['role_id'], ['cikg_roles.id'], name=op.f('fk_role_required_skills_role_id_cikg_roles')),
    sa.ForeignKeyConstraint(['skill_id'], ['skills.id'], name=op.f('fk_role_required_skills_skill_id_skills')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_role_required_skills')),
    sa.UniqueConstraint('role_id', 'skill_id', name='uq_role_required_skills_pair')
    )
    op.create_table('skill_aliases',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('skill_id', sa.UUID(), nullable=False),
    sa.Column('alias_text', sa.String(length=255), nullable=False),
    sa.Column('normalized_text', sa.String(length=255), nullable=False),
    sa.Column('source', sa.String(length=20), nullable=False),
    sa.Column('confidence', sa.Float(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("source IN ('curated', 'ai_suggested', 'user_confirmed')", name=op.f('ck_skill_aliases_source')),
    sa.ForeignKeyConstraint(['skill_id'], ['skills.id'], name=op.f('fk_skill_aliases_skill_id_skills')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_skill_aliases')),
    sa.UniqueConstraint('normalized_text', name='uq_skill_aliases_normalized_text')
    )
    op.create_table('skill_category_memberships',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('skill_id', sa.UUID(), nullable=False),
    sa.Column('category_id', sa.UUID(), nullable=False),
    sa.Column('content_status', sa.String(length=20), nullable=False),
    sa.Column('source_attribution', sa.String(length=255), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("content_status IN ('draft', 'approved')", name=op.f('ck_skill_category_memberships_status')),
    sa.ForeignKeyConstraint(['category_id'], ['skill_categories.id'], name=op.f('fk_skill_category_memberships_category_id_skill_categories')),
    sa.ForeignKeyConstraint(['skill_id'], ['skills.id'], name=op.f('fk_skill_category_memberships_skill_id_skills')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_skill_category_memberships')),
    sa.UniqueConstraint('skill_id', 'category_id', name='uq_skill_category_memberships_pair')
    )
    op.create_table('skill_competency_memberships',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('skill_id', sa.UUID(), nullable=False),
    sa.Column('competency_id', sa.UUID(), nullable=False),
    sa.Column('content_status', sa.String(length=20), nullable=False),
    sa.Column('source_attribution', sa.String(length=255), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("content_status IN ('draft', 'approved')", name=op.f('ck_skill_competency_memberships_status')),
    sa.ForeignKeyConstraint(['competency_id'], ['competencies.id'], name=op.f('fk_skill_competency_memberships_competency_id_competencies')),
    sa.ForeignKeyConstraint(['skill_id'], ['skills.id'], name=op.f('fk_skill_competency_memberships_skill_id_skills')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_skill_competency_memberships')),
    sa.UniqueConstraint('skill_id', 'competency_id', name='uq_skill_competency_memberships_pair')
    )
    op.create_index("ix_skill_category_memberships_category_id", "skill_category_memberships", ["category_id"])
    op.create_index("ix_skill_competency_memberships_competency_id", "skill_competency_memberships", ["competency_id"])
    op.create_index("ix_category_parents_parent_category_id", "category_parents", ["parent_category_id"])
    op.create_index("ix_related_skills_skill_b_id", "related_skills", ["skill_b_id"])
    op.create_index("ix_role_required_skills_skill_id", "role_required_skills", ["skill_id"])
    op.create_index("ix_skill_aliases_skill_id", "skill_aliases", ["skill_id"])


def downgrade() -> None:
    op.drop_table('skill_competency_memberships')
    op.drop_table('skill_category_memberships')
    op.drop_table('skill_aliases')
    op.drop_table('role_required_skills')
    op.drop_table('related_skills')
    op.drop_table('category_parents')
    op.drop_table('skills')
    op.drop_table('skill_categories')
    op.drop_table('competencies')
    op.drop_table('cikg_roles')
