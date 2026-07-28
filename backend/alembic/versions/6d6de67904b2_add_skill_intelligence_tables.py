"""add skill intelligence tables

Revision ID: 6d6de67904b2
Revises: 1007d872b535
Create Date: 2026-07-26 14:47:01.867715

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '6d6de67904b2'
down_revision: str | None = '1007d872b535'
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table('skill_categories',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('name', sa.String(length=100), nullable=False),
    sa.Column('display_order', sa.Integer(), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_skill_categories')),
    sa.UniqueConstraint('name', name=op.f('uq_skill_categories_name'))
    )

    op.create_table('skills',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('category_id', sa.UUID(), nullable=False),
    sa.Column('name', sa.String(length=255), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('is_core', sa.Boolean(), nullable=False),
    sa.ForeignKeyConstraint(['category_id'], ['skill_categories.id'], name=op.f('fk_skills_category_id_skill_categories')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_skills')),
    sa.UniqueConstraint('name', name=op.f('uq_skills_name'))
    )

    op.create_table('user_skills',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('tenant_id', sa.UUID(), nullable=False),
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('skill_id', sa.UUID(), nullable=False),
    sa.Column('proficiency_level', sa.String(length=20), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['skill_id'], ['skills.id'], name=op.f('fk_user_skills_skill_id_skills')),
    sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], name=op.f('fk_user_skills_tenant_id_tenants')),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_user_skills_user_id_users')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_user_skills'))
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

    op.create_table('target_role_skills',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('tenant_id', sa.UUID(), nullable=False),
    sa.Column('target_role_id', sa.UUID(), nullable=False),
    sa.Column('skill_id', sa.UUID(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['skill_id'], ['skills.id'], name=op.f('fk_target_role_skills_skill_id_skills')),
    sa.ForeignKeyConstraint(['target_role_id'], ['target_roles.id'], name=op.f('fk_target_role_skills_target_role_id_target_roles')),
    sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], name=op.f('fk_target_role_skills_tenant_id_tenants')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_target_role_skills'))
    )

    op.create_index("ix_target_role_skills_tenant_id_target_role_id", "target_role_skills", ["tenant_id", "target_role_id"])

    op.execute("ALTER TABLE target_role_skills ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE target_role_skills FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY tenant_isolation_policy ON target_role_skills
            USING (tenant_id = current_setting('app.tenant_id', true)::uuid)
            WITH CHECK (tenant_id = current_setting('app.tenant_id', true)::uuid)
        """
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS tenant_isolation_policy ON target_role_skills")
    op.drop_table('target_role_skills')
    op.execute("DROP POLICY IF EXISTS tenant_isolation_policy ON user_skills")
    op.drop_table('user_skills')
    op.drop_table('skills')
    op.drop_table('skill_categories')
