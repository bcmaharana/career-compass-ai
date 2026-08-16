"""AI-generated interview answers.

Read-only, regenerate-only by design (confirmed with the user): this
service only ever fires on an explicit "Generate"/"Regenerate" action,
never automatically, and the result isn't user-editable — a fresh call
is the only way to get different wording. Grounded in whatever real
context is available (target role name, profile headline/core
competencies, and the linked topic's own discussion notes, if any) —
same "AI output should draw on real data, not answer in a vacuum"
convention LearningRecommendationService/CoachPage's suggested prompts
already established. Degrade-gracefully choice: persist a
status="failed" row with error_message (Resume Intelligence's/Learning
Recommendations' pattern) rather than leave the field untouched — but
unlike a fresh generate, a failed *regenerate* attempt does not blow
away a previous good answer, so the user doesn't lose a working answer
just because a retry happened to fail.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from app.ai_platform.llm_service.service import LLMServiceInterface
from app.application.career_profile.career_profile_service import CareerProfileService
from app.application.career_profile.target_role_service import TargetRoleService
from app.core.exceptions import CareerCompassError, NotFoundError
from app.domain.interview_prep.entities import InterviewQuestion
from app.domain.interview_prep.repositories import InterviewQuestionRepository, InterviewTopicRepository

_USE_CASE = "interview_answer_generation"
_MAX_RESPONSE_TOKENS = 600


class InterviewAnswerService:
    def __init__(
        self,
        questions: InterviewQuestionRepository,
        topics: InterviewTopicRepository,
        career_profile: CareerProfileService,
        target_roles: TargetRoleService,
        llm: LLMServiceInterface,
    ) -> None:
        self._questions = questions
        self._topics = topics
        self._career_profile = career_profile
        self._target_roles = target_roles
        self._llm = llm

    async def generate_answer(
        self, *, tenant_id: UUID, user_id: UUID, question_id: UUID
    ) -> InterviewQuestion:
        question = await self._questions.get_by_id(tenant_id, question_id)
        if question is None or question.user_id != user_id:
            raise NotFoundError(
                "Interview question not found.", code="INTERVIEW_QUESTION_NOT_FOUND"
            )

        # A question can now be tagged to more than one scope — ground
        # against the first real Target Role it's tagged to (in tag
        # order, i.e. whichever was added first), falling back to the
        # Master profile if it's only tagged to Master (or has no real
        # role tags at all). Blending context from every tagged role
        # would be more "complete" but adds real complexity for a
        # single generated answer that doesn't need it.
        target_role_id = next(
            (rid for rid in question.scope_target_role_ids if rid is not None), None
        )
        role_context = ""
        if target_role_id is not None:
            role = await self._target_roles.get_owned_or_raise(
                tenant_id=tenant_id, user_id=user_id, target_role_id=target_role_id
            )
            role_context = f" for the \"{role.role_name}\" role"

        profile = await self._career_profile.get_or_create(
            tenant_id=tenant_id, user_id=user_id, target_role_id=target_role_id
        )
        profile_lines: list[str] = []
        if profile.headline:
            profile_lines.append(f"Headline: {profile.headline}")
        competency_names = [c.name for c in profile.core_competencies]
        if competency_names:
            profile_lines.append(f"Key skills/competencies: {', '.join(competency_names)}")
        profile_context = (
            f"Candidate background:\n{chr(10).join(profile_lines)}\n" if profile_lines else ""
        )

        topic_context = ""
        if question.topic_id is not None:
            topic = await self._topics.get_by_id(tenant_id, question.topic_id)
            if topic is not None and topic.discussion:
                topic_context = f"Notes on this topic from the candidate's own prep:\n{topic.discussion}\n"

        try:
            answer = await self._llm.generate(
                use_case=_USE_CASE,
                input_variables={
                    "question": question.question,
                    "role_context": role_context,
                    "profile_context": profile_context,
                    "topic_context": topic_context,
                },
                tenant_id=tenant_id,
                user_id=user_id,
                max_tokens=_MAX_RESPONSE_TOKENS,
                temperature=0.4,
            )
            question.ai_answer = answer.strip()
            question.ai_answer_status = "generated"
            question.ai_answer_error = None
        except CareerCompassError as exc:
            # A failed regenerate doesn't erase a previously-good answer
            # — only the status/error fields change, ai_answer is left
            # exactly as it was.
            question.ai_answer_status = "failed"
            question.ai_answer_error = str(exc)

        question.ai_answer_generated_at = datetime.now(UTC)
        return await self._questions.update(question)
