"""resume inclusion toggles and profile fields

Revision ID: d8f3a5c17b62
Revises: c7e2f9a04d18
Create Date: 2026-08-14 00:00:00.000000

Two unrelated additions requested together in the same session:

1. Resume-inclusion toggles (app/adapters/documents/, ResumeExportService):
   - include_in_resume BOOLEAN NOT NULL DEFAULT true on every per-item
     orderable entity (experiences, educations, certifications,
     career_highlights, key_achievements, career_goals,
     peer_endorsements) — a "print this specific entry in the resume?"
     switch, default on so existing data behaves exactly as before this
     migration.
   - resume_section_toggles JSON NULL on career_profiles — whole-section
     on/off, keyed by the same section keys section_order already uses.
     NULL/missing key means "on," so an existing profile with no saved
     preference here also behaves exactly as before.
   core_competencies' own per-item toggle lives inside that column's
   existing JSON blob (CoreCompetency.include_in_resume), not a new
   column — no schema change needed for it.

2. Three new Settings > Profile fields on users: visa_status,
   linkedin_url, other_professional_url — all nullable text, same shape
   as the existing country/language/address_line1 columns.
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'd8f3a5c17b62'
down_revision: str | None = 'c7e2f9a04d18'
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

_INCLUDE_IN_RESUME_TABLES = (
    'experiences',
    'educations',
    'certifications',
    'career_highlights',
    'key_achievements',
    'career_goals',
    'peer_endorsements',
)


def upgrade() -> None:
    for table in _INCLUDE_IN_RESUME_TABLES:
        op.add_column(
            table,
            sa.Column(
                'include_in_resume',
                sa.Boolean(),
                nullable=False,
                server_default=sa.true(),
            ),
        )

    op.add_column('career_profiles', sa.Column('resume_section_toggles', sa.JSON(), nullable=True))

    op.add_column('users', sa.Column('visa_status', sa.String(length=100), nullable=True))
    op.add_column('users', sa.Column('linkedin_url', sa.String(length=2048), nullable=True))
    op.add_column('users', sa.Column('other_professional_url', sa.String(length=2048), nullable=True))


def downgrade() -> None:
    op.drop_column('users', 'other_professional_url')
    op.drop_column('users', 'linkedin_url')
    op.drop_column('users', 'visa_status')

    op.drop_column('career_profiles', 'resume_section_toggles')

    for table in reversed(_INCLUDE_IN_RESUME_TABLES):
        op.drop_column(table, 'include_in_resume')
