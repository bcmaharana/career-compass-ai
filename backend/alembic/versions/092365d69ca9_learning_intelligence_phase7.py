"""learning intelligence phase7

Revision ID: 092365d69ca9
Revises: 9c9f583ee903
Create Date: 2026-08-15 00:20:00.000000

Phase 7 per CLAUDE.md's roadmap: `learning_items` (a self-managed
learning log, scoped directly by user_id — same shape as
career_goals) and `learning_recommendation_sets` (one row per
(tenant_id, user_id, target_role_id), AI-generated and cached). Both
tenant-owned like every other domain table (RLS enabled+forced,
exact-match policy).
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '092365d69ca9'
down_revision: str | None = '9c9f583ee903'
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table('learning_items',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('tenant_id', sa.UUID(), nullable=False),
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('title', sa.String(length=255), nullable=False),
    sa.Column('provider', sa.String(length=255), nullable=True),
    sa.Column('url', sa.String(length=1000), nullable=True),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('target_role_id', sa.UUID(), nullable=True),
    sa.Column('notes', sa.Text(), nullable=True),
    sa.Column('started_at', sa.Date(), nullable=True),
    sa.Column('completed_at', sa.Date(), nullable=True),
    sa.Column('display_order', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
    sa.CheckConstraint("status IN ('planned', 'in_progress', 'completed')", name=op.f('ck_learning_items_status')),
    sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], name=op.f('fk_learning_items_tenant_id_tenants')),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_learning_items_user_id_users')),
    sa.ForeignKeyConstraint(['target_role_id'], ['target_roles.id'], name=op.f('fk_learning_items_target_role_id_target_roles'), ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_learning_items'))
    )
    op.create_index(
        "ix_learning_items_tenant_id_user_id",
        "learning_items",
        ["tenant_id", "user_id"],
    )
    op.execute("ALTER TABLE learning_items ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE learning_items FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY tenant_isolation_policy ON learning_items
            USING (tenant_id = current_setting('app.tenant_id', true)::uuid)
            WITH CHECK (tenant_id = current_setting('app.tenant_id', true)::uuid)
        """
    )

    op.create_table('learning_recommendation_sets',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('tenant_id', sa.UUID(), nullable=False),
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('target_role_id', sa.UUID(), nullable=False),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('missing_skills_hash', sa.String(length=64), nullable=False),
    sa.Column('recommendations', sa.JSON(), nullable=True),
    sa.Column('error_message', sa.Text(), nullable=True),
    sa.Column('generated_at', sa.DateTime(timezone=True), nullable=False),
    sa.CheckConstraint("status IN ('generated', 'failed')", name=op.f('ck_learning_recommendation_sets_status')),
    sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], name=op.f('fk_learning_recommendation_sets_tenant_id_tenants')),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_learning_recommendation_sets_user_id_users')),
    sa.ForeignKeyConstraint(['target_role_id'], ['target_roles.id'], name=op.f('fk_learning_recommendation_sets_target_role_id_target_roles')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_learning_recommendation_sets')),
    sa.UniqueConstraint('tenant_id', 'user_id', 'target_role_id', name='uq_learning_recommendation_sets_scope')
    )
    op.execute("ALTER TABLE learning_recommendation_sets ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE learning_recommendation_sets FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY tenant_isolation_policy ON learning_recommendation_sets
            USING (tenant_id = current_setting('app.tenant_id', true)::uuid)
            WITH CHECK (tenant_id = current_setting('app.tenant_id', true)::uuid)
        """
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS tenant_isolation_policy ON learning_recommendation_sets")
    op.drop_table('learning_recommendation_sets')
    op.execute("DROP POLICY IF EXISTS tenant_isolation_policy ON learning_items")
    op.drop_index("ix_learning_items_tenant_id_user_id", table_name="learning_items")
    op.drop_table('learning_items')
