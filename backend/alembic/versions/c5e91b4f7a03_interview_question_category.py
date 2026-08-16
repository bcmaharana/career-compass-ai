"""interview question category

Revision ID: c5e91b4f7a03
Revises: b3f6a1c9d824
Create Date: 2026-08-17 09:00:00.000000

Adds `category` (free-text grouping label, same shape as
`interview_topics.section`) to `interview_questions` — requested
directly by the user so Questions can be grouped/filtered the same way
Topics already group by section.
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'c5e91b4f7a03'
down_revision: str | None = 'b3f6a1c9d824'
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        'interview_questions',
        sa.Column('category', sa.String(length=255), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('interview_questions', 'category')
