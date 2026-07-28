"""add target_roles

Revision ID: a048a6cf0f9d
Revises: cee3cc57136a
Create Date: 2026-07-26 00:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'a048a6cf0f9d'
down_revision: str | None = 'cee3cc57136a'
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table('target_roles',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('tenant_id', sa.UUID(), nullable=False),
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('role_name', sa.String(length=255), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], name=op.f('fk_target_roles_tenant_id_tenants')),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_target_roles_user_id_users')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_target_roles'))
    )

    op.create_index("ix_target_roles_tenant_id_user_id", "target_roles", ["tenant_id", "user_id"])

    op.execute("ALTER TABLE target_roles ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE target_roles FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY tenant_isolation_policy ON target_roles
            USING (tenant_id = current_setting('app.tenant_id', true)::uuid)
            WITH CHECK (tenant_id = current_setting('app.tenant_id', true)::uuid)
        """
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS tenant_isolation_policy ON target_roles")
    op.drop_table('target_roles')
