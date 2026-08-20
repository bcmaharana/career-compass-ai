"""AI-generated, JD-tailored resume content -> rendered into a real
DOCX/PDF, stored as its own artifact — never overwrites the profile's
canonical resume (a different storage key prefix than
ResumeExportService.generate's "generated-resumes/..." — see this
module's key pattern below).

Structured-JSON + regenerate-only pattern, same shape as
LearningRecommendationService/InterviewAnswerService: on failure, the
session's status/error fields are updated but a previously-good
tailored_resume_*_key is left untouched (InterviewAnswerService's
"failed regenerate never clobbers a good prior result" convention) —
generate() never raises for a generation failure, it returns the
session with status="failed" instead, same contract
InterviewAnswerService.generate_answer() has.

The AI is asked for plain text using the "• " bullet convention (see
app/core/rich_text.py's plain_text_to_rich_html docstring) rather than
raw HTML — safer than trusting LLM-authored markup, and it's the exact
conversion this app's own plain-text-migration script already
established.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from typing import Literal
from uuid import UUID

from app.adapters.documents.resume_docx_builder import build_resume_docx
from app.adapters.documents.resume_pdf_builder import build_resume_pdf
from app.ai_platform.llm_service.service import LLMServiceInterface
from app.application.career_profile.resume_export_service import ResumeExportService
from app.core.exceptions import CareerCompassError, NotFoundError
from app.core.logging import get_logger
from app.adapters.documents.rich_text_export import plain_text
from app.core.rich_text import plain_text_to_rich_html
from app.domain.jd_tailoring.entities import JdTailoringSession
from app.domain.jd_tailoring.repositories import JdTailoringSessionRepository
from app.domain.resume_intelligence.storage import PrivateObjectStorageRepository

logger = get_logger(__name__)

_USE_CASE = "jd_tailoring_resume_generation"
_MAX_RESPONSE_TOKENS = 3000
_JSON_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL)
_DOWNLOAD_URL_TTL_SECONDS = 3600

#: Confirmed live (2026-08-19): once gather_resume_data_with_master_fallback
#: (added the same day to fix a different bug — a Target Role Profile
#: with no data of its own would otherwise silently produce an
#: almost-empty tailored resume) started feeding a real, heavily-used
#: Master profile's *entire* experience list into this prompt, a real
#: generation attempt truncated mid-JSON ("The AI did not return
#: recognizable JSON.") — the model has to write tailored bullets for
#: every experience it's given within one fixed max_tokens budget, and
#: a profile with many entries (this app has seen 179 on one real
#: account) blows that budget long before the JSON closes. Same fix
#: LearningRecommendationService already applied for the same class of
#: problem (its own _MAX_SKILLS_PER_PROMPT): cap what's actually sent,
#: don't just raise the ceiling and delay the same failure. Experiences
#: beyond the cap simply keep their original, untailored description —
#: the existing bullets_by_id-miss fallback already handles that.
_MAX_EXPERIENCES_FOR_TAILORING = 8
_MAX_DESCRIPTION_CHARS_FOR_PROMPT = 500

TailoredResumeFormat = Literal["docx", "pdf"]

_CONTENT_TYPES: dict[TailoredResumeFormat, str] = {
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "pdf": "application/pdf",
}


#: reportlab's PDF builder renders resume text in a base-14 Helvetica
#: font under WinAnsiEncoding (CP1252) — confirmed live (2026-08-19):
#: em-dash/en-dash both have real CP1252 code points and render fine,
#: but U+2010/U+2011/U+2012 (hyphen/non-breaking hyphen/figure dash) do
#: not, and silently corrupt into an unrelated glyph in the generated
#: PDF ("high‑throughput" -> "highnthroughput") rather than raising
#: — caught by actually downloading and text-extracting a real
#: generated PDF, not assumed. An LLM is meaningfully more likely to
#: produce this specific character than a person typing through the
#: rich-text toolbar (which has no way to enter it), so this is fixed
#: here rather than in the shared resume_pdf_builder.py both this
#: service and the profile's own canonical resume export use.
_UNSAFE_HYPHENS_RE = re.compile("[‐‑‒]")


def _normalize_llm_text(text: str) -> str:
    return _UNSAFE_HYPHENS_RE.sub("-", text)


#: The model doesn't reliably follow "use the '• ' prefix convention"
#: as "the code will add that prefix, don't add your own" — confirmed
#: live (2026-08-19): a real generation's stored tailored_resume_content
#: had bullets already starting with "• " despite the prompt only
#: asking for the convention, not for this code to add it on top. This
#: code always adds exactly one "• " prefix regardless, so a bullet
#: already carrying one would get double-prefixed ("• • text") — and
#: plain_text_to_rich_html only strips the outer one, leaving a literal
#: "•" as part of the <li>'s own text, rendered as a stray bullet-shaped
#: glyph alongside the list's real bullet marker in the generated
#: document. Strip any bullet-like prefix the model already added before
#: this code adds its own canonical one.
_EXISTING_BULLET_PREFIX_RE = re.compile(r"^[•\-*]\s+")


def _strip_existing_bullet_prefix(text: str) -> str:
    return _EXISTING_BULLET_PREFIX_RE.sub("", text)


def _repair_raw_control_chars_in_json_strings(text: str) -> str:
    """Escapes literal newline/carriage-return/tab characters that
    appear INSIDE a JSON string literal — a well-documented LLM output
    bug: a raw control character inside a string is illegal per the
    JSON spec, but models routinely emit one anyway (e.g. a bullet the
    model "sees" as spanning multiple lines). Tracks string-literal
    state with a simple scan (toggling on an unescaped '"', respecting
    backslash-escapes) so control characters genuinely between JSON
    tokens — always legal there — are left untouched. Strictly
    additive: it can only turn illegal-per-spec bytes into their legal
    escaped form, never touch anything that was already valid, so it's
    safe to run unconditionally before every parse attempt.
    """
    out: list[str] = []
    in_string = False
    escaped = False
    for ch in text:
        if in_string:
            if escaped:
                out.append(ch)
                escaped = False
            elif ch == "\\":
                out.append(ch)
                escaped = True
            elif ch == '"':
                in_string = False
                out.append(ch)
            elif ch == "\n":
                out.append("\\n")
            elif ch == "\r":
                out.append("\\r")
            elif ch == "\t":
                out.append("\\t")
            else:
                out.append(ch)
        else:
            if ch == '"':
                in_string = True
            out.append(ch)
    return "".join(out)


def _parse_tailored_content(text: str) -> dict[str, object]:
    fence_match = _JSON_FENCE_RE.search(text)
    candidate = fence_match.group(1) if fence_match else text

    start = candidate.find("{")
    end = candidate.rfind("}")
    if start == -1 or end == -1 or end < start:
        raise ValueError("The AI did not return recognizable JSON.")

    json_slice = _repair_raw_control_chars_in_json_strings(candidate[start : end + 1])
    parsed: dict[str, object] = json.loads(json_slice)
    if not isinstance(parsed.get("headline"), str) or not isinstance(parsed.get("summary"), str):
        raise ValueError("The AI's response was missing 'headline'/'summary'.")
    if not isinstance(parsed.get("experience_bullets"), list):
        raise ValueError("The AI's response was missing an 'experience_bullets' array.")
    return parsed


@dataclass(slots=True)
class TailoredResumeDownloadUrls:
    docx_url: str | None
    pdf_url: str | None


class TailoredResumeService:
    def __init__(
        self,
        sessions: JdTailoringSessionRepository,
        resume_export: ResumeExportService,
        storage: PrivateObjectStorageRepository,
        llm: LLMServiceInterface,
    ) -> None:
        self._sessions = sessions
        self._resume_export = resume_export
        self._storage = storage
        self._llm = llm

    async def generate(
        self, *, tenant_id: UUID, user_id: UUID, session_id: UUID, format: TailoredResumeFormat
    ) -> tuple[JdTailoringSession, str | None]:
        session = await self._sessions.get_by_id(tenant_id, session_id)
        if session is None or session.user_id != user_id:
            raise NotFoundError(
                "JD Tailoring session not found.", code="JD_TAILORING_SESSION_NOT_FOUND"
            )

        # NotFoundError here (no profile at all) is a real 404, not a
        # generation failure — deliberately left outside the try below.
        # gather_resume_data_with_master_fallback (not plain
        # gather_resume_data) — session.target_role_id arrives
        # implicitly from whichever role was selected in Opportunity
        # Intelligence, and an unpopulated Target Role Profile would
        # otherwise silently produce a near-empty tailored resume. See
        # that method's docstring.
        _profile, base_data = await self._resume_export.gather_resume_data_with_master_fallback(
            tenant_id=tenant_id, user_id=user_id, target_role_id=session.target_role_id
        )
        experiences_json = json.dumps(
            [
                {
                    "id": str(e.id),
                    "title": e.title,
                    "company": e.company,
                    "description": plain_text(e.description or "")[
                        :_MAX_DESCRIPTION_CHARS_FOR_PROMPT
                    ],
                }
                for e in base_data.experiences[:_MAX_EXPERIENCES_FOR_TAILORING]
            ]
        )

        # Populated only once the LLM call itself succeeds — a failure
        # in _parse_tailored_content can then log what the model
        # actually returned, which the previous version of this code
        # never captured anywhere, making a real parse failure like
        # "Expecting ',' delimiter: line 36 column 6" undiagnosable
        # after the fact (confirmed live, 2026-08-19 — a real user
        # report with zero way to see the raw text that broke).
        raw: str | None = None
        try:
            raw = await self._llm.generate(
                use_case=_USE_CASE,
                input_variables={
                    "jd_text": session.jd_text,
                    "current_headline": base_data.profile.headline or "",
                    "current_summary": base_data.profile.summary or "",
                    "experiences_json": experiences_json,
                },
                tenant_id=tenant_id,
                user_id=user_id,
                max_tokens=_MAX_RESPONSE_TOKENS,
                temperature=0.3,
            )
            parsed = _parse_tailored_content(raw)

            tailored_profile = replace(
                base_data.profile,
                headline=plain_text_to_rich_html(_normalize_llm_text(str(parsed["headline"]))),
                summary=plain_text_to_rich_html(_normalize_llm_text(str(parsed["summary"]))),
            )
            experience_bullets = parsed["experience_bullets"]
            assert isinstance(experience_bullets, list)  # validated by _parse_tailored_content
            bullets_by_id: dict[str, list[str]] = {
                str(b["id"]): [_normalize_llm_text(str(x)) for x in b.get("bullets", [])]
                for b in experience_bullets
                if isinstance(b, dict) and "id" in b
            }
            tailored_experiences = [
                (
                    replace(
                        e,
                        description=plain_text_to_rich_html(
                            "\n".join(
                                f"• {_strip_existing_bullet_prefix(line)}"
                                for line in bullets_by_id[str(e.id)]
                            )
                        ),
                    )
                    if str(e.id) in bullets_by_id
                    else e
                )
                for e in base_data.experiences
            ]
            tailored_data = replace(
                base_data, profile=tailored_profile, experiences=tailored_experiences
            )

            content = (
                build_resume_docx(tailored_data)
                if format == "docx"
                else build_resume_pdf(tailored_data)
            )
            key = f"tailored-resumes/{tenant_id}/{session.id}/resume.{format}"
            await self._storage.upload_private(
                key=key, content=content, content_type=_CONTENT_TYPES[format]
            )

            if format == "docx":
                session.tailored_resume_docx_key = key
            else:
                session.tailored_resume_pdf_key = key
            session.tailored_resume_content = parsed
            session.tailored_resume_status = "generated"
            session.tailored_resume_error = None
        except (CareerCompassError, ValueError, json.JSONDecodeError, KeyError) as exc:
            logger.warning(
                "jd_tailored_resume_generate_failed",
                error=str(exc),
                raw_response=raw[:4000] if raw is not None else None,
            )
            session.tailored_resume_status = "failed"
            session.tailored_resume_error = str(exc)

        session.tailored_resume_generated_at = datetime.now(UTC)
        updated = await self._sessions.update(session)

        key_for_format = (
            updated.tailored_resume_docx_key
            if format == "docx"
            else updated.tailored_resume_pdf_key
        )
        url: str | None = None
        if key_for_format is not None:
            url = await self._storage.get_presigned_url(
                key=key_for_format,
                expires_in_seconds=_DOWNLOAD_URL_TTL_SECONDS,
                download_filename=f"Tailored Resume.{format}",
            )
        return updated, url

    async def get_download_urls(self, session: JdTailoringSession) -> TailoredResumeDownloadUrls:
        """Fresh presigned URLs for whichever formats have already been
        generated (None for a format never generated) — a stored
        presigned URL would go stale, same reasoning as
        ResumeExportService.get_download_urls."""
        docx_url = None
        if session.tailored_resume_docx_key is not None:
            docx_url = await self._storage.get_presigned_url(
                key=session.tailored_resume_docx_key,
                expires_in_seconds=_DOWNLOAD_URL_TTL_SECONDS,
                download_filename="Tailored Resume.docx",
            )
        pdf_url = None
        if session.tailored_resume_pdf_key is not None:
            pdf_url = await self._storage.get_presigned_url(
                key=session.tailored_resume_pdf_key,
                expires_in_seconds=_DOWNLOAD_URL_TTL_SECONDS,
                download_filename="Tailored Resume.pdf",
            )
        return TailoredResumeDownloadUrls(docx_url=docx_url, pdf_url=pdf_url)
