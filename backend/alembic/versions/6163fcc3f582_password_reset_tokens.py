"""password reset tokens

Revision ID: 6163fcc3f582
Revises: f1a4c9e6b3d2
Create Date: 2026-08-10 00:00:00.000000

password_reset_tokens backs the "forgot password" flow
(app/application/identity/request_password_reset.py,
reset_password.py). Deliberately NOT RLS-enforced, unlike every other
tenant-owned table added since the foundational migration — the
confirm-reset step must resolve which tenant a token belongs to
*before* any tenant context can be bound, the same chicken-and-egg
problem `tenants`/`permissions` already have (see that migration's own
"intentionally exempt from RLS" comment and
docs/architecture/multi-tenancy-design.md). tenant_id/user_id are still
present with real foreign keys for referential integrity — RLS
exemption is not the same as "no tenant relationship."
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '6163fcc3f582'
down_revision: str | None = 'f1a4c9e6b3d2'
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table('password_reset_tokens',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('tenant_id', sa.UUID(), nullable=False),
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('token_hash', sa.String(length=64), nullable=False),
    sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('used_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], name=op.f('fk_password_reset_tokens_tenant_id_tenants')),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_password_reset_tokens_user_id_users')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_password_reset_tokens')),
    sa.UniqueConstraint('token_hash', name=op.f('uq_password_reset_tokens_token_hash'))
    )

    op.create_index(
        "ix_password_reset_tokens_tenant_id_user_id",
        "password_reset_tokens",
        ["tenant_id", "user_id"],
    )

    # No ENABLE/FORCE ROW LEVEL SECURITY / CREATE POLICY here — see the
    # module docstring above. This is deliberate, not an oversight.


def downgrade() -> None:
    op.drop_index("ix_password_reset_tokens_tenant_id_user_id", table_name="password_reset_tokens")
    op.drop_table('password_reset_tokens')
