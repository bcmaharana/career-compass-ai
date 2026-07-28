"""add last_login_at to users

Revision ID: c39a9984c880
Revises: 4ea882bbc7ad
Create Date: 2026-07-27 22:41:48.815105

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'c39a9984c880'
down_revision: str | None = '4ea882bbc7ad'
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column('users', sa.Column('last_login_at', sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column('users', 'last_login_at')
