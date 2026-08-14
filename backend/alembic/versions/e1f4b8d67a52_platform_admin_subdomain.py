"""platform admin subdomain snapshot

Revision ID: e1f4b8d67a52
Revises: d8f3a5c17b62
Create Date: 2026-08-14 00:00:00.000000

Adds platform_admins.subdomain, a snapshot of the granted account's
tenant subdomain (same "avoid a cross-tenant lookup to render the
admins list" reasoning as the existing email/full_name snapshot
columns). Needed because the admins list previously had no way to tell
apart two grants for the same email under different tenants (e.g. a
Personal account and an Enterprise account sharing an email) — the
subdomain, and whether it's Personal (via is_personal_subdomain) or
Enterprise, is now shown per row.

Backfilled from tenants for any existing grants before the NOT NULL
constraint is applied, following the same "temporarily nullable, backfill,
then constrain" shape used elsewhere in this codebase for backfills
that need to run outside the app's own request-time RLS context.
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'e1f4b8d67a52'
down_revision: str | None = 'd8f3a5c17b62'
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column('platform_admins', sa.Column('subdomain', sa.String(length=63), nullable=True))
    op.execute(
        """
        UPDATE platform_admins
        SET subdomain = tenants.subdomain
        FROM tenants
        WHERE tenants.id = platform_admins.tenant_id
        """
    )
    op.alter_column('platform_admins', 'subdomain', nullable=False)


def downgrade() -> None:
    op.drop_column('platform_admins', 'subdomain')
