"""showcase page background image

Adds ShowcasePage.background_image_url — a page-level image the owner
uploads and controls directly (public-bucket direct URL, same mechanics
as a ShowcaseColumn's own image_url), shown as the top card's background
once the page's name/headline moved into the public page's own brand
header bar. See ShowcasePage's own domain docstring for the full design.

Revision ID: a19d54339c33
Revises: 3be0e5e5f7f6
Create Date: 2026-08-27 10:00:00.000000

"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a19d54339c33'
down_revision: str | None = '3be0e5e5f7f6'
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        'showcase_pages', sa.Column('background_image_url', sa.String(length=500), nullable=True)
    )


def downgrade() -> None:
    op.drop_column('showcase_pages', 'background_image_url')
