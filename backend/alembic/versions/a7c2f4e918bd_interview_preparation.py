"""interview preparation

Revision ID: a7c2f4e918bd
Revises: 9f8c93952d56
Create Date: 2026-08-16 09:00:00.000000

Interview Preparation: `interview_topics` (study-notes cards, optionally
grouped by a free-text `section` label, optional private-bucket image)
and `interview_questions` (a question, the user's own answer, an
AI-generated answer, labeled reference links, and an optional link into
one of this scope's topics). Both scoped directly by user_id and
optionally tied to a Target Role (target_role_id nullable, ON DELETE SET
NULL — same precedent as learning_items), tenant-owned like every other
domain table (RLS enabled+forced, exact-match policy).
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'a7c2f4e918bd'
down_revision: str | None = '9f8c93952d56'
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table('interview_topics',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('tenant_id', sa.UUID(), nullable=False),
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('target_role_id', sa.UUID(), nullable=True),
    sa.Column('name', sa.String(length=255), nullable=False),
    sa.Column('section', sa.String(length=255), nullable=True),
    sa.Column('discussion', sa.Text(), nullable=True),
    sa.Column('image_key', sa.String(length=500), nullable=True),
    sa.Column('display_order', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], name=op.f('fk_interview_topics_tenant_id_tenants')),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_interview_topics_user_id_users')),
    sa.ForeignKeyConstraint(['target_role_id'], ['target_roles.id'], name=op.f('fk_interview_topics_target_role_id_target_roles'), ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_interview_topics'))
    )
    op.create_index(
        "ix_interview_topics_tenant_id_user_id",
        "interview_topics",
        ["tenant_id", "user_id"],
    )
    op.execute("ALTER TABLE interview_topics ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE interview_topics FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY tenant_isolation_policy ON interview_topics
            USING (tenant_id = current_setting('app.tenant_id', true)::uuid)
            WITH CHECK (tenant_id = current_setting('app.tenant_id', true)::uuid)
        """
    )

    op.create_table('interview_questions',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('tenant_id', sa.UUID(), nullable=False),
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('target_role_id', sa.UUID(), nullable=True),
    sa.Column('topic_id', sa.UUID(), nullable=True),
    sa.Column('question', sa.Text(), nullable=False),
    sa.Column('manual_answer', sa.Text(), nullable=True),
    sa.Column('ai_answer', sa.Text(), nullable=True),
    sa.Column('ai_answer_status', sa.String(length=20), nullable=True),
    sa.Column('ai_answer_error', sa.Text(), nullable=True),
    sa.Column('ai_answer_generated_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('reference_links', sa.JSON(), nullable=False),
    sa.Column('display_order', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
    sa.CheckConstraint("ai_answer_status IS NULL OR ai_answer_status IN ('generated', 'failed')", name=op.f('ck_interview_questions_ai_answer_status')),
    sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], name=op.f('fk_interview_questions_tenant_id_tenants')),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_interview_questions_user_id_users')),
    sa.ForeignKeyConstraint(['target_role_id'], ['target_roles.id'], name=op.f('fk_interview_questions_target_role_id_target_roles'), ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['topic_id'], ['interview_topics.id'], name=op.f('fk_interview_questions_topic_id_interview_topics'), ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_interview_questions'))
    )
    op.create_index(
        "ix_interview_questions_tenant_id_user_id",
        "interview_questions",
        ["tenant_id", "user_id"],
    )
    op.execute("ALTER TABLE interview_questions ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE interview_questions FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY tenant_isolation_policy ON interview_questions
            USING (tenant_id = current_setting('app.tenant_id', true)::uuid)
            WITH CHECK (tenant_id = current_setting('app.tenant_id', true)::uuid)
        """
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS tenant_isolation_policy ON interview_questions")
    op.drop_index("ix_interview_questions_tenant_id_user_id", table_name="interview_questions")
    op.drop_table('interview_questions')
    op.execute("DROP POLICY IF EXISTS tenant_isolation_policy ON interview_topics")
    op.drop_index("ix_interview_topics_tenant_id_user_id", table_name="interview_topics")
    op.drop_table('interview_topics')
