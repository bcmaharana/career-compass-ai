"""platform identity integration

Revision ID: 3be0e5e5f7f6
Revises: fdcb71317e5d
Create Date: 2026-08-25 01:53:54.269424

Hand-trimmed from the raw `alembic revision --autogenerate` output —
that raw diff also proposed dropping ~10 unrelated indexes/constraints
(functional indexes on lower(...), the search_vector generated column's
NOT NULL, etc.) purely because SQLAlchemy's declarative metadata
doesn't perfectly round-trip those hand-written-SQL constructs, not
because anything about them actually changed. Only the two columns this
migration is actually about are kept — see
docs/adr/ADR-010-platform-identity-integration.md.
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '3be0e5e5f7f6'
down_revision: str | None = 'fdcb71317e5d'
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        'tenants',
        sa.Column('platform_org_id', postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_index(
        'uq_tenants_platform_org_id',
        'tenants',
        ['platform_org_id'],
        unique=True,
        postgresql_where=sa.text('platform_org_id IS NOT NULL'),
    )

    op.add_column(
        'users',
        sa.Column('platform_account_id', postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_index(
        'uq_users_platform_account_id_per_tenant',
        'users',
        ['tenant_id', 'platform_account_id'],
        unique=True,
        postgresql_where=sa.text('platform_account_id IS NOT NULL'),
    )


def downgrade() -> None:
    op.drop_index('uq_users_platform_account_id_per_tenant', table_name='users')
    op.drop_column('users', 'platform_account_id')

    op.drop_index('uq_tenants_platform_org_id', table_name='tenants')
    op.drop_column('tenants', 'platform_org_id')
