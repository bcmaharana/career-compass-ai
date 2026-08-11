"""personal phone logins

Revision ID: 9b2d5a7c1e4f
Revises: 3d4607f025b8
Create Date: 2026-08-11 00:00:00.000000

personal_phone_logins backs phone login for Personal accounts
(app/application/identity/authenticate_user.py's execute_phone,
app/application/identity/update_user_profile.py's write path). Same
"deliberately NOT RLS-enforced" reasoning as password_reset_tokens: a
Personal login-by-phone attempt must resolve which tenant a phone
number belongs to *before* any tenant context can be bound.

phone_number_e164 is the primary key rather than a surrogate id — it IS
the natural key this table exists to enforce uniqueness on. Only
Personal-tenant users are ever registered here (see
is_personal_subdomain in app/domain/identity/personal_accounts.py);
Enterprise phone numbers stay purely tenant-scoped and untouched by
this table, since the same E.164 number can legitimately exist under
two different Enterprise tenants today (users.phone_number_e164's own
uniqueness constraint is per (tenant_id, phone_number_e164), not
global — see 65b85da50536_user_phone_number_e164.py).

Backfills existing Personal users who already saved a phone number via
Settings > Profile before this table existed, so they get phone login
without having to re-save anything. ON CONFLICT DO NOTHING guards
against the (extremely unlikely) case of two different Personal users
already sharing the same E.164 number — first one wins, silently; this
is a migration-time edge case, not expected to occur in practice.
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '9b2d5a7c1e4f'
down_revision: str | None = '3d4607f025b8'
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table('personal_phone_logins',
    sa.Column('phone_number_e164', sa.String(length=20), nullable=False),
    sa.Column('tenant_id', sa.UUID(), nullable=False),
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], name=op.f('fk_personal_phone_logins_tenant_id_tenants')),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_personal_phone_logins_user_id_users')),
    sa.PrimaryKeyConstraint('phone_number_e164', name=op.f('pk_personal_phone_logins')),
    sa.UniqueConstraint('user_id', name=op.f('uq_personal_phone_logins_user_id'))
    )

    # No ENABLE/FORCE ROW LEVEL SECURITY / CREATE POLICY here — see the
    # module docstring above. Deliberate, not an oversight.

    op.execute(
        """
        INSERT INTO personal_phone_logins (phone_number_e164, tenant_id, user_id, updated_at)
        SELECT u.phone_number_e164, u.tenant_id, u.id, now()
        FROM users u
        JOIN tenants t ON t.id = u.tenant_id
        WHERE u.phone_number_e164 IS NOT NULL
          AND t.subdomain LIKE 'p-%'
        ON CONFLICT (phone_number_e164) DO NOTHING
        """
    )


def downgrade() -> None:
    op.drop_table('personal_phone_logins')
