"""core competencies categories

Revision ID: c3f8a217b4d6
Revises: b7e4c8a91f3d
Create Date: 2026-08-05 15:10:00.000000

Converts career_profiles.core_competencies from a flat list of strings
to a list of {"name": str, "category": str | None} objects, so a Core
Competencies / My Skills entry can carry an associated category (e.g.
"Agile & Scaling") without reviving the global SkillCategory catalog
ADR-005 removed — category here is a plain per-item attribute, editable
per entry, not a link into shared reference data.
"""
from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'c3f8a217b4d6'
down_revision: str | None = 'b7e4c8a91f3d'
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    # Cross-tenant UPDATE — Alembic runs with no app.tenant_id session
    # context, so career_profiles' forced tenant_isolation_policy would
    # otherwise silently block this backfill from touching any row. See
    # CLAUDE.md's documented RLS-backfill gotcha.
    op.execute("ALTER TABLE career_profiles DISABLE ROW LEVEL SECURITY")
    op.execute(
        """
        UPDATE career_profiles
        SET core_competencies = (
            SELECT COALESCE(jsonb_agg(jsonb_build_object('name', elem, 'category', NULL)), '[]'::jsonb)
            FROM jsonb_array_elements_text(core_competencies::jsonb) elem
        )
        WHERE jsonb_array_length(core_competencies::jsonb) > 0
        """
    )
    op.execute("ALTER TABLE career_profiles ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE career_profiles FORCE ROW LEVEL SECURITY")


def downgrade() -> None:
    op.execute("ALTER TABLE career_profiles DISABLE ROW LEVEL SECURITY")
    op.execute(
        """
        UPDATE career_profiles
        SET core_competencies = (
            SELECT COALESCE(jsonb_agg(elem->>'name'), '[]'::jsonb)
            FROM jsonb_array_elements(core_competencies::jsonb) elem
        )
        WHERE jsonb_array_length(core_competencies::jsonb) > 0
        """
    )
    op.execute("ALTER TABLE career_profiles ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE career_profiles FORCE ROW LEVEL SECURITY")
