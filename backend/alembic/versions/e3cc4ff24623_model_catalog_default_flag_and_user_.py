"""model catalog default flag and user model preference

Revision ID: e3cc4ff24623
Revises: bdc2e7597843
Create Date: 2026-07-28 16:35:16.895641

"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e3cc4ff24623'
down_revision: str | None = 'bdc2e7597843'
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        'model_versions',
        sa.Column('is_default', sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    # Backfill: whatever was already "active" before this column existed
    # becomes the platform default — preserves current chat behavior for
    # anyone with no explicit preference yet.
    op.execute("UPDATE model_versions SET is_default = true WHERE status = 'active'")

    op.add_column(
        'users',
        sa.Column('preferred_model_version_id', sa.UUID(), nullable=True),
    )
    op.create_foreign_key(
        op.f('fk_users_preferred_model_version_id_model_versions'),
        'users',
        'model_versions',
        ['preferred_model_version_id'],
        ['id'],
    )


def downgrade() -> None:
    op.drop_constraint(
        op.f('fk_users_preferred_model_version_id_model_versions'), 'users', type_='foreignkey'
    )
    op.drop_column('users', 'preferred_model_version_id')
    op.drop_column('model_versions', 'is_default')
