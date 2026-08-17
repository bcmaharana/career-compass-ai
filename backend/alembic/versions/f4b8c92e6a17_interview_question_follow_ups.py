"""interview question follow-ups

Revision ID: f4b8c92e6a17
Revises: d4a8f21e6c37
Create Date: 2026-08-17 20:00:00.000000

Adds the ability to attach follow-up question(s) to an Interview
Question, requested directly by the user. A follow-up is the SAME
InterviewQuestion row shape, not a separate entity — it gets a manual
answer, AI-suggested answer, and reference links for free — linked to
its parent via a new nullable, self-referential `parent_question_id`
(ON DELETE CASCADE: a follow-up has no independent meaning once its
parent is gone, unlike topic_id's SET NULL). Single level only
(enforced at the application layer, not the DB): a follow-up is never
itself scope-tagged (InterviewQuestionService never creates
InterviewQuestionScopeTagModel rows for one) and is never given its own
parent_question_id.

A follow-up's ordering among its siblings needs a plain per-row
`display_order` column (re-added here after the previous migration
dropped it from this table entirely) rather than the scope-tag-table
based ordering top-level questions use, since a follow-up isn't
scope-tagged at all — there's no per-scope list for it to have a
position within, just one flat list of siblings under the same parent.
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'f4b8c92e6a17'
down_revision: str | None = 'd4a8f21e6c37'
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        'interview_questions',
        sa.Column('parent_question_id', sa.UUID(), nullable=True),
    )
    op.add_column(
        'interview_questions',
        sa.Column('display_order', sa.Integer(), nullable=False, server_default='0'),
    )
    op.create_foreign_key(
        op.f('fk_interview_questions_parent_question_id_interview_questions'),
        'interview_questions', 'interview_questions',
        ['parent_question_id'], ['id'], ondelete='CASCADE',
    )
    op.create_index(
        "ix_interview_questions_parent_question_id",
        "interview_questions",
        ["parent_question_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_interview_questions_parent_question_id", table_name="interview_questions")
    op.drop_constraint(
        op.f('fk_interview_questions_parent_question_id_interview_questions'),
        'interview_questions', type_='foreignkey',
    )
    op.drop_column('interview_questions', 'display_order')
    op.drop_column('interview_questions', 'parent_question_id')
