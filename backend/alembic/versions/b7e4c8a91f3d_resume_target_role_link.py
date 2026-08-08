"""resume target role link

Revision ID: b7e4c8a91f3d
Revises: a1c9f0d3e7b2
Create Date: 2026-08-04 21:40:00.000000

Adds a nullable target_role_id FK to resumes so a person can keep
multiple resume versions, each tailored to a different TargetRole —
part of moving Resume Intelligence from a single-superseded-slot model
to a real upload history (see the "Also removes soft_delete_all_for_user"
note in resume_intelligence.py's application-layer changes; this
migration is the schema half of that change).
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'b7e4c8a91f3d'
down_revision: str | None = 'a1c9f0d3e7b2'
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column('resumes', sa.Column('target_role_id', sa.UUID(), nullable=True))
    op.create_foreign_key(
        op.f('fk_resumes_target_role_id_target_roles'),
        'resumes',
        'target_roles',
        ['target_role_id'],
        ['id'],
    )
    op.create_index(
        "ix_resumes_tenant_id_target_role_id",
        "resumes",
        ["tenant_id", "target_role_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_resumes_tenant_id_target_role_id", table_name="resumes")
    op.drop_constraint(
        op.f('fk_resumes_target_role_id_target_roles'), 'resumes', type_='foreignkey'
    )
    op.drop_column('resumes', 'target_role_id')
