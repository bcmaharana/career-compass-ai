"""add tag to target_roles

Revision ID: 1007d872b535
Revises: a048a6cf0f9d
Create Date: 2026-07-26 00:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '1007d872b535'
down_revision: str | None = 'a048a6cf0f9d'
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def _initials(role_name: str, max_len: int = 3) -> str:
    """Best-effort backfill for existing rows: first letter of each
    word, e.g. "Enterprise Agile Coach" -> "EAC" — deliberately matches
    the exact convention the feature itself asks users to follow, so
    existing real rows (not just placeholder data) get a sensible tag
    instead of a meaningless one.
    """
    letters = "".join(word[0] for word in role_name.split() if word)[:max_len]
    return (letters or role_name[:max_len] or "TBD").upper()


def upgrade() -> None:
    op.add_column('target_roles', sa.Column('tag', sa.String(length=3), nullable=True))

    connection = op.get_bind()

    # Cross-tenant read+write to backfill existing rows — disable RLS
    # for the duration, same caveat as every other backfill migration in
    # this codebase: alembic runs with no app.tenant_id context set, so
    # RLS would otherwise silently make the SELECT below return zero
    # rows (and would block the UPDATEs too).
    op.execute("ALTER TABLE target_roles DISABLE ROW LEVEL SECURITY")

    rows = connection.execute(
        sa.text("SELECT id, role_name FROM target_roles WHERE tag IS NULL")
    ).fetchall()
    for row in rows:
        connection.execute(
            sa.text("UPDATE target_roles SET tag = :tag WHERE id = :id"),
            {"tag": _initials(row.role_name), "id": row.id},
        )

    op.execute("ALTER TABLE target_roles ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE target_roles FORCE ROW LEVEL SECURITY")

    op.alter_column('target_roles', 'tag', existing_type=sa.String(length=3), nullable=False)


def downgrade() -> None:
    op.drop_column('target_roles', 'tag')
