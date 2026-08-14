"""resume export fields

Revision ID: c7e2f9a04d18
Revises: a3f8c1d92b47
Create Date: 2026-08-13 00:00:00.000000

Three nullable columns on career_profiles backing the Download Resume
feature (app/application/career_profile/resume_export_service.py):
resume_docx_key/resume_pdf_key (storage keys in the private resumes
bucket for the most recently generated document, one per format,
overwritten on regeneration — not a history) and resume_generated_at.
No RLS changes needed — career_profiles is already tenant-owned/RLS-
enforced; these are just three more nullable columns on an existing
table.
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'c7e2f9a04d18'
down_revision: str | None = 'a3f8c1d92b47'
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column('career_profiles', sa.Column('resume_docx_key', sa.String(length=512), nullable=True))
    op.add_column('career_profiles', sa.Column('resume_pdf_key', sa.String(length=512), nullable=True))
    op.add_column('career_profiles', sa.Column('resume_generated_at', sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column('career_profiles', 'resume_generated_at')
    op.drop_column('career_profiles', 'resume_pdf_key')
    op.drop_column('career_profiles', 'resume_docx_key')
