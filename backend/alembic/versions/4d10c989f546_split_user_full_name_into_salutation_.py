"""split user full_name into salutation/first_name/last_name

Revision ID: 4d10c989f546
Revises: ae48c87e76d3
Create Date: 2026-07-26 00:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '4d10c989f546'
down_revision: str | None = 'ae48c87e76d3'
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

# No real first/last name data exists yet for pre-existing users (the
# prior full_name column was itself only ever a placeholder derived from
# email — see migration ae48c87e76d3). Rather than propagate that guess
# further, existing rows get an explicit placeholder here; real values
# land whenever a proper name-entry UI ships. Adding NOT NULL columns
# with a constant server_default is DDL, not a per-row UPDATE, so it
# doesn't touch RLS at all (unlike ae48c87e76d3's backfill) — Postgres
# 11+ applies a constant column default without a table rewrite.
PLACEHOLDER_FIRST_NAME = "First"
PLACEHOLDER_LAST_NAME = "Last"


def upgrade() -> None:
    op.add_column('users', sa.Column('salutation', sa.String(length=20), nullable=True))
    op.add_column(
        'users',
        sa.Column(
            'first_name', sa.String(length=150), nullable=False, server_default=PLACEHOLDER_FIRST_NAME
        ),
    )
    op.add_column(
        'users',
        sa.Column(
            'last_name', sa.String(length=150), nullable=False, server_default=PLACEHOLDER_LAST_NAME
        ),
    )
    # Drop the defaults now that existing rows are backfilled — future
    # inserts must supply a real first/last name explicitly.
    op.alter_column('users', 'first_name', server_default=None)
    op.alter_column('users', 'last_name', server_default=None)

    op.drop_column('users', 'full_name')


def downgrade() -> None:
    op.add_column('users', sa.Column('full_name', sa.String(length=255), nullable=True))

    # Cross-tenant UPDATE, same RLS caveat as ae48c87e76d3's backfill —
    # disable/re-enable around it rather than an in-place ADD COLUMN
    # DEFAULT, since the value here is computed per row, not constant.
    op.execute("ALTER TABLE users DISABLE ROW LEVEL SECURITY")
    op.execute(
        """
        UPDATE users
        SET full_name = trim(
            coalesce(salutation || ' ', '') || first_name || ' ' || last_name
        )
        """
    )
    op.execute("ALTER TABLE users ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE users FORCE ROW LEVEL SECURITY")

    op.alter_column('users', 'full_name', existing_type=sa.String(length=255), nullable=False)

    op.drop_column('users', 'last_name')
    op.drop_column('users', 'first_name')
    op.drop_column('users', 'salutation')
