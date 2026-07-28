"""add role tags and skill role tags plus user skill display order

Revision ID: ac9319012a74
Revises: 6d6de67904b2
Create Date: 2026-07-26 16:05:11.068333

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'ac9319012a74'
down_revision: str | None = '6d6de67904b2'
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table('role_tags',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('name', sa.String(length=255), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_role_tags'))
    )
    # Functional unique index rather than a plain unique constraint on
    # `name` — "Scrum Master" and "scrum master" must collide, since
    # role-tag matching against a target role's free-text role_name is
    # always case-insensitive (see RoleTagRepository.get_by_name).
    op.execute("CREATE UNIQUE INDEX ux_role_tags_name_lower ON role_tags (lower(name))")

    op.create_table('skill_role_tags',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('skill_id', sa.UUID(), nullable=False),
    sa.Column('role_tag_id', sa.UUID(), nullable=False),
    sa.ForeignKeyConstraint(['role_tag_id'], ['role_tags.id'], name=op.f('fk_skill_role_tags_role_tag_id_role_tags')),
    sa.ForeignKeyConstraint(['skill_id'], ['skills.id'], name=op.f('fk_skill_role_tags_skill_id_skills')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_skill_role_tags')),
    sa.UniqueConstraint('skill_id', 'role_tag_id', name=op.f('uq_skill_role_tags_skill_id'))
    )
    op.create_index("ix_skill_role_tags_role_tag_id", "skill_role_tags", ["role_tag_id"])

    # user_skills already exists (created in 6d6de67904b2) and is RLS-
    # forced, so the backfill UPDATE below must run with RLS disabled —
    # Alembic has no app.tenant_id session context, so a forced policy
    # would otherwise silently block the UPDATE across every tenant. See
    # CLAUDE.md's documented migration-backfill gotcha.
    op.add_column('user_skills', sa.Column('display_order', sa.Integer(), nullable=True))

    op.execute("ALTER TABLE user_skills DISABLE ROW LEVEL SECURITY")
    op.execute(
        """
        UPDATE user_skills
        SET display_order = sub.rn
        FROM (
            SELECT id, ROW_NUMBER() OVER (
                PARTITION BY tenant_id, user_id ORDER BY created_at
            ) - 1 AS rn
            FROM user_skills
        ) AS sub
        WHERE user_skills.id = sub.id
        """
    )
    op.execute("ALTER TABLE user_skills ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE user_skills FORCE ROW LEVEL SECURITY")

    op.alter_column('user_skills', 'display_order', nullable=False, server_default='0')


def downgrade() -> None:
    op.drop_column('user_skills', 'display_order')
    op.drop_index("ix_skill_role_tags_role_tag_id", table_name="skill_role_tags")
    op.drop_table('skill_role_tags')
    op.execute("DROP INDEX IF EXISTS ux_role_tags_name_lower")
    op.drop_table('role_tags')
