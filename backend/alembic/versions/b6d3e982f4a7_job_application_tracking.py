"""job application tracking

Revision ID: b6d3e982f4a7
Revises: a2f7c48e91b3
Create Date: 2026-08-19 12:05:00.000000

Job Application Tracking: `recruiter_contacts` (a standalone, reusable
address book — created first so job_applications.recruiter_id can FK
it), `job_applications` (flat, user_id-scoped like learning_items, not
career_profile_id — a job application is for one real job at one
company, not "for" a profile; fixed status pipeline; snapshots the
source Adzuna listing's fields since job_listing_cache has no stable
per-listing row to FK against), and `interview_rounds` (a structured,
independently-reorderable one-to-many child of job_applications — no
ON DELETE CASCADE, same "explicit cleanup in account_deletion.py"
convention as jd_tailoring_messages/chat_messages). All three
tenant-owned (RLS enabled+forced, exact-match policy).
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'b6d3e982f4a7'
down_revision: str | None = 'a2f7c48e91b3'
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table('recruiter_contacts',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('tenant_id', sa.UUID(), nullable=False),
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('name', sa.String(length=255), nullable=False),
    sa.Column('email', sa.String(length=255), nullable=True),
    sa.Column('phone', sa.String(length=50), nullable=True),
    sa.Column('company', sa.String(length=255), nullable=True),
    sa.Column('linkedin_url', sa.String(length=500), nullable=True),
    sa.Column('role_title', sa.String(length=255), nullable=True),
    sa.Column('contact_history', sa.JSON(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], name=op.f('fk_recruiter_contacts_tenant_id_tenants')),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_recruiter_contacts_user_id_users')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_recruiter_contacts'))
    )
    op.create_index(
        "ix_recruiter_contacts_tenant_id_user_id",
        "recruiter_contacts",
        ["tenant_id", "user_id"],
    )
    op.execute("ALTER TABLE recruiter_contacts ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE recruiter_contacts FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY tenant_isolation_policy ON recruiter_contacts
            USING (tenant_id = current_setting('app.tenant_id', true)::uuid)
            WITH CHECK (tenant_id = current_setting('app.tenant_id', true)::uuid)
        """
    )

    op.create_table('job_applications',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('tenant_id', sa.UUID(), nullable=False),
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('target_role_id', sa.UUID(), nullable=True),
    sa.Column('company', sa.String(length=255), nullable=False),
    sa.Column('role_title', sa.String(length=255), nullable=False),
    sa.Column('status', sa.String(length=30), nullable=False, server_default='considering'),
    sa.Column('status_changed_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('source_provider_id', sa.String(length=255), nullable=True),
    sa.Column('source_title', sa.String(length=500), nullable=True),
    sa.Column('source_company', sa.String(length=255), nullable=True),
    sa.Column('source_redirect_url', sa.String(length=1000), nullable=True),
    sa.Column('jd_tailoring_session_id', sa.UUID(), nullable=True),
    sa.Column('recruiter_id', sa.UUID(), nullable=True),
    sa.Column('applied_at', sa.Date(), nullable=True),
    sa.Column('notes', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
    sa.CheckConstraint(
        "status IN ('considering', 'applied', 'phone_screen', 'interview', 'offer', "
        "'rejected', 'withdrawn', 'didnt_hear_back', 'other')",
        name=op.f('ck_job_applications_status'),
    ),
    sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], name=op.f('fk_job_applications_tenant_id_tenants')),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_job_applications_user_id_users')),
    sa.ForeignKeyConstraint(['target_role_id'], ['target_roles.id'], name=op.f('fk_job_applications_target_role_id_target_roles'), ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['jd_tailoring_session_id'], ['jd_tailoring_sessions.id'], name=op.f('fk_job_applications_jd_tailoring_session_id_jd_tailoring_sessions'), ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['recruiter_id'], ['recruiter_contacts.id'], name=op.f('fk_job_applications_recruiter_id_recruiter_contacts'), ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_job_applications'))
    )
    op.create_index(
        "ix_job_applications_tenant_id_user_id",
        "job_applications",
        ["tenant_id", "user_id"],
    )
    op.create_index(
        "ix_job_applications_tenant_id_source_provider_id",
        "job_applications",
        ["tenant_id", "source_provider_id"],
    )
    op.execute("ALTER TABLE job_applications ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE job_applications FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY tenant_isolation_policy ON job_applications
            USING (tenant_id = current_setting('app.tenant_id', true)::uuid)
            WITH CHECK (tenant_id = current_setting('app.tenant_id', true)::uuid)
        """
    )

    op.create_table('interview_rounds',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('tenant_id', sa.UUID(), nullable=False),
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('job_application_id', sa.UUID(), nullable=False),
    sa.Column('stage_label', sa.String(length=255), nullable=False),
    sa.Column('display_order', sa.Integer(), nullable=False),
    sa.Column('round_date', sa.Date(), nullable=True),
    sa.Column('interviewer_name', sa.String(length=255), nullable=True),
    sa.Column('interviewer_title', sa.String(length=255), nullable=True),
    sa.Column('notes', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], name=op.f('fk_interview_rounds_tenant_id_tenants')),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_interview_rounds_user_id_users')),
    sa.ForeignKeyConstraint(['job_application_id'], ['job_applications.id'], name=op.f('fk_interview_rounds_job_application_id_job_applications')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_interview_rounds'))
    )
    op.create_index(
        "ix_interview_rounds_tenant_id_user_id",
        "interview_rounds",
        ["tenant_id", "user_id"],
    )
    op.execute("ALTER TABLE interview_rounds ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE interview_rounds FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY tenant_isolation_policy ON interview_rounds
            USING (tenant_id = current_setting('app.tenant_id', true)::uuid)
            WITH CHECK (tenant_id = current_setting('app.tenant_id', true)::uuid)
        """
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS tenant_isolation_policy ON interview_rounds")
    op.drop_index("ix_interview_rounds_tenant_id_user_id", table_name="interview_rounds")
    op.drop_table('interview_rounds')
    op.execute("DROP POLICY IF EXISTS tenant_isolation_policy ON job_applications")
    op.drop_index("ix_job_applications_tenant_id_source_provider_id", table_name="job_applications")
    op.drop_index("ix_job_applications_tenant_id_user_id", table_name="job_applications")
    op.drop_table('job_applications')
    op.execute("DROP POLICY IF EXISTS tenant_isolation_policy ON recruiter_contacts")
    op.drop_index("ix_recruiter_contacts_tenant_id_user_id", table_name="recruiter_contacts")
    op.drop_table('recruiter_contacts')
