"""user phone_number_e164 for phone login lookup

Revision ID: 65b85da50536
Revises: e3cc4ff24623
Create Date: 2026-07-28 18:05:00.000000

"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '65b85da50536'
down_revision: str | None = 'e3cc4ff24623'
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        'users',
        sa.Column('phone_number_e164', sa.String(length=20), nullable=True),
    )
    # Nullable + unique, not a partial/filtered index: Postgres treats
    # every NULL as distinct for a plain unique constraint, so any number
    # of users with no phone_number_e164 yet coexist fine — only two rows
    # both claiming the *same* real E.164 number within one tenant would
    # collide, which is exactly the case phone login depends on being
    # impossible. Same per-tenant-scoped shape as uq_users_tenant_id_email.
    op.create_unique_constraint(
        op.f('uq_users_tenant_id_phone_number_e164'),
        'users',
        ['tenant_id', 'phone_number_e164'],
    )


def downgrade() -> None:
    op.drop_constraint(
        op.f('uq_users_tenant_id_phone_number_e164'), 'users', type_='unique'
    )
    op.drop_column('users', 'phone_number_e164')
