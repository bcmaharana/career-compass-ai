"""certificate library assets and public links

Revision ID: c82f49d31a70
Revises: c4a7e2f91b6d
Create Date: 2026-10-21 10:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "c82f49d31a70"
down_revision: str | None = "c4a7e2f91b6d"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("certifications", sa.Column("certificate_file_key", sa.String(512)))
    op.add_column("certifications", sa.Column("certificate_file_name", sa.String(255)))
    op.add_column("certifications", sa.Column("certificate_file_content_type", sa.String(100)))
    op.add_column("certifications", sa.Column("badge_image_key", sa.String(512)))
    op.add_column("certifications", sa.Column("badge_image_name", sa.String(255)))
    op.add_column("certifications", sa.Column("badge_image_content_type", sa.String(100)))
    op.add_column("certifications", sa.Column("badge_url", sa.String(2048)))

    op.drop_constraint(
        op.f("ck_public_share_links_resource_type"), "public_share_links", type_="check"
    )
    op.create_check_constraint(
        op.f("ck_public_share_links_resource_type"),
        "public_share_links",
        "resource_type IN ('showcase_page', 'interview_topic', 'certification')",
    )

    # Target-role certificates remain attached to their role for resume
    # tailoring; create copies on each owner's Master Profile for the
    # shared certificate library.
    op.execute(
        """
        INSERT INTO career_profiles
            (id, tenant_id, user_id, current_version, core_competencies, target_role_id)
        SELECT gen_random_uuid(), target_profiles.tenant_id, target_profiles.user_id,
               1, '[]'::json, NULL
        FROM career_profiles AS target_profiles
        JOIN certifications AS certs
          ON certs.career_profile_id = target_profiles.id
         AND certs.deleted_at IS NULL
        WHERE target_profiles.target_role_id IS NOT NULL
          AND target_profiles.deleted_at IS NULL
          AND NOT EXISTS (
              SELECT 1
              FROM career_profiles AS master
              WHERE master.tenant_id = target_profiles.tenant_id
                AND master.user_id = target_profiles.user_id
                AND master.target_role_id IS NULL
                AND master.deleted_at IS NULL
          )
        GROUP BY target_profiles.tenant_id, target_profiles.user_id
        """
    )
    op.execute(
        """
        INSERT INTO certifications (
            id, tenant_id, career_profile_id, name, issuing_organization,
            issue_date, expiration_date, credential_id, credential_url,
            display_order, include_in_resume
        )
        SELECT gen_random_uuid(), source.tenant_id, master.id, source.name,
               source.issuing_organization, source.issue_date, source.expiration_date,
               source.credential_id, source.credential_url, source.display_order,
               source.include_in_resume
        FROM certifications AS source
        JOIN career_profiles AS role_profile
          ON role_profile.id = source.career_profile_id
         AND role_profile.target_role_id IS NOT NULL
         AND role_profile.deleted_at IS NULL
        JOIN career_profiles AS master
          ON master.tenant_id = role_profile.tenant_id
         AND master.user_id = role_profile.user_id
         AND master.target_role_id IS NULL
         AND master.deleted_at IS NULL
        WHERE source.deleted_at IS NULL
        """
    )


def downgrade() -> None:
    op.execute("DELETE FROM public_share_links WHERE resource_type = 'certification'")
    op.drop_constraint(
        op.f("ck_public_share_links_resource_type"), "public_share_links", type_="check"
    )
    op.create_check_constraint(
        op.f("ck_public_share_links_resource_type"),
        "public_share_links",
        "resource_type IN ('showcase_page', 'interview_topic')",
    )
    op.drop_column("certifications", "badge_url")
    op.drop_column("certifications", "badge_image_content_type")
    op.drop_column("certifications", "badge_image_name")
    op.drop_column("certifications", "badge_image_key")
    op.drop_column("certifications", "certificate_file_content_type")
    op.drop_column("certifications", "certificate_file_name")
    op.drop_column("certifications", "certificate_file_key")
