"""showcase page header fields: name, headline, summary

Revision ID: fdcb71317e5d
Revises: 151c0de9eca1
Create Date: 2026-08-24 12:00:00.000000

Direct request: a top-bar on the Showcase Page — profile picture on the
left, name+headline and the executive summary on the right. `name`/
`headline`/`summary` are seeded once (see ShowcasePageService.get_or_create)
from the owning User's display_name and the resolved CareerProfile's
headline/summary, then independently editable — same "seed once, not a
sync" precedent `blocks` itself already follows.

No photo column: the profile picture is deliberately NOT copied/stored
here at all ("the profile picture will be fixed" — direct request), only
ever resolved live from the real CareerProfile at read time.

All three columns are nullable with no default and no backfill in this
migration — an existing showcase_pages row (pre-dating this feature)
simply has them NULL until scripts/backfill_showcase_page_header.py runs
(a real, if very small, prod row exists and needs its header populated
this way, not silently left blank).
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'fdcb71317e5d'
down_revision: str | None = '151c0de9eca1'
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column('showcase_pages', sa.Column('name', sa.String(length=255), nullable=True))
    op.add_column('showcase_pages', sa.Column('headline', sa.Text(), nullable=True))
    op.add_column('showcase_pages', sa.Column('summary', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('showcase_pages', 'summary')
    op.drop_column('showcase_pages', 'headline')
    op.drop_column('showcase_pages', 'name')
