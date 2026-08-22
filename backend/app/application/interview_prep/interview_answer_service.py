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

from app.adapters.documents.rich_text_export import plain_text
from app.ai_platform.llm_service.service import LLMServiceInterface
from app.application.career_profile.career_profile_service import CareerProfileService
from app.application.career_profile.target_role_service import TargetRoleService
from app.core.exceptions import CareerCompassError, NotFoundError
from app.core.rich_text import sanitize_rich_text
from app.domain.interview_prep.entities import InterviewQuestion, InterviewTopic
from app.domain.interview_prep.repositories import InterviewQuestionRepository, InterviewTopicRepository

_USE_CASE = "interview_answer_generation"
_MAX_RESPONSE_TOKENS = 600


def _topic_notes_text(topic: InterviewTopic) -> str:
    """Flattens every rich_text column across a topic's blocks into plain
    text for LLM grounding — the block-based replacement for what used to
    be a single `topic.discussion` field (2026-08-24). Reuses
    ResumeExportService's own HTML-to-plain-text walker
    (app/adapters/documents/rich_text_export.py) rather than duplicating
    that logic; non-text column types (image/video/links) carry nothing
    meaningful to ground an answer in, so they're skipped."""
    texts = [
        plain_text(column.html)
        for block in topic.blocks
        for column in block.columns
        if column.type == "rich_text" and column.html
    ]
    return "\n".join(t for t in texts if t)


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

        # A follow-up isn't scope-tagged and has no topic_id of its own
        # (see app/domain/interview_prep/entities.py's InterviewQuestion
        # docstring) — ground it in its parent's scopes/topic instead of
        # its own (always empty) ones, so a follow-up under a
        # role-tagged question doesn't silently regress to generic
        # Master-profile grounding.
        grounding_source = question
        parent_question_text: str | None = None
        if question.parent_question_id is not None:
            parent = await self._questions.get_by_id(tenant_id, question.parent_question_id)
            if parent is not None:
                grounding_source = parent
                parent_question_text = parent.question
        parent_question_context = (
            f'This is a follow-up to the earlier question: "{parent_question_text}"\n\n'
            if parent_question_text
            else ""
        )

        # A question can now be tagged to more than one scope — ground
        # against the first real Target Role it's tagged to (in tag
        # order, i.e. whichever was added first), falling back to the
        # Master profile if it's only tagged to Master (or has no real
        # role tags at all). Blending context from every tagged role
        # would be more "complete" but adds real complexity for a
        # single generated answer that doesn't need it.
        target_role_id = next(
            (rid for rid in grounding_source.scope_target_role_ids if rid is not None), None
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
        if grounding_source.topic_id is not None:
            topic = await self._topics.get_by_id(tenant_id, grounding_source.topic_id)
            if topic is not None:
                notes = _topic_notes_text(topic)
                if notes:
                    topic_context = f"Notes on this topic from the candidate's own prep:\n{notes}\n"

        try:
            answer = await self._llm.generate(
                use_case=_USE_CASE,
                input_variables={
                    "question": question.question,
                    "role_context": role_context,
                    "profile_context": profile_context,
                    "topic_context": topic_context,
                    "parent_question_context": parent_question_context,
                },
                tenant_id=tenant_id,
                user_id=user_id,
                max_tokens=_MAX_RESPONSE_TOKENS,
                temperature=0.4,
            )
            # Sanitized like every other rich-text-adjacent field in this
            # domain (manual_answer, discussion) even though this field is
            # rendered as plain text today, not through RichTextDisplay —
            # defense-in-depth against the day someone adds formatting
            # support here too and forgets this is the one field in the
            # domain that was never sanitized on write.
            question.ai_answer = sanitize_rich_text(answer.strip())
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
