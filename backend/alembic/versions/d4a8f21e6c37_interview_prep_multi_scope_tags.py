"""interview prep multi-scope tags

Revision ID: d4a8f21e6c37
Revises: c5e91b4f7a03
Create Date: 2026-08-17 12:00:00.000000

Replaces InterviewTopic/InterviewQuestion's single exclusive
`target_role_id` (Master vs one Target Role) with a proper many-to-many
scope tagging model, requested directly by the user: "Each question or
topic can be tagged with one or more roles... Correcting in one place
will update in others automatically." A tagged item is the SAME row
surfaced under every scope it's tagged to, not a copy.

Two new join tables, `interview_topic_scope_tags` /
`interview_question_scope_tags` — `target_role_id` nullable (NULL =
Master, matching the existing convention elsewhere in this app),
`ON DELETE CASCADE` on both the item FK and the target_role FK (deleting
a target role, or the item itself, just removes that one tag row — the
item persists under its remaining tags if any). Two partial unique
indexes (not one plain UNIQUE(item_id, target_role_id)) because
Postgres treats every NULL as distinct in a unique constraint, which
would silently allow duplicate "tagged to Master" rows for the same
item — one partial index handles the NOT NULL (real role) case, the
other the IS NULL (Master) case. `display_order` lives on the tag row,
not the item, since reordering is independent per scope (confirmed with
the user) — the same item can sit at a different position in each
scope's list.

Data is backfilled from each item's current `target_role_id`/
`display_order` into exactly one tag row before those columns are
dropped, so every existing item keeps its current single scope and
position as the starting point.
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'd4a8f21e6c37'
down_revision: str | None = 'c5e91b4f7a03'
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        'interview_topic_scope_tags',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('tenant_id', sa.UUID(), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('topic_id', sa.UUID(), nullable=False),
        sa.Column('target_role_id', sa.UUID(), nullable=True),
        sa.Column('display_order', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], name=op.f('fk_interview_topic_scope_tags_tenant_id_tenants')),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_interview_topic_scope_tags_user_id_users')),
        sa.ForeignKeyConstraint(['topic_id'], ['interview_topics.id'], name=op.f('fk_interview_topic_scope_tags_topic_id_interview_topics'), ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['target_role_id'], ['target_roles.id'], name=op.f('fk_interview_topic_scope_tags_target_role_id_target_roles'), ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_interview_topic_scope_tags')),
    )
    op.create_index(
        "uq_interview_topic_scope_tags_role",
        "interview_topic_scope_tags",
        ["topic_id", "target_role_id"],
        unique=True,
        postgresql_where=sa.text("target_role_id IS NOT NULL"),
    )
    op.create_index(
        "uq_interview_topic_scope_tags_master",
        "interview_topic_scope_tags",
        ["topic_id"],
        unique=True,
        postgresql_where=sa.text("target_role_id IS NULL"),
    )
    op.create_index(
        "ix_interview_topic_scope_tags_tenant_id",
        "interview_topic_scope_tags",
        ["tenant_id"],
    )
    # (user_id, target_role_id) is the exact filter next_display_order()/
    # move() use to find "this user's ordered list for this scope" —
    # denormalized here (rather than requiring a join back to
    # interview_topics for every such query) specifically so Master
    # (target_role_id IS NULL, which has no owning row of its own to key
    # off of) still scopes per-user instead of colliding every user's
    # Master-tagged topics into one shared ordering pool.
    op.create_index(
        "ix_interview_topic_scope_tags_user_id_target_role_id",
        "interview_topic_scope_tags",
        ["user_id", "target_role_id"],
    )

    op.create_table(
        'interview_question_scope_tags',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('tenant_id', sa.UUID(), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('question_id', sa.UUID(), nullable=False),
        sa.Column('target_role_id', sa.UUID(), nullable=True),
        sa.Column('display_order', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], name=op.f('fk_interview_question_scope_tags_tenant_id_tenants')),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_interview_question_scope_tags_user_id_users')),
        sa.ForeignKeyConstraint(['question_id'], ['interview_questions.id'], name=op.f('fk_interview_question_scope_tags_question_id_interview_questions'), ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['target_role_id'], ['target_roles.id'], name=op.f('fk_interview_question_scope_tags_target_role_id_target_roles'), ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_interview_question_scope_tags')),
    )
    op.create_index(
        "uq_interview_question_scope_tags_role",
        "interview_question_scope_tags",
        ["question_id", "target_role_id"],
        unique=True,
        postgresql_where=sa.text("target_role_id IS NOT NULL"),
    )
    op.create_index(
        "uq_interview_question_scope_tags_master",
        "interview_question_scope_tags",
        ["question_id"],
        unique=True,
        postgresql_where=sa.text("target_role_id IS NULL"),
    )
    op.create_index(
        "ix_interview_question_scope_tags_tenant_id",
        "interview_question_scope_tags",
        ["tenant_id"],
    )
    op.create_index(
        "ix_interview_question_scope_tags_user_id_target_role_id",
        "interview_question_scope_tags",
        ["user_id", "target_role_id"],
    )

    # Backfill: one tag row per existing item, carrying its current
    # target_role_id + display_order forward as the starting scope/
    # position, before those columns are dropped from the item tables
    # below. Runs before RLS is enabled on the new tables, so no
    # app.tenant_id session context is needed here.
    op.execute(
        """
        INSERT INTO interview_topic_scope_tags (id, tenant_id, user_id, topic_id, target_role_id, display_order)
        SELECT gen_random_uuid(), tenant_id, user_id, id, target_role_id, display_order
        FROM interview_topics
        """
    )
    op.execute(
        """
        INSERT INTO interview_question_scope_tags (id, tenant_id, user_id, question_id, target_role_id, display_order)
        SELECT gen_random_uuid(), tenant_id, user_id, id, target_role_id, display_order
        FROM interview_questions
        """
    )

    op.execute("ALTER TABLE interview_topic_scope_tags ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE interview_topic_scope_tags FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY tenant_isolation_policy ON interview_topic_scope_tags
            USING (tenant_id = current_setting('app.tenant_id', true)::uuid)
            WITH CHECK (tenant_id = current_setting('app.tenant_id', true)::uuid)
        """
    )
    op.execute("ALTER TABLE interview_question_scope_tags ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE interview_question_scope_tags FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY tenant_isolation_policy ON interview_question_scope_tags
            USING (tenant_id = current_setting('app.tenant_id', true)::uuid)
            WITH CHECK (tenant_id = current_setting('app.tenant_id', true)::uuid)
        """
    )

    # Scoping now lives entirely in the tag tables above.
    op.drop_constraint('fk_interview_topics_target_role_id_target_roles', 'interview_topics', type_='foreignkey')
    op.drop_column('interview_topics', 'target_role_id')
    op.drop_column('interview_topics', 'display_order')
    op.drop_constraint('fk_interview_questions_target_role_id_target_roles', 'interview_questions', type_='foreignkey')
    op.drop_column('interview_questions', 'target_role_id')
    op.drop_column('interview_questions', 'display_order')


def downgrade() -> None:
    op.add_column('interview_questions', sa.Column('display_order', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('interview_questions', sa.Column('target_role_id', sa.UUID(), nullable=True))
    op.create_foreign_key(
        op.f('fk_interview_questions_target_role_id_target_roles'),
        'interview_questions', 'target_roles', ['target_role_id'], ['id'], ondelete='SET NULL',
    )
    op.add_column('interview_topics', sa.Column('display_order', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('interview_topics', sa.Column('target_role_id', sa.UUID(), nullable=True))
    op.create_foreign_key(
        op.f('fk_interview_topics_target_role_id_target_roles'),
        'interview_topics', 'target_roles', ['target_role_id'], ['id'], ondelete='SET NULL',
    )

    # Lossy best-effort backfill: an item tagged to more than one scope
    # can only carry ONE value back into the old exclusive column, so
    # this picks an arbitrary tag (lowest id) per item — downgrading
    # after real multi-scope tagging has happened will not perfectly
    # round-trip, which is expected for a genuine model change.
    op.execute(
        """
        UPDATE interview_topics t
        SET target_role_id = s.target_role_id, display_order = s.display_order
        FROM (
            SELECT DISTINCT ON (topic_id) topic_id, target_role_id, display_order
            FROM interview_topic_scope_tags
            ORDER BY topic_id, id
        ) s
        WHERE t.id = s.topic_id
        """
    )
    op.execute(
        """
        UPDATE interview_questions q
        SET target_role_id = s.target_role_id, display_order = s.display_order
        FROM (
            SELECT DISTINCT ON (question_id) question_id, target_role_id, display_order
            FROM interview_question_scope_tags
            ORDER BY question_id, id
        ) s
        WHERE q.id = s.question_id
        """
    )

    op.execute("DROP POLICY IF EXISTS tenant_isolation_policy ON interview_question_scope_tags")
    op.drop_index("ix_interview_question_scope_tags_tenant_id", table_name="interview_question_scope_tags")
    op.drop_index("uq_interview_question_scope_tags_master", table_name="interview_question_scope_tags")
    op.drop_index("uq_interview_question_scope_tags_role", table_name="interview_question_scope_tags")
    op.drop_table('interview_question_scope_tags')

    op.execute("DROP POLICY IF EXISTS tenant_isolation_policy ON interview_topic_scope_tags")
    op.drop_index("ix_interview_topic_scope_tags_tenant_id", table_name="interview_topic_scope_tags")
    op.drop_index("uq_interview_topic_scope_tags_master", table_name="interview_topic_scope_tags")
    op.drop_index("uq_interview_topic_scope_tags_role", table_name="interview_topic_scope_tags")
    op.drop_table('interview_topic_scope_tags')
