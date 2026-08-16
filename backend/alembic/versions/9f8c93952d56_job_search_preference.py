"""job search preference

Revision ID: 9f8c93952d56
Revises: 092365d69ca9
Create Date: 2026-08-15 00:30:00.000000

Settings > Job Search Preference (Phase 6 follow-up): 5 new nullable
columns on `users`, same "plain field on User, None means default
behavior" pattern as `preferred_model_version_id`. All None reproduces
the original behavior (profile city/state, no other filters).
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '9f8c93952d56'
down_revision: str | None = '092365d69ca9'
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column('users', sa.Column('job_search_location', sa.String(length=255), nullable=True))
    op.add_column('users', sa.Column('job_search_max_days_old', sa.Integer(), nullable=True))
    op.add_column('users', sa.Column('job_search_distance_miles', sa.Integer(), nullable=True))
    op.add_column('users', sa.Column('job_search_employment_time', sa.String(length=20), nullable=True))
    op.add_column('users', sa.Column('job_search_employment_type', sa.String(length=20), nullable=True))

    # job_listing_cache: expand the cache key to the new filter
    # dimensions. 0/'' sentinels (not NULL) — Postgres treats every NULL
    # as distinct for UNIQUE constraint purposes, which would silently
    # defeat this table's whole purpose. server_default backfills
    # existing cache rows (all of which represent "no preference"
    # searches, since this preference didn't exist before) to the
    # sentinel automatically.
    op.drop_constraint('uq_job_listing_cache_search', 'job_listing_cache', type_='unique')
    op.add_column(
        'job_listing_cache',
        sa.Column('max_days_old', sa.Integer(), nullable=False, server_default='0'),
    )
    op.add_column(
        'job_listing_cache',
        sa.Column('distance_miles', sa.Integer(), nullable=False, server_default='0'),
    )
    op.add_column(
        'job_listing_cache',
        sa.Column('employment_time', sa.String(length=20), nullable=False, server_default=''),
    )
    op.add_column(
        'job_listing_cache',
        sa.Column('employment_type', sa.String(length=20), nullable=False, server_default=''),
    )
    op.create_unique_constraint(
        'uq_job_listing_cache_search',
        'job_listing_cache',
        ['role_query', 'location_query', 'max_days_old', 'distance_miles', 'employment_time', 'employment_type'],
    )


def downgrade() -> None:
    op.drop_constraint('uq_job_listing_cache_search', 'job_listing_cache', type_='unique')
    op.drop_column('job_listing_cache', 'employment_type')
    op.drop_column('job_listing_cache', 'employment_time')
    op.drop_column('job_listing_cache', 'distance_miles')
    op.drop_column('job_listing_cache', 'max_days_old')
    op.create_unique_constraint(
        'uq_job_listing_cache_search', 'job_listing_cache', ['role_query', 'location_query']
    )

    op.drop_column('users', 'job_search_employment_type')
    op.drop_column('users', 'job_search_employment_time')
    op.drop_column('users', 'job_search_distance_miles')
    op.drop_column('users', 'job_search_max_days_old')
    op.drop_column('users', 'job_search_location')
