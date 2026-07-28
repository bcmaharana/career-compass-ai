"""add country language address to users

Revision ID: 6f8912663358
Revises: 7e5d44c12c51
Create Date: 2026-07-28 00:12:32.683174

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '6f8912663358'
down_revision: str | None = '7e5d44c12c51'
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column('users', sa.Column('country', sa.String(length=2), nullable=True))
    op.add_column('users', sa.Column('language', sa.String(length=10), nullable=True))
    op.add_column('users', sa.Column('address', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('users', 'address')
    op.drop_column('users', 'language')
    op.drop_column('users', 'country')
