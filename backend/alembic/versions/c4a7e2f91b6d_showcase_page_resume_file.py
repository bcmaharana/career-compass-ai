"""showcase page resume file

Adds ShowcasePage.resume_file_key/resume_file_name — a real resume
document (PDF or Word) the owner uploads and controls directly, stored
in the private resumes bucket (same bucket/adapter as
resume_intelligence's uploads and ResumeExportService's generated
files — this file carries the same PII, unlike ShowcasePage's own
public-bucket block/background images). No parsing: the file is stored
and served back as-is, never read for content. See
ShowcasePageService.upload_resume for the upload path and
PublicShowcaseService.get_showcase_page for how the public page resolves
a fresh, time-limited download URL from the stored key.

Revision ID: c4a7e2f91b6d
Revises: a19d54339c33
Create Date: 2026-09-04 09:00:00.000000

"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c4a7e2f91b6d'
down_revision: str | None = 'a19d54339c33'
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        'showcase_pages', sa.Column('resume_file_key', sa.String(length=500), nullable=True)
    )
    op.add_column(
        'showcase_pages', sa.Column('resume_file_name', sa.String(length=255), nullable=True)
    )


def downgrade() -> None:
    op.drop_column('showcase_pages', 'resume_file_name')
    op.drop_column('showcase_pages', 'resume_file_key')
