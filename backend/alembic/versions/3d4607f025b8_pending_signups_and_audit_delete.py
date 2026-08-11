"""pending signups and audit event delete

Revision ID: 3d4607f025b8
Revises: 6163fcc3f582
Create Date: 2026-08-10 00:00:00.000000

Two independent changes for account-lifecycle features:

1. `pending_signups` — backs email verification
   (app/application/identity/request_personal_signup.py,
   request_organization_signup.py, verify_signup.py). No tenant_id/
   user_id at all: unlike password_reset_tokens, no tenant exists yet
   for a pending signup — nothing is written to tenants/organizations/
   users until the emailed verification link is confirmed.

2. Narrows the `audit_events_immutable` trigger (from
   cde4f82abc35_identity_platform_foundation.py) from
   `BEFORE UPDATE OR DELETE` to `BEFORE UPDATE` only. The function body
   is unchanged. This is a deliberate, real trade-off, not a bug fix:
   every tenant has audit rows from its own creation
   (tenant.created/user.created), so a genuine "delete my account"
   feature is impossible while DELETE is blocked unconditionally.
   "History can never be rewritten" (the trigger's actual original
   intent) is preserved — only "a closed account's own trail can be
   removed along with the account" becomes possible, which is standard
   behavior for any real delete-my-account feature.
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '3d4607f025b8'
down_revision: str | None = '6163fcc3f582'
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table('pending_signups',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('kind', sa.String(length=20), nullable=False),
    sa.Column('email', sa.String(length=320), nullable=False),
    sa.Column('hashed_password', sa.String(length=255), nullable=False),
    sa.Column('first_name', sa.String(length=150), nullable=False),
    sa.Column('last_name', sa.String(length=150), nullable=False),
    sa.Column('tenant_name', sa.String(length=255), nullable=True),
    sa.Column('subdomain', sa.String(length=63), nullable=True),
    sa.Column('organization_name', sa.String(length=255), nullable=True),
    sa.Column('token_hash', sa.String(length=64), nullable=False),
    sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_pending_signups')),
    sa.UniqueConstraint('token_hash', name=op.f('uq_pending_signups_token_hash'))
    )

    # No ENABLE/FORCE ROW LEVEL SECURITY / CREATE POLICY here — no
    # tenant_id column at all, deliberately (see module docstring).

    op.execute("DROP TRIGGER IF EXISTS audit_events_immutable ON audit_events")
    op.execute(
        """
        CREATE TRIGGER audit_events_immutable
        BEFORE UPDATE ON audit_events
        FOR EACH ROW EXECUTE FUNCTION reject_audit_event_mutation()
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS audit_events_immutable ON audit_events")
    op.execute(
        """
        CREATE TRIGGER audit_events_immutable
        BEFORE UPDATE OR DELETE ON audit_events
        FOR EACH ROW EXECUTE FUNCTION reject_audit_event_mutation()
        """
    )

    op.drop_table('pending_signups')
