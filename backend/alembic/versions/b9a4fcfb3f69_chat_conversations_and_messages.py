"""chat conversations and messages

Revision ID: b9a4fcfb3f69
Revises: 2be908e7e965
Create Date: 2026-07-25 00:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'b9a4fcfb3f69'
down_revision: str | None = '2be908e7e965'
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table('chat_conversations',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('tenant_id', sa.UUID(), nullable=False),
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], name=op.f('fk_chat_conversations_tenant_id_tenants')),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_chat_conversations_user_id_users')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_chat_conversations'))
    )
    op.create_table('chat_messages',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('tenant_id', sa.UUID(), nullable=False),
    sa.Column('conversation_id', sa.UUID(), nullable=False),
    sa.Column('role', sa.String(length=20), nullable=False),
    sa.Column('content', sa.Text(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['conversation_id'], ['chat_conversations.id'], name=op.f('fk_chat_messages_conversation_id_chat_conversations')),
    sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], name=op.f('fk_chat_messages_tenant_id_tenants')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_chat_messages'))
    )

    op.create_index(
        "ix_chat_conversations_tenant_id_user_id", "chat_conversations", ["tenant_id", "user_id"]
    )
    op.create_index(
        "ix_chat_messages_tenant_id_conversation_id",
        "chat_messages",
        ["tenant_id", "conversation_id"],
    )

    # --- Row-Level Security ---
    # Both tables are strictly tenant-owned (exact-match policy), same
    # shape as every other domain — see multi-tenancy-design.md.
    for table in ("chat_conversations", "chat_messages"):
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"""
            CREATE POLICY tenant_isolation_policy ON {table}
                USING (tenant_id = current_setting('app.tenant_id', true)::uuid)
                WITH CHECK (tenant_id = current_setting('app.tenant_id', true)::uuid)
            """
        )


def downgrade() -> None:
    for table in ("chat_conversations", "chat_messages"):
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation_policy ON {table}")

    op.drop_table('chat_messages')
    op.drop_table('chat_conversations')
