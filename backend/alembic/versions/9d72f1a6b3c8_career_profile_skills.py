"""Add the independent Career Profile Skills library."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "9d72f1a6b3c8"
down_revision: str | None = "c82f49d31a70"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "career_profile_skills",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("career_profile_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("issuing_organization", sa.String(length=255), nullable=False),
        sa.Column("issue_date", sa.Date(), nullable=True),
        sa.Column("expiration_date", sa.Date(), nullable=True),
        sa.Column("credential_id", sa.String(length=255), nullable=True),
        sa.Column("credential_url", sa.String(length=2048), nullable=True),
        sa.Column("skill_file_key", sa.String(length=512), nullable=True),
        sa.Column("skill_file_name", sa.String(length=255), nullable=True),
        sa.Column("skill_file_content_type", sa.String(length=100), nullable=True),
        sa.Column("badge_image_key", sa.String(length=512), nullable=True),
        sa.Column("badge_image_name", sa.String(length=255), nullable=True),
        sa.Column("badge_image_content_type", sa.String(length=100), nullable=True),
        sa.Column("badge_url", sa.String(length=2048), nullable=True),
        sa.Column("display_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("include_in_resume", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.ForeignKeyConstraint(
            ["career_profile_id"],
            ["career_profiles.id"],
            name=op.f("fk_career_profile_skills_career_profile_id_career_profiles"),
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"], ["tenants.id"], name=op.f("fk_career_profile_skills_tenant_id_tenants")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_career_profile_skills")),
    )
    op.create_index(
        "ix_career_profile_skills_tenant_id_career_profile_id",
        "career_profile_skills",
        ["tenant_id", "career_profile_id"],
    )
    op.create_index(
        "ix_career_profile_skills_career_profile_id_display_order",
        "career_profile_skills",
        ["career_profile_id", "display_order"],
    )
    op.execute("ALTER TABLE career_profile_skills ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE career_profile_skills FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY tenant_isolation_policy ON career_profile_skills
            USING (tenant_id = current_setting('app.tenant_id', true)::uuid)
            WITH CHECK (tenant_id = current_setting('app.tenant_id', true)::uuid)
        """
    )

    op.drop_constraint(
        op.f("ck_public_share_links_resource_type"), "public_share_links", type_="check"
    )
    op.create_check_constraint(
        op.f("ck_public_share_links_resource_type"),
        "public_share_links",
        "resource_type IN ('showcase_page', 'interview_topic', 'certification', 'profile_skill')",
    )


def downgrade() -> None:
    op.execute("DELETE FROM public_share_links WHERE resource_type = 'profile_skill'")
    op.drop_constraint(
        op.f("ck_public_share_links_resource_type"), "public_share_links", type_="check"
    )
    op.create_check_constraint(
        op.f("ck_public_share_links_resource_type"),
        "public_share_links",
        "resource_type IN ('showcase_page', 'interview_topic', 'certification')",
    )
    op.execute("DROP POLICY IF EXISTS tenant_isolation_policy ON career_profile_skills")
    op.drop_index(
        "ix_career_profile_skills_career_profile_id_display_order",
        table_name="career_profile_skills",
    )
    op.drop_index(
        "ix_career_profile_skills_tenant_id_career_profile_id",
        table_name="career_profile_skills",
    )
    op.drop_table("career_profile_skills")
