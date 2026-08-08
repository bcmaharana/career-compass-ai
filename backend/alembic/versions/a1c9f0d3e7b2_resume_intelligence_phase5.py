"""resume intelligence phase5

Revision ID: a1c9f0d3e7b2
Revises: e333def9cd81
Create Date: 2026-08-04 00:00:00.000000

Phase 5 per CLAUDE.md's roadmap: a single `resumes` table holding an
uploaded resume's private storage key, extracted plain text, and the
LLM's structured extraction result (`extracted_data` JSON) as a
reviewable draft. Tenant-owned like every other domain table (RLS
enabled+forced, exact-match policy). Not orderable (no display_order)
and write-once after creation (no update-triggering columns beyond
`updated_at`'s bookkeeping default).
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'a1c9f0d3e7b2'
down_revision: str | None = 'e333def9cd81'
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table('resumes',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('tenant_id', sa.UUID(), nullable=False),
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('original_filename', sa.String(length=255), nullable=False),
    sa.Column('file_key', sa.String(length=500), nullable=False),
    sa.Column('content_type', sa.String(length=120), nullable=False),
    sa.Column('file_size_bytes', sa.Integer(), nullable=False),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('raw_text', sa.Text(), nullable=True),
    sa.Column('extracted_data', sa.JSON(), nullable=True),
    sa.Column('error_message', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
    sa.CheckConstraint("status IN ('parsed', 'failed')", name=op.f('ck_resumes_status')),
    sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], name=op.f('fk_resumes_tenant_id_tenants')),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_resumes_user_id_users')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_resumes'))
    )

    op.create_index(
        "ix_resumes_tenant_id_user_id",
        "resumes",
        ["tenant_id", "user_id"],
    )

    op.execute("ALTER TABLE resumes ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE resumes FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY tenant_isolation_policy ON resumes
            USING (tenant_id = current_setting('app.tenant_id', true)::uuid)
            WITH CHECK (tenant_id = current_setting('app.tenant_id', true)::uuid)
        """
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS tenant_isolation_policy ON resumes")
    op.drop_index("ix_resumes_tenant_id_user_id", table_name="resumes")
    op.drop_table('resumes')
