"""add phone number to users

Revision ID: 7e5d44c12c51
Revises: c39a9984c880
Create Date: 2026-07-27 23:47:53.774762

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '7e5d44c12c51'
down_revision: str | None = 'c39a9984c880'
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column('users', sa.Column('phone_number', sa.String(length=30), nullable=True))


def downgrade() -> None:
    op.drop_column('users', 'phone_number')
