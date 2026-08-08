"""skill categories name not globally unique

Revision ID: 02e41ab151ce
Revises: e8e87feda0bd
Create Date: 2026-07-29 14:45:00.000000

cikg-mvp1-seed-data.md's own seed content reuses generic category names
across unrelated domains (e.g. "Regulatory" under both Healthcare's
Health Information & Compliance and Finance's Risk & Compliance) — these
are legitimately different nodes that happen to share an English label.
The uq_skill_categories_name constraint added in e8e87feda0bd was wrong;
disambiguation is by hierarchy position (category_parents), not by name.
"""
from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '02e41ab151ce'
down_revision: str | None = 'e8e87feda0bd'
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint("uq_skill_categories_name", "skill_categories", type_="unique")


def downgrade() -> None:
    op.create_unique_constraint("uq_skill_categories_name", "skill_categories", ["name"])
