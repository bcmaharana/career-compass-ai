"""public sharing: showcase pages, public articles, user handle

Revision ID: ee3d0b0ddfe8
Revises: e1f805b1a80c
Create Date: 2026-08-22 00:00:00.000000

Public profile sharing (direct 2026-08-22 request): a per-Target-Role
"Showcase Page" (a freeform, block-based document — NOT the profile made
public, a distinct editable page seeded once from the tailored resume)
and the existing Interview Prep Topic gaining a public/private toggle
("Article" when framed externally, same entity internally).

`public_share_links` is the RLS-exempt cross-tenant lookup this whole
feature turns on — same "must be resolvable before any tenant context
exists" reasoning as `personal_phone_logins`/`password_reset_tokens`, just
for anonymous content viewing instead of login. Every tenant-owned table
(`showcase_pages`, `interview_topics`) is FORCE ROW LEVEL SECURITY, and
`current_setting('app.tenant_id', true)` is NULL until a request
explicitly binds a tenant_id — which an anonymous request has no JWT to
derive one from. The anonymous read path looks up `share_key` here first
(no tenant context needed for this table), learns `tenant_id`, binds it via
TenantContextBinder, and only then queries the real, RLS-protected row.
`UNIQUE (resource_type, resource_id)` guarantees a resource is only ever
issued one key for its whole lifetime, so toggling public -> private ->
public again reuses the exact same URL (direct requirement) rather than
minting a new one.

`showcase_pages.target_role_id` is UNIQUE (one page per target role,
direct requirement) with ON DELETE CASCADE — a showcase page has no
meaning once its target role is gone. `blocks` is a single JSONB column,
not a separate child table: the block list is small, bounded, and freely
reordered as a whole, the same "whole list as one JSON blob, replaced
atomically" shape `career_profiles.core_competencies`/
`resume_section_toggles` already use, not the heavier per-row-with-move()
pattern Experience/Education use — reordering is just rewriting array
order in one UPDATE, no separate reorder endpoint needed.

`interview_topics.is_public` is the only new column there — no separate
`public_share_key` column on the topic itself, since it goes through the
same shared `public_share_links` table as showcase pages (`resource_type
= 'interview_topic'`), one lookup mechanism for both content types.

`users.middle_name` is a genuinely new field, added because the agreed
default-handle rule (First/Middle/Last initials, "0" if no middle name)
assumes one exists to check — this app never collected it before.
`users.handle` is the reserved, globally-unique (case-insensitive) short
public identifier used as the first URL path segment
(scaledbrain.com/{handle}/{role_tag}/{key}) — nullable (not every user
will set one immediately; computed lazily by the application layer, not
backfilled here), with a partial functional unique index on `lower(handle)`
so `NULL` handles (arbitrarily many) never collide with each other,
Postgres correctly treating every NULL as distinct.
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'ee3d0b0ddfe8'
down_revision: str | None = 'e1f805b1a80c'
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table('public_share_links',
    sa.Column('share_key', sa.String(length=64), nullable=False),
    sa.Column('tenant_id', sa.UUID(), nullable=False),
    sa.Column('resource_type', sa.String(length=20), nullable=False),
    sa.Column('resource_id', sa.UUID(), nullable=False),
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint(
        "resource_type IN ('showcase_page', 'interview_topic')",
        name=op.f('ck_public_share_links_resource_type'),
    ),
    sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], name=op.f('fk_public_share_links_tenant_id_tenants')),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_public_share_links_user_id_users')),
    sa.PrimaryKeyConstraint('share_key', name=op.f('pk_public_share_links')),
    sa.UniqueConstraint('resource_type', 'resource_id', name=op.f('uq_public_share_links_resource_type_resource_id'))
    )
    # No ENABLE/FORCE ROW LEVEL SECURITY / CREATE POLICY here — see the
    # module docstring above. Deliberate, not an oversight.

    op.create_table('showcase_pages',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('tenant_id', sa.UUID(), nullable=False),
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('target_role_id', sa.UUID(), nullable=False),
    sa.Column('is_public', sa.Boolean(), nullable=False, server_default='false'),
    sa.Column('blocks', sa.JSON(), nullable=False, server_default='[]'),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], name=op.f('fk_showcase_pages_tenant_id_tenants')),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_showcase_pages_user_id_users')),
    sa.ForeignKeyConstraint(['target_role_id'], ['target_roles.id'], name=op.f('fk_showcase_pages_target_role_id_target_roles'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_showcase_pages')),
    sa.UniqueConstraint('target_role_id', name=op.f('uq_showcase_pages_target_role_id'))
    )
    op.create_index(
        "ix_showcase_pages_tenant_id_user_id",
        "showcase_pages",
        ["tenant_id", "user_id"],
    )
    op.execute("ALTER TABLE showcase_pages ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE showcase_pages FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY tenant_isolation_policy ON showcase_pages
            USING (tenant_id = current_setting('app.tenant_id', true)::uuid)
            WITH CHECK (tenant_id = current_setting('app.tenant_id', true)::uuid)
        """
    )

    op.add_column('interview_topics', sa.Column('is_public', sa.Boolean(), nullable=False, server_default='false'))

    op.add_column('users', sa.Column('middle_name', sa.String(length=150), nullable=True))
    op.add_column('users', sa.Column('handle', sa.String(length=32), nullable=True))
    op.execute(
        "CREATE UNIQUE INDEX uq_users_handle_lower ON users (lower(handle)) WHERE handle IS NOT NULL"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_users_handle_lower")
    op.drop_column('users', 'handle')
    op.drop_column('users', 'middle_name')

    op.drop_column('interview_topics', 'is_public')

    op.execute("DROP POLICY IF EXISTS tenant_isolation_policy ON showcase_pages")
    op.drop_index("ix_showcase_pages_tenant_id_user_id", table_name="showcase_pages")
    op.drop_table('showcase_pages')

    op.drop_table('public_share_links')
