"""add full_name to users

Revision ID: ae48c87e76d3
Revises: b9a4fcfb3f69
Create Date: 2026-07-25 00:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'ae48c87e76d3'
down_revision: str | None = 'b9a4fcfb3f69'
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column('users', sa.Column('full_name', sa.String(length=255), nullable=True))

    # --- Backfill across all tenants ---
    # Alembic runs with no app.tenant_id context set, so the users
    # table's existing tenant_isolation_policy (Phase 1 migration) would
    # silently block this UPDATE from touching any row otherwise —
    # temporarily disable RLS for the backfill, then restore it exactly
    # as it was (ENABLE + FORCE), per the documented multi-tenancy
    # migration gotcha. The policy definition itself is untouched by
    # DISABLE/ENABLE, only whether it's currently enforced.
    op.execute("ALTER TABLE users DISABLE ROW LEVEL SECURITY")
    op.execute(
        """
        UPDATE users
        SET full_name = initcap(replace(split_part(email, '@', 1), '.', ' '))
        WHERE full_name IS NULL
        """
    )
    op.execute("ALTER TABLE users ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE users FORCE ROW LEVEL SECURITY")

    op.alter_column('users', 'full_name', existing_type=sa.String(length=255), nullable=False)


def downgrade() -> None:
    op.drop_column('users', 'full_name')
