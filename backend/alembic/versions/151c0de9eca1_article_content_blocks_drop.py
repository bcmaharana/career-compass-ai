"""article content blocks: drop interview_topics old content columns

Revision ID: 151c0de9eca1
Revises: be55f657c85d
Create Date: 2026-08-24 00:00:01.000000

Step 2 of 2 — see `be55f657c85d_article_content_blocks_add.py`'s module
docstring for the full two-step rationale.

Refuses to run (raises rather than silently dropping real data) if any
row still has old-shape content (`discussion`, `image_key`, or a
non-empty `reference_links`) while its `blocks` column is still empty —
that combination means `scripts/migrate_article_content_to_blocks.py`
hasn't been run against this database yet, same defensive-check
precedent as `e333def9cd81_cikg_mvp2b_governance_expansion.py`'s
zero-draft-rows guard before narrowing a CHECK constraint.
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '151c0de9eca1'
down_revision: str | None = 'be55f657c85d'
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    connection = op.get_bind()
    unmigrated_count = connection.execute(
        sa.text(
            "SELECT count(*) FROM interview_topics "
            "WHERE blocks::text = '[]' AND ("
            "  (discussion IS NOT NULL AND discussion != '') "
            "  OR image_key IS NOT NULL "
            "  OR reference_links::text != '[]'"
            ")"
        )
    ).scalar_one()
    if unmigrated_count:
        raise RuntimeError(
            f"Refusing to drop interview_topics.discussion/image_key/reference_links: "
            f"{unmigrated_count} row(s) still have old-shape content with an empty "
            "blocks column. Run scripts/migrate_article_content_to_blocks.py against "
            "this database first."
        )
    op.drop_column('interview_topics', 'discussion')
    op.drop_column('interview_topics', 'image_key')
    op.drop_column('interview_topics', 'reference_links')


def downgrade() -> None:
    op.add_column(
        'interview_topics',
        sa.Column('reference_links', sa.JSON(), nullable=False, server_default='[]'),
    )
    op.add_column('interview_topics', sa.Column('image_key', sa.String(length=500), nullable=True))
    op.add_column('interview_topics', sa.Column('discussion', sa.Text(), nullable=True))
