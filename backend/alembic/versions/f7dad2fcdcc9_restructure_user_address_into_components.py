"""restructure user address into components

Revision ID: f7dad2fcdcc9
Revises: 6f8912663358
Create Date: 2026-07-28 00:47:26.197904

"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f7dad2fcdcc9'
down_revision: str | None = '6f8912663358'
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column('users', sa.Column('address_line1', sa.String(length=255), nullable=True))
    op.add_column('users', sa.Column('address_line2', sa.String(length=255), nullable=True))
    op.add_column('users', sa.Column('city', sa.String(length=100), nullable=True))
    op.add_column('users', sa.Column('state', sa.String(length=100), nullable=True))
    op.add_column('users', sa.Column('postal_code', sa.String(length=20), nullable=True))
    op.drop_column('users', 'address')


def downgrade() -> None:
    op.add_column('users', sa.Column('address', sa.Text(), nullable=True))
    op.drop_column('users', 'postal_code')
    op.drop_column('users', 'state')
    op.drop_column('users', 'city')
    op.drop_column('users', 'address_line2')
    op.drop_column('users', 'address_line1')
