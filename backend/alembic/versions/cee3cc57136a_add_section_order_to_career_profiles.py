"""add section_order to career_profiles

Revision ID: cee3cc57136a
Revises: 4d10c989f546
Create Date: 2026-07-26 00:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'cee3cc57136a'
down_revision: str | None = '4d10c989f546'
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    # Nullable, no backfill needed — NULL means "use the page's default
    # section order" at the application layer (see
    # CareerProfileService.update), so every existing row is already in
    # a valid state with no data migration required.
    op.add_column('career_profiles', sa.Column('section_order', sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column('career_profiles', 'section_order')
