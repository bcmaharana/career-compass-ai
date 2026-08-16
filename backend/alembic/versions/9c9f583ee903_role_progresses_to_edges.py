"""role progresses to edges

Revision ID: 9c9f583ee903
Revises: c3aac483f98f
Create Date: 2026-08-15 00:10:00.000000

Career path (Phase 6, Opportunity Intelligence): a new Role-to-Role
directed edge on the existing CIKG graph. Global reference data (no
tenant_id/RLS), governed through the existing ContentRevisionService
(propose/approve, cycle-checked at approval) exactly like
prerequisite_of_edges/specializes_edges — no new governance mechanism,
just a new entity_type string ("edge:role_progresses_to").
"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '9c9f583ee903'
down_revision: str | None = 'c3aac483f98f'
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        'role_progresses_to_edges',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('source_role_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('cikg_roles.id'), nullable=False),
        sa.Column('target_role_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('cikg_roles.id'), nullable=False),
        sa.Column('content_status', sa.String(length=20), nullable=False, server_default='approved'),
        sa.Column('source_attribution', sa.String(length=255), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.CheckConstraint("content_status IN ('approved', 'deprecated')", name='status'),
        sa.CheckConstraint('source_role_id != target_role_id', name='no_self_loop'),
        sa.UniqueConstraint('source_role_id', 'target_role_id', name='uq_role_progresses_to_edges_pair'),
    )


def downgrade() -> None:
    op.drop_table('role_progresses_to_edges')
