"""interview topic reference links

Revision ID: b3f6a1c9d824
Revises: a7c2f4e918bd
Create Date: 2026-08-16 20:00:00.000000

Adds `reference_links` (list[{url, label}], same JSON-blob shape
`interview_questions.reference_links` already uses) to
`interview_topics` — requested directly by the user so Topics can carry
the same labeled external reference links Questions already do.
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'b3f6a1c9d824'
down_revision: str | None = 'a7c2f4e918bd'
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        'interview_topics',
        sa.Column('reference_links', sa.JSON(), nullable=False, server_default='[]'),
    )


def downgrade() -> None:
    op.drop_column('interview_topics', 'reference_links')
