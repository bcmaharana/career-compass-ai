"""target role profiles

Revision ID: f1a4c9e6b3d2
Revises: d92e6a4f1c78
Create Date: 2026-08-07 16:00:00.000000

Adds a nullable target_role_id FK to career_profiles so a user can have
one Master Profile (target_role_id IS NULL) plus up to 10 independent
Target Role Profiles (TargetRoleService.MAX_TARGET_ROLES), each with its
own Experience/Education/Certification/CareerHighlight/KeyAchievement/
CoreCompetencies/headline/summary — child tables need no schema change at
all, since they already scope via career_profile_id, and a Target Role
Profile is just another career_profiles row with its own children.

Two PARTIAL unique indexes, not one plain composite unique index: Postgres
treats NULLs as distinct from each other in a standard unique index, so a
single UNIQUE(tenant_id, user_id, target_role_id) would NOT stop a second
Master (target_role_id IS NULL) row per user. No backfill needed —
existing rows get target_role_id = NULL for free, which *is* "Master."
No RLS change needed (career_profiles already has FORCE ROW LEVEL SECURITY
with a tenant_id-only policy, unaffected by a new column).
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'f1a4c9e6b3d2'
down_revision: str | None = 'd92e6a4f1c78'
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column('career_profiles', sa.Column('target_role_id', sa.UUID(), nullable=True))
    op.create_foreign_key(
        op.f('fk_career_profiles_target_role_id_target_roles'),
        'career_profiles',
        'target_roles',
        ['target_role_id'],
        ['id'],
    )
    op.create_index(
        "uq_career_profiles_master_per_user",
        "career_profiles",
        ["tenant_id", "user_id"],
        unique=True,
        postgresql_where=sa.text("target_role_id IS NULL AND deleted_at IS NULL"),
    )
    op.create_index(
        "uq_career_profiles_target_role_per_user",
        "career_profiles",
        ["tenant_id", "user_id", "target_role_id"],
        unique=True,
        postgresql_where=sa.text("target_role_id IS NOT NULL AND deleted_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_career_profiles_target_role_per_user", table_name="career_profiles")
    op.drop_index("uq_career_profiles_master_per_user", table_name="career_profiles")
    op.drop_constraint(
        op.f('fk_career_profiles_target_role_id_target_roles'),
        'career_profiles',
        type_='foreignkey',
    )
    op.drop_column('career_profiles', 'target_role_id')
