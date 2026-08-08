"""ai platform governance tables

Revision ID: bdc2e7597843
Revises: f7dad2fcdcc9
Create Date: 2026-07-28 15:17:50.245674

"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'bdc2e7597843'
down_revision: str | None = 'f7dad2fcdcc9'
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    # prompt_versions and model_versions are reference data (no
    # tenant_id), same shape as permissions/roles — no RLS.
    op.create_table('prompt_versions',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('name', sa.String(length=100), nullable=False),
    sa.Column('version', sa.Integer(), nullable=False),
    sa.Column('template', sa.Text(), nullable=False),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('owner', sa.String(length=255), nullable=False),
    sa.Column('approved_by', sa.String(length=255), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_prompt_versions'))
    )
    op.create_index(
        "ix_prompt_versions_name_status", "prompt_versions", ["name", "status"]
    )

    op.create_table('model_versions',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('provider', sa.String(length=50), nullable=False),
    sa.Column('model_name', sa.String(length=100), nullable=False),
    sa.Column('version', sa.String(length=50), nullable=False),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('cost_per_1k_tokens', sa.Numeric(10, 6), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_model_versions'))
    )
    op.create_index(
        "ix_model_versions_status", "model_versions", ["status"]
    )

    # ai_invocations is tenant-owned, RLS-enforced like every other
    # domain table — see multi-tenancy-design.md.
    op.create_table('ai_invocations',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('tenant_id', sa.UUID(), nullable=False),
    sa.Column('user_id', sa.UUID(), nullable=True),
    sa.Column('prompt_version_id', sa.UUID(), nullable=False),
    sa.Column('model_version_id', sa.UUID(), nullable=False),
    sa.Column('input_tokens', sa.Integer(), nullable=False),
    sa.Column('output_tokens', sa.Integer(), nullable=False),
    sa.Column('latency_ms', sa.Numeric(10, 2), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], name=op.f('fk_ai_invocations_tenant_id_tenants')),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_ai_invocations_user_id_users')),
    sa.ForeignKeyConstraint(['prompt_version_id'], ['prompt_versions.id'], name=op.f('fk_ai_invocations_prompt_version_id_prompt_versions')),
    sa.ForeignKeyConstraint(['model_version_id'], ['model_versions.id'], name=op.f('fk_ai_invocations_model_version_id_model_versions')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_ai_invocations'))
    )
    op.create_index(
        "ix_ai_invocations_tenant_id_created_at", "ai_invocations", ["tenant_id", "created_at"]
    )

    op.execute("ALTER TABLE ai_invocations ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE ai_invocations FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY tenant_isolation_policy ON ai_invocations
            USING (tenant_id = current_setting('app.tenant_id', true)::uuid)
            WITH CHECK (tenant_id = current_setting('app.tenant_id', true)::uuid)
        """
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS tenant_isolation_policy ON ai_invocations")
    op.drop_table('ai_invocations')
    op.drop_table('model_versions')
    op.drop_table('prompt_versions')
