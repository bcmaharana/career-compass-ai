"""jd tailoring

Revision ID: a2f7c48e91b3
Revises: f4b8c92e6a17
Create Date: 2026-08-19 12:00:00.000000

JD Tailoring: `jd_tailoring_sessions` (a real multi-turn AI conversation
grounded in one job description, scoped to a career profile — Master or
a Target Role Profile, target_role_id nullable ON DELETE SET NULL, same
precedent as learning_items/interview_topics) and
`jd_tailoring_messages` (its message thread — deliberately NOT built on
the existing chat_conversations/chat_messages tables, which are
hard-wired to one conversation per user; see
app/domain/jd_tailoring/entities.py's module docstring). Both
tenant-owned (RLS enabled+forced, exact-match policy).
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'a2f7c48e91b3'
down_revision: str | None = 'f4b8c92e6a17'
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table('jd_tailoring_sessions',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('tenant_id', sa.UUID(), nullable=False),
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('target_role_id', sa.UUID(), nullable=True),
    sa.Column('source_type', sa.String(length=20), nullable=False),
    sa.Column('source_provider_id', sa.String(length=255), nullable=True),
    sa.Column('source_title', sa.String(length=500), nullable=True),
    sa.Column('source_company', sa.String(length=255), nullable=True),
    sa.Column('source_redirect_url', sa.String(length=1000), nullable=True),
    sa.Column('jd_text', sa.Text(), nullable=False),
    sa.Column('tailored_resume_docx_key', sa.String(length=500), nullable=True),
    sa.Column('tailored_resume_pdf_key', sa.String(length=500), nullable=True),
    sa.Column('tailored_resume_content', sa.JSON(), nullable=True),
    sa.Column('tailored_resume_status', sa.String(length=20), nullable=True),
    sa.Column('tailored_resume_error', sa.Text(), nullable=True),
    sa.Column('tailored_resume_generated_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
    sa.CheckConstraint("source_type IN ('job_listing', 'custom')", name=op.f('ck_jd_tailoring_sessions_source_type')),
    sa.CheckConstraint("tailored_resume_status IS NULL OR tailored_resume_status IN ('generated', 'failed')", name=op.f('ck_jd_tailoring_sessions_tailored_resume_status')),
    sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], name=op.f('fk_jd_tailoring_sessions_tenant_id_tenants')),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_jd_tailoring_sessions_user_id_users')),
    sa.ForeignKeyConstraint(['target_role_id'], ['target_roles.id'], name=op.f('fk_jd_tailoring_sessions_target_role_id_target_roles'), ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_jd_tailoring_sessions'))
    )
    op.create_index(
        "ix_jd_tailoring_sessions_tenant_id_user_id",
        "jd_tailoring_sessions",
        ["tenant_id", "user_id"],
    )
    op.execute("ALTER TABLE jd_tailoring_sessions ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE jd_tailoring_sessions FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY tenant_isolation_policy ON jd_tailoring_sessions
            USING (tenant_id = current_setting('app.tenant_id', true)::uuid)
            WITH CHECK (tenant_id = current_setting('app.tenant_id', true)::uuid)
        """
    )

    op.create_table('jd_tailoring_messages',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('tenant_id', sa.UUID(), nullable=False),
    sa.Column('session_id', sa.UUID(), nullable=False),
    sa.Column('role', sa.String(length=20), nullable=False),
    sa.Column('content', sa.Text(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("role IN ('user', 'assistant')", name=op.f('ck_jd_tailoring_messages_role')),
    sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], name=op.f('fk_jd_tailoring_messages_tenant_id_tenants')),
    sa.ForeignKeyConstraint(['session_id'], ['jd_tailoring_sessions.id'], name=op.f('fk_jd_tailoring_messages_session_id_jd_tailoring_sessions')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_jd_tailoring_messages'))
    )
    op.create_index(
        "ix_jd_tailoring_messages_tenant_id_session_id",
        "jd_tailoring_messages",
        ["tenant_id", "session_id"],
    )
    op.execute("ALTER TABLE jd_tailoring_messages ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE jd_tailoring_messages FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY tenant_isolation_policy ON jd_tailoring_messages
            USING (tenant_id = current_setting('app.tenant_id', true)::uuid)
            WITH CHECK (tenant_id = current_setting('app.tenant_id', true)::uuid)
        """
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS tenant_isolation_policy ON jd_tailoring_messages")
    op.drop_index("ix_jd_tailoring_messages_tenant_id_session_id", table_name="jd_tailoring_messages")
    op.drop_table('jd_tailoring_messages')
    op.execute("DROP POLICY IF EXISTS tenant_isolation_policy ON jd_tailoring_sessions")
    op.drop_index("ix_jd_tailoring_sessions_tenant_id_user_id", table_name="jd_tailoring_sessions")
    op.drop_table('jd_tailoring_sessions')
