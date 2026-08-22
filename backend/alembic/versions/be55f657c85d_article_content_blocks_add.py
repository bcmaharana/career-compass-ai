"""article content blocks: add interview_topics.blocks

Revision ID: be55f657c85d
Revises: ee3d0b0ddfe8
Create Date: 2026-08-24 00:00:00.000000

Step 1 of 2 (direct 2026-08-24 request: "Articles don't have same design
of + Add block functionality" — porting ShowcasePage's freeform
row/column content-block model to InterviewTopic/Article). Adds
`interview_topics.blocks` (same JSON row/column shape as
`showcase_pages.blocks`, see app/domain/content_blocks/entities.py) with
a `'[]'` default so every existing row gets a valid empty value
immediately, without yet touching the old `discussion`/`image_key`/
`reference_links` columns those rows' real content still lives in.

Deliberately NOT a single migration that also drops the old columns:
`scripts/migrate_article_content_to_blocks.py` must run in between (same
disabled-RLS-for-its-own-duration, content-preservation-verified-before
-write discipline as `scripts/migrate_showcase_blocks_to_columns.py`) to
convert each row's real discussion/image/reference_links content into
equivalent blocks before anything old is dropped. See
`c94a2fbb2e91_article_content_blocks_drop.py` (step 2) for the
defensive check that refuses to drop the old columns if any row still
has real old-shape content sitting in an unmigrated (empty) `blocks`.
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'be55f657c85d'
down_revision: str | None = 'ee3d0b0ddfe8'
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        'interview_topics',
        sa.Column('blocks', sa.JSON(), nullable=False, server_default='[]'),
    )


def downgrade() -> None:
    op.drop_column('interview_topics', 'blocks')
