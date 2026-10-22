"""Record credentials that do not expire."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "b74c2d91e6a0"
down_revision: str | None = "9d72f1a6b3c8"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "certifications",
        sa.Column("does_not_expire", sa.Boolean(), server_default=sa.false(), nullable=False),
    )
    op.add_column(
        "career_profile_skills",
        sa.Column("does_not_expire", sa.Boolean(), server_default=sa.false(), nullable=False),
    )


def downgrade() -> None:
    op.drop_column("career_profile_skills", "does_not_expire")
    op.drop_column("certifications", "does_not_expire")
