"""job listing cache

Revision ID: c3aac483f98f
Revises: e1f4b8d67a52
Create Date: 2026-08-15 00:00:00.000000

Opportunity Intelligence (Phase 6) job listings via Adzuna. Global
reference data, not tenant-owned — job results for a given (role,
location) search are identical regardless of which tenant is asking, so
no tenant_id/RLS, same shape as CIKG's tables (prerequisite_of_edges,
etc.) rather than Resume Intelligence's tenant-owned pattern. Adzuna's
free tier is rate-limited (~1,000 calls/month) and this codebase has no
job scheduler, so results are cached here and refreshed at request time
against a TTL rather than fetched fresh on every page load.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'c3aac483f98f'
down_revision: str | None = 'e1f4b8d67a52'
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        'job_listing_cache',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('role_query', sa.String(length=255), nullable=False),
        sa.Column('location_query', sa.String(length=255), nullable=False),
        sa.Column('listings', sa.JSON(), nullable=False),
        sa.Column('fetched_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('source', sa.String(length=20), nullable=False, server_default='adzuna'),
        sa.UniqueConstraint('role_query', 'location_query', name='uq_job_listing_cache_search'),
    )


def downgrade() -> None:
    op.drop_table('job_listing_cache')
