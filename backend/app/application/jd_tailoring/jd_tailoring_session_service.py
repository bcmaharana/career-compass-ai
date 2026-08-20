"""JD Tailoring session + multi-turn chat.

A real, per-JD multi-turn conversation, deliberately NOT built on the
existing Chat domain (app/domain/chat/) — see
app/domain/jd_tailoring/entities.py's module docstring for why. Reuses
ChatService.send_message()'s exact pattern (load history, persist user
message, render history+context into the prompt, call LLMService,
degrade gracefully on failure, persist+return the reply) rather than
its tables.

Grounding mirrors InterviewAnswerService's profile_context construction
(headline + core competency names, empty string when absent — the
template never branches on presence/absence).
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from app.adapters.documents.resume_data import ResumeData, education_degree_line, format_date_range
from app.adapters.documents.rich_text_export import plain_text
from app.ai_platform.llm_service.service import LLMServiceInterface
from app.application.career_profile.resume_export_service import ResumeExportService
from app.core.exceptions import CareerCompassError, NotFoundError
from app.core.logging import get_logger
from app.domain.jd_tailoring.entities import (
    JdTailoringMessage,
    JdTailoringMessageRole,
    JdTailoringSession,
)
from app.domain.jd_tailoring.repositories import (
    JdTailoringMessageRepository,
    JdTailoringSessionRepository,
)

logger = get_logger(__name__)

_USE_CASE = "jd_tailoring_chat"
_MAX_HISTORY_MESSAGES = 20
_MAX_RESPONSE_TOKENS = 1000

_FALLBACK_REPLY = (
    "I'm having trouble reaching the AI right now — please try again in a moment. "
    "Your message has been saved."
)

#: The prompt instructs plain text — no markdown headers/bold/tables
#: (see JD_TAILORING_CHAT_PROMPT_TEMPLATE's "Formatting rules") — but
#: the model doesn't reliably comply. Confirmed live (2026-08-19): a
#: real reply correctly dropped ** bold and table syntax but still
#: emitted a literal "### Gaps you should watch for" section header
#: mid-response, and an earlier real user report showed a reply with
#: full markdown headers/bold/a table. Since this reply renders as
#: plain text (MessageBubble in JdTailoringPage.tsx has no markdown
#: renderer), any markdown syntax that slips through shows up as raw,
#: ugly punctuation rather than formatting — same
#: don't-trust-instruction-compliance-alone lesson as
#: tailored_resume_service.py's _normalize_llm_text/bullet-prefix
#: stripping, applied here to the chat path instead.
_MARKDOWN_HEADER_RE = re.compile(r"^#{1,6}[ \t]+", re.MULTILINE)
_MARKDOWN_BOLD_RE = re.compile(r"\*\*(.+?)\*\*")
_MARKDOWN_BOLD_UNDERSCORE_RE = re.compile(r"__(.+?)__")
_MARKDOWN_HR_RE = re.compile(r"^[ \t]*([-*_])(?:[ \t]*\1){2,}[ \t]*$", re.MULTILINE)
_MARKDOWN_TABLE_SEPARATOR_RE = re.compile(
    r"^[ \t]*\|?[ \t]*:?-{2,}:?[ \t]*(\|[ \t]*:?-{2,}:?[ \t]*)*\|?[ \t]*$", re.MULTILINE
)


def _strip_markdown_formatting(text: str) -> str:
    text = _MARKDOWN_TABLE_SEPARATOR_RE.sub("", text)
    text = _MARKDOWN_HR_RE.sub("", text)
    text = _MARKDOWN_HEADER_RE.sub("", text)
    text = _MARKDOWN_BOLD_RE.sub(r"\1", text)
    text = _MARKDOWN_BOLD_UNDERSCORE_RE.sub(r"\1", text)
    text = text.replace("|", " - ")
    return re.sub(r"\n{3,}", "\n\n", text).strip()


#: Bounded, real-facts-only grounding for the chat — deliberately more
#: than just headline + competency names (what this used to send):
#: confirmed live (2026-08-19) that a reply full of specific, confident
#: claims ("5 years as Scrum Master for two Fortune-500 product
#: streams," "$4M budget micro-services migration," "CSM certification
#: — present") was pure invention, since the model was never actually
#: given any Experience/Education/Certification facts to draw from in
#: the first place — headline/competency names alone give it nothing
#: to be specific about, yet it was specific anyway. Capped so a
#: profile with many entries doesn't blow the prompt budget; the model
#: is explicitly told these are the only facts it may reference (see
#: the "Formatting rules" footer at JD_TAILORING_CHAT_PROMPT_TEMPLATE's
#: end, extended with a matching grounding rule).
_MAX_EXPERIENCES_IN_CONTEXT = 6
_MAX_DESCRIPTION_CHARS = 300


def _build_profile_context(data: ResumeData) -> str:
    lines: list[str] = []
    headline = plain_text(data.profile.headline) if data.profile.headline else ""
    if headline:
        lines.append(f"Headline: {headline}")
    summary = plain_text(data.profile.summary) if data.profile.summary else ""
    if summary:
        lines.append(f"Summary: {summary}")
    competency_names = [c.name for c in data.profile.core_competencies]
    if competency_names:
        lines.append(f"Key skills/competencies: {', '.join(competency_names)}")

    if data.experiences:
        lines.append("Work experience:")
        for exp in data.experiences[:_MAX_EXPERIENCES_IN_CONTEXT]:
            desc = plain_text(exp.description or "")[:_MAX_DESCRIPTION_CHARS].strip()
            line = f"- {exp.title} at {exp.company} ({format_date_range(exp.start_date, exp.end_date)})"
            if desc:
                line += f": {desc}"
            lines.append(line)

    if data.educations:
        edu_parts = [
            f"{education_degree_line(edu)} — {edu.institution}".strip(" —")
            for edu in data.educations
        ]
        lines.append(f"Education: {'; '.join(edu_parts)}")

    if data.certifications:
        cert_names = [c.name for c in data.certifications]
        lines.append(f"Certifications: {', '.join(cert_names)}")

    if not lines:
        return ""
    return (
        "Candidate background — this is the ONLY information you have about the "
        "candidate; do not assume or invent anything beyond it:\n"
        + "\n".join(lines)
        + "\n"
    )


@dataclass(slots=True)
class JdTailoringTurn:
    session_id: UUID
    user_message: JdTailoringMessage
    assistant_message: JdTailoringMessage


class JdTailoringSessionService:
    def __init__(
        self,
        sessions: JdTailoringSessionRepository,
        messages: JdTailoringMessageRepository,
        resume_export: ResumeExportService,
        llm: LLMServiceInterface,
    ) -> None:
        self._sessions = sessions
        self._messages = messages
        self._resume_export = resume_export
        self._llm = llm

    async def start_from_listing(
        self,
        *,
        tenant_id: UUID,
        user_id: UUID,
        target_role_id: UUID | None,
        provider_id: str,
        title: str,
        company: str,
        redirect_url: str,
        jd_text: str,
    ) -> JdTailoringSession:
        now = datetime.now(UTC)
        return await self._sessions.create(
            JdTailoringSession(
                id=uuid.uuid4(),
                tenant_id=tenant_id,
                user_id=user_id,
                source_type="job_listing",
                jd_text=jd_text,
                created_at=now,
                updated_at=now,
                target_role_id=target_role_id,
                source_provider_id=provider_id,
                source_title=title,
                source_company=company,
                source_redirect_url=redirect_url,
            )
        )

    async def start_custom(
        self,
        *,
        tenant_id: UUID,
        user_id: UUID,
        target_role_id: UUID | None,
        jd_text: str,
        company: str,
        role_title: str,
    ) -> JdTailoringSession:
        # source_title/source_company aren't only for job_listing sessions
        # despite the name — a custom session has real company/role_title
        # too (AI-extracted + manually filled in), and without storing it
        # here the session history list would have nothing to show a
        # custom session as beyond a bare "Custom JD" for every one of
        # them, indistinguishable from each other.
        now = datetime.now(UTC)
        return await self._sessions.create(
            JdTailoringSession(
                id=uuid.uuid4(),
                tenant_id=tenant_id,
                user_id=user_id,
                source_type="custom",
                source_title=role_title,
                source_company=company,
                jd_text=jd_text,
                created_at=now,
                updated_at=now,
                target_role_id=target_role_id,
            )
        )

    async def get_owned_or_raise(
        self, *, tenant_id: UUID, user_id: UUID, session_id: UUID
    ) -> JdTailoringSession:
        """Public (not the usual leading-underscore ownership-check
        helper) — TailoredResumeService and the router both need to
        verify a session before acting on it, same reasoning as
        TargetRoleService.get_owned_or_raise."""
        session = await self._sessions.get_by_id(tenant_id, session_id)
        if session is None or session.user_id != user_id:
            raise NotFoundError(
                "JD Tailoring session not found.", code="JD_TAILORING_SESSION_NOT_FOUND"
            )
        return session

    async def list_for_user(self, tenant_id: UUID, user_id: UUID) -> list[JdTailoringSession]:
        return await self._sessions.list_for_user(tenant_id, user_id)

    async def list_messages(
        self, *, tenant_id: UUID, user_id: UUID, session_id: UUID
    ) -> list[JdTailoringMessage]:
        await self.get_owned_or_raise(tenant_id=tenant_id, user_id=user_id, session_id=session_id)
        return await self._messages.list_by_session(tenant_id, session_id)

    async def send_message(
        self, *, tenant_id: UUID, user_id: UUID, session_id: UUID, content: str
    ) -> JdTailoringTurn:
        session = await self.get_owned_or_raise(
            tenant_id=tenant_id, user_id=user_id, session_id=session_id
        )
        history = await self._messages.list_by_session(tenant_id, session_id)

        user_message = await self._messages.create(
            JdTailoringMessage(
                id=uuid.uuid4(),
                tenant_id=tenant_id,
                session_id=session_id,
                role=JdTailoringMessageRole.USER,
                content=content,
                created_at=datetime.now(UTC),
            )
        )

        reply = await self._generate_reply(
            tenant_id=tenant_id,
            user_id=user_id,
            session=session,
            history=history,
            content=content,
        )

        assistant_message = await self._messages.create(
            JdTailoringMessage(
                id=uuid.uuid4(),
                tenant_id=tenant_id,
                session_id=session_id,
                role=JdTailoringMessageRole.ASSISTANT,
                content=reply,
                created_at=datetime.now(UTC),
            )
        )
        return JdTailoringTurn(
            session_id=session_id,
            user_message=user_message,
            assistant_message=assistant_message,
        )

    async def soft_delete(self, *, tenant_id: UUID, user_id: UUID, session_id: UUID) -> None:
        await self.get_owned_or_raise(tenant_id=tenant_id, user_id=user_id, session_id=session_id)
        await self._sessions.soft_delete(tenant_id, session_id)

    async def clear_messages(self, *, tenant_id: UUID, user_id: UUID, session_id: UUID) -> None:
        """Wipes just the conversation history for a session — the
        session itself (its JD text, target role link, and any already-
        generated tailored resume) stays exactly as it is, unlike
        soft_delete above which removes the whole session. Direct
        2026-08-20 follow-up request: "the session needs to stay, but
        only the AI conversation [should be cleared]." A genuine hard
        delete of the message rows (JdTailoringMessage has no
        deleted_at column to soft-delete against, unlike the session
        itself), so this can't be undone.
        """
        await self.get_owned_or_raise(tenant_id=tenant_id, user_id=user_id, session_id=session_id)
        await self._messages.delete_all_for_session(tenant_id, session_id)

    async def delete_message(
        self, *, tenant_id: UUID, user_id: UUID, session_id: UUID, message_id: UUID
    ) -> None:
        """Removes exactly one message from the conversation — e.g. one
        specific piece of AI-suggested advice the person doesn't want to
        keep — leaving every other message and the session itself
        untouched. Direct 2026-08-20 follow-up to clear_messages above:
        "if the user wants... to pick any specific advice, then there
        should be one icon to enable the deletion of that specific
        conversation [message]."
        """
        await self.get_owned_or_raise(tenant_id=tenant_id, user_id=user_id, session_id=session_id)
        await self._messages.delete(tenant_id, session_id, message_id)

    async def _generate_reply(
        self,
        *,
        tenant_id: UUID,
        user_id: UUID,
        session: JdTailoringSession,
        history: list[JdTailoringMessage],
        content: str,
    ) -> str:
        # gather_resume_data_with_master_fallback (not a plain profile
        # lookup) — session.target_role_id arrives implicitly from
        # whichever role was selected in Opportunity Intelligence, and
        # grounding on an unpopulated Target Role Profile left this
        # chat with nothing but a headline/competency-name list (or
        # nothing at all) to work from, which is exactly what let the
        # model fabricate plausible-sounding specifics (years of
        # experience, project budgets, certifications) no real profile
        # data ever supported — confirmed live (2026-08-19).
        #
        # Unlike CareerProfileService.get_or_create (the previous
        # source here, which lazily auto-creates a blank profile row),
        # ResumeExportService's gather requires a real profile row to
        # already exist and raises NotFoundError otherwise — a brand
        # new user who reaches JD Tailoring without ever having visited
        # a page that auto-provisions their Master profile first is a
        # real, if rare, case. Treated the same as "no data available"
        # rather than letting it fail the whole chat turn.
        try:
            _profile, data = await self._resume_export.gather_resume_data_with_master_fallback(
                tenant_id=tenant_id, user_id=user_id, target_role_id=session.target_role_id
            )
            profile_context = _build_profile_context(data)
        except NotFoundError:
            profile_context = ""

        try:
            raw_reply = await self._llm.generate(
                use_case=_USE_CASE,
                input_variables={
                    "jd_text": session.jd_text,
                    "profile_context": profile_context,
                    "conversation_history": _render_history(history),
                    "user_message": content,
                },
                tenant_id=tenant_id,
                user_id=user_id,
                max_tokens=_MAX_RESPONSE_TOKENS,
            )
            return _strip_markdown_formatting(raw_reply)
        except CareerCompassError as exc:
            logger.warning("jd_tailoring_llm_generate_failed", code=exc.code, error=str(exc))
            return _FALLBACK_REPLY


def _render_history(history: list[JdTailoringMessage]) -> str:
    if not history:
        return "(no previous messages)"

    recent = history[-_MAX_HISTORY_MESSAGES:]
    speaker = {
        JdTailoringMessageRole.USER: "Candidate",
        JdTailoringMessageRole.ASSISTANT: "Advisor",
    }
    return "\n".join(f"{speaker[message.role]}: {message.content}" for message in recent)
