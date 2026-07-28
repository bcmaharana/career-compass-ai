"""simplify skill intelligence to free text

Revision ID: 4ea882bbc7ad
Revises: ac9319012a74
Create Date: 2026-07-27 15:24:55.748655

Removes the skill_intelligence catalog/proficiency/category model
(SkillCategory, Skill, RoleTag, SkillRoleTag, UserSkill, TargetRoleSkill)
per ADR-005 — explicit user decision that My Skills and Target Role Skill
Requirements should be plain free-text lists, mirroring
CareerProfile.core_competencies, rather than catalog-linked entities.

`target_roles.required_skills` replaces TargetRoleSkill's catalog-linked
rows. My Skills has no new column at all — it's served directly from the
already-existing `career_profiles.core_competencies`.
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '4ea882bbc7ad'
down_revision: str | None = 'ac9319012a74'
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        'target_roles',
        sa.Column('required_skills', sa.JSON(), nullable=False, server_default='[]'),
    )

    # Drop in FK-safe order: join/link tables before the tables they
    # reference.
    op.execute("DROP POLICY IF EXISTS tenant_isolation_policy ON skill_role_tags")
    op.drop_index("ix_skill_role_tags_role_tag_id", table_name="skill_role_tags")
    op.drop_table('skill_role_tags')

    op.execute("DROP INDEX IF EXISTS ux_role_tags_name_lower")
    op.drop_table('role_tags')

    op.execute("DROP POLICY IF EXISTS tenant_isolation_policy ON target_role_skills")
    op.drop_index("ix_target_role_skills_tenant_id_target_role_id", table_name="target_role_skills")
    op.drop_table('target_role_skills')

    op.execute("DROP POLICY IF EXISTS tenant_isolation_policy ON user_skills")
    op.drop_index("ix_user_skills_tenant_id_user_id", table_name="user_skills")
    op.drop_table('user_skills')

    op.drop_table('skills')
    op.drop_table('skill_categories')


def downgrade() -> None:
    op.create_table(
        'skill_categories',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('display_order', sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_skill_categories')),
        sa.UniqueConstraint('name', name=op.f('uq_skill_categories_name')),
    )

    op.create_table(
        'skills',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('category_id', sa.UUID(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('is_core', sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(
            ['category_id'], ['skill_categories.id'], name=op.f('fk_skills_category_id_skill_categories')
        ),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_skills')),
        sa.UniqueConstraint('name', name=op.f('uq_skills_name')),
    )

    op.create_table(
        'user_skills',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('tenant_id', sa.UUID(), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('skill_id', sa.UUID(), nullable=False),
        sa.Column('proficiency_level', sa.String(length=20), nullable=False),
        sa.Column('display_order', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['skill_id'], ['skills.id'], name=op.f('fk_user_skills_skill_id_skills')),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], name=op.f('fk_user_skills_tenant_id_tenants')),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_user_skills_user_id_users')),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_user_skills')),
    )
    op.create_index("ix_user_skills_tenant_id_user_id", "user_skills", ["tenant_id", "user_id"])
    op.execute("ALTER TABLE user_skills ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE user_skills FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY tenant_isolation_policy ON user_skills
            USING (tenant_id = current_setting('app.tenant_id', true)::uuid)
            WITH CHECK (tenant_id = current_setting('app.tenant_id', true)::uuid)
        """
    )

    op.create_table(
        'target_role_skills',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('tenant_id', sa.UUID(), nullable=False),
        sa.Column('target_role_id', sa.UUID(), nullable=False),
        sa.Column('skill_id', sa.UUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['skill_id'], ['skills.id'], name=op.f('fk_target_role_skills_skill_id_skills')),
        sa.ForeignKeyConstraint(
            ['target_role_id'], ['target_roles.id'], name=op.f('fk_target_role_skills_target_role_id_target_roles')
        ),
        sa.ForeignKeyConstraint(
            ['tenant_id'], ['tenants.id'], name=op.f('fk_target_role_skills_tenant_id_tenants')
        ),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_target_role_skills')),
    )
    op.create_index(
        "ix_target_role_skills_tenant_id_target_role_id", "target_role_skills", ["tenant_id", "target_role_id"]
    )
    op.execute("ALTER TABLE target_role_skills ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE target_role_skills FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY tenant_isolation_policy ON target_role_skills
            USING (tenant_id = current_setting('app.tenant_id', true)::uuid)
            WITH CHECK (tenant_id = current_setting('app.tenant_id', true)::uuid)
        """
    )

    op.create_table(
        'role_tags',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_role_tags')),
    )
    op.execute("CREATE UNIQUE INDEX ux_role_tags_name_lower ON role_tags (lower(name))")

    op.create_table(
        'skill_role_tags',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('skill_id', sa.UUID(), nullable=False),
        sa.Column('role_tag_id', sa.UUID(), nullable=False),
        sa.ForeignKeyConstraint(
            ['role_tag_id'], ['role_tags.id'], name=op.f('fk_skill_role_tags_role_tag_id_role_tags')
        ),
        sa.ForeignKeyConstraint(['skill_id'], ['skills.id'], name=op.f('fk_skill_role_tags_skill_id_skills')),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_skill_role_tags')),
        sa.UniqueConstraint('skill_id', 'role_tag_id', name=op.f('uq_skill_role_tags_skill_id')),
    )
    op.create_index("ix_skill_role_tags_role_tag_id", "skill_role_tags", ["role_tag_id"])

    op.drop_column('target_roles', 'required_skills')
