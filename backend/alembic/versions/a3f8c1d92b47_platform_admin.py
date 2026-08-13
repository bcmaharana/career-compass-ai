"""platform admin

Revision ID: a3f8c1d92b47
Revises: d4a7f2c9b6e1
Create Date: 2026-08-13 00:00:00.000000

Two new tables backing the first cross-tenant admin concept in this app
(app/domain/platform_admin/): platform_admins (grants specific users
permission codes like platform.settings.edit, regardless of which tenant
they belong to) and platform_settings (a general key/value store for
platform-wide config previously only editable via .env + a redeploy —
e.g. RESEND_FROM_EMAIL/RESEND_WELCOME_FROM_EMAIL).

Neither table carries a RLS policy — same "no ENABLE/FORCE ROW LEVEL
SECURITY, deliberate not an oversight" shape as personal_phone_logins
(9b2d5a7c1e4f_personal_phone_logins.py): a platform-admin permission
check must be answerable for the caller's own (tenant_id, user_id)
without needing tenant context bound first, and platform_settings is
genuinely global, not owned by any tenant at all.
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'a3f8c1d92b47'
down_revision: str | None = 'd4a7f2c9b6e1'
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        'platform_admins',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('tenant_id', sa.UUID(), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('full_name', sa.String(length=255), nullable=False),
        sa.Column('permission_codes', sa.JSON(), nullable=False),
        sa.Column('granted_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('granted_by_user_id', sa.UUID(), nullable=False),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], name=op.f('fk_platform_admins_tenant_id_tenants')),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_platform_admins_user_id_users')),
        sa.ForeignKeyConstraint(['granted_by_user_id'], ['users.id'], name=op.f('fk_platform_admins_granted_by_user_id_users')),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_platform_admins')),
        sa.UniqueConstraint('tenant_id', 'user_id', name='uq_platform_admins_tenant_user'),
    )

    op.create_table(
        'platform_settings',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('key', sa.String(length=100), nullable=False),
        sa.Column('value', sa.Text(), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_by_user_id', sa.UUID(), nullable=True),
        sa.ForeignKeyConstraint(['updated_by_user_id'], ['users.id'], name=op.f('fk_platform_settings_updated_by_user_id_users')),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_platform_settings')),
        sa.UniqueConstraint('key', name=op.f('uq_platform_settings_key')),
    )

    # No ENABLE/FORCE ROW LEVEL SECURITY / CREATE POLICY here — see the
    # module docstring above. Deliberate, not an oversight.


def downgrade() -> None:
    op.drop_table('platform_settings')
    op.drop_table('platform_admins')
