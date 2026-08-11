"""terms of service acceptance

Revision ID: d4a7f2c9b6e1
Revises: 9b2d5a7c1e4f
Create Date: 2026-08-11 00:00:00.000000

Records real Terms of Service / Privacy Policy consent, not just a
client-side checkbox — see app/domain/identity/legal_terms.py and
PersonalSignupRequest/OrganizationSignupRequest's new agreed_to_terms
field.

`pending_signups` gets NOT NULL columns (a signup request can't be
created without agreeing at all going forward) — the server_default is
only a safety net for any genuinely in-flight row at migration time,
not something new application code relies on; every real INSERT after
this migration provides real values explicitly.

`users` gets nullable columns, deliberately not backfilled — an
account created before this feature existed never actually saw these
documents, so recording a fabricated acceptance timestamp for it would
be dishonest, not merely an oversight.
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'd4a7f2c9b6e1'
down_revision: str | None = '9b2d5a7c1e4f'
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        'pending_signups',
        sa.Column(
            'agreed_to_terms_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('now()'),
            nullable=False,
        ),
    )
    op.add_column(
        'pending_signups',
        sa.Column(
            'terms_version',
            sa.String(length=20),
            server_default='pre-2026-08-11',
            nullable=False,
        ),
    )
    op.alter_column('pending_signups', 'agreed_to_terms_at', server_default=None)
    op.alter_column('pending_signups', 'terms_version', server_default=None)

    op.add_column(
        'users', sa.Column('agreed_to_terms_at', sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column(
        'users', sa.Column('terms_version', sa.String(length=20), nullable=True)
    )


def downgrade() -> None:
    op.drop_column('users', 'terms_version')
    op.drop_column('users', 'agreed_to_terms_at')
    op.drop_column('pending_signups', 'terms_version')
    op.drop_column('pending_signups', 'agreed_to_terms_at')
