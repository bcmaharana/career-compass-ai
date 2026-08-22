"""chat conversation section_key

Revision ID: e1f805b1a80c
Revises: b6d3e982f4a7
Create Date: 2026-08-22 01:00:00.000000

Real live production issue, caught within hours of the previous session's
"AI chat conversation-management parity" deploy: that change made the
footer's persistent AI Chat conversation survive navigation instead of
resetting per Left Nav section, but this app only ever had ONE
conversation per account (the "only one in practice" design chat-store.ts
has documented since Phase 0) — so surviving navigation meant the exact
same conversation, and its message history, followed the user onto every
unrelated page. Direct correction: "the conversation was for that page
only... not to be displayed in any other page."

`section_key` scopes a conversation to exactly one top-level section (the
same `matchNavItem(pathname).to` value this app already uses everywhere
else to identify a section, e.g. "/dashboard", "/profile", "/coach") — a
user now has at most one "current" conversation per section, not one per
account. `server_default=''` rather than backfilling: there is no
retroactive way to know which section an existing conversation's messages
were "for," since that was never tracked before this column existed —
those rows simply stop being resolvable as any section's "latest"
conversation going forward, the same "honestly left unset rather than
fabricating history" precedent `agreed_to_terms_at` already established
for pre-existing accounts.
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'e1f805b1a80c'
down_revision: str | None = 'b6d3e982f4a7'
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        'chat_conversations',
        sa.Column('section_key', sa.String(length=100), nullable=False, server_default=''),
    )
    op.create_index(
        "ix_chat_conversations_tenant_id_user_id_section_key",
        "chat_conversations",
        ["tenant_id", "user_id", "section_key"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_chat_conversations_tenant_id_user_id_section_key",
        table_name="chat_conversations",
    )
    op.drop_column('chat_conversations', 'section_key')
