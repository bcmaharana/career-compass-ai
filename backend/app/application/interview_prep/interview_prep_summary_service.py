"""Interview Prep cross-scope summary — how many topics/questions exist
per scope (Master + each Target Role), for the page's scope picker to
show real counts next to each option. Computed live from the existing
list_for_scope repository methods rather than a dedicated COUNT-only
query — same "live computation, no batch job" precedent as CIKG's
knowledge_quality_score, reasonable at this app's per-user data volumes
(a handful of topics/questions across at most MAX_TARGET_ROLES scopes).
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from app.application.career_profile.target_role_service import TargetRoleService
from app.domain.interview_prep.repositories import InterviewQuestionRepository, InterviewTopicRepository


@dataclass(slots=True)
class InterviewPrepScopeSummary:
    target_role_id: UUID | None
    role_name: str
    topic_count: int
    question_count: int


@dataclass(slots=True)
class InterviewPrepSummary:
    scopes: list[InterviewPrepScopeSummary]
    #: Distinct topics/questions across EVERY scope, not a sum of the
    #: per-scope counts above — a topic or question tagged into more
    #: than one scope (Master AND a Target Role, say) is the same row
    #: appearing in both scopes' own lists, so summing would double
    #: -count it. Deduplicated by id from the exact same per-scope
    #: fetches get_summary already does, no extra query.
    total_topic_count: int
    total_question_count: int


class InterviewPrepSummaryService:
    def __init__(
        self,
        topics: InterviewTopicRepository,
        questions: InterviewQuestionRepository,
        target_roles: TargetRoleService,
    ) -> None:
        self._topics = topics
        self._questions = questions
        self._target_roles = target_roles

    async def get_summary(self, *, tenant_id: UUID, user_id: UUID) -> InterviewPrepSummary:
        roles = await self._target_roles.list_for_current_user(
            tenant_id=tenant_id, user_id=user_id
        )
        scopes: list[tuple[UUID | None, str]] = [(None, "Master")] + [
            (role.id, role.role_name) for role in roles
        ]

        summaries: list[InterviewPrepScopeSummary] = []
        all_topic_ids: set[UUID] = set()
        all_question_ids: set[UUID] = set()
        for target_role_id, role_name in scopes:
            topic_list = await self._topics.list_for_scope(tenant_id, user_id, target_role_id)
            question_list = await self._questions.list_for_scope(tenant_id, user_id, target_role_id)
            all_topic_ids.update(topic.id for topic in topic_list)
            all_question_ids.update(question.id for question in question_list)
            # Only scopes with at least one artifact — an empty scope
            # would just be noise in a "what have I built so far" summary.
            if not topic_list and not question_list:
                continue
            summaries.append(
                InterviewPrepScopeSummary(
                    target_role_id=target_role_id,
                    role_name=role_name,
                    topic_count=len(topic_list),
                    question_count=len(question_list),
                )
            )
        return InterviewPrepSummary(
            scopes=summaries,
            total_topic_count=len(all_topic_ids),
            total_question_count=len(all_question_ids),
        )
