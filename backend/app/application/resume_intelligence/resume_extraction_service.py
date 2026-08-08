"""Resume upload + extraction application service.

Parsing happens synchronously within the upload request (this codebase
has no job queue): validate -> upload to the private resumes bucket ->
extract plain text (pdfplumber/python-docx, CPU-bound, run via
asyncio.to_thread) -> call the already-wired LLMService with a
structured-extraction prompt -> parse its JSON response into
extracted_data. Any failure past the initial validation step (text
extraction, the LLM call, or malformed JSON back from the model) is
caught and persisted as a `failed` Resume row with an error_message,
rather than raising — the user can see what happened and re-upload,
same "never hard-fail the whole request over an upstream failure"
principle ChatService already established, adapted here to surface a
retryable failure state instead of a fallback string (there's no
sensible fallback for structured extraction).
"""

from __future__ import annotations

import asyncio
import json
import re
import uuid
from datetime import UTC, date, datetime
from uuid import UUID

from app.ai_platform.llm_service.service import LLMServiceInterface
from app.application.resume_intelligence.certification_line_parser import (
    extract_certification_names,
)
from app.core.exceptions import CareerCompassError, NotFoundError, ValidationError
from app.core.logging import get_logger
from app.domain.resume_intelligence.entities import Resume
from app.domain.resume_intelligence.repositories import ResumeRepository
from app.domain.resume_intelligence.storage import PrivateObjectStorageRepository
from app.domain.resume_intelligence.text_extraction import ResumeTextExtractor

logger = get_logger(__name__)

_RESUME_EXTRACTION_USE_CASE = "resume_extraction"
_CERTIFICATION_ISSUER_BACKFILL_USE_CASE = "resume_certification_issuer_backfill"
_MAX_RESUME_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB
_MAX_PROMPT_CHARS = 24000  # keeps the rendered prompt within a safe token budget
# Raised from 15000 after a real, longer resume (15 roles spanning 1993-present,
# ~16.5k chars of extracted text) silently lost its three earliest roles to this
# cap before the prompt was ever built — every provider, not just a token-budget-
# constrained one, was extracting from a truncated source text with no visible
# error. 24000 chars covers this resume with headroom; GroqProvider's own
# defensive max_tokens clamp (see groq_provider.py's _SAFE_TOTAL_TOKEN_BUDGET)
# already handles the *output*-token side of a long prompt for that specific
# provider's tighter free-tier ceiling, so raising this input-side cap doesn't
# reintroduce the Groq 413 that constant was originally added to prevent.
# A full multi-role resume's JSON (all sections, with descriptions) can
# genuinely need more than 2500 tokens — raised defensively after field
# extraction gaps were observed live; a truncated response fails
# _parse_llm_json's JSON parsing outright (surfaced as a retryable
# `failed` status), which is safer than silently returning partial data,
# but still worth avoiding when it's simply a token-budget shortfall.
# Raised again to 6000 after a real resume with a fuller Career
# Highlights + Experience section produced a genuine mid-document JSON
# syntax error from qwen2.5:7b (a missing colon partway through, not a
# clean end-of-output truncation) — more headroom reduces how close to
# the limit a large resume's response gets, even though this particular
# failure wasn't confirmed to be truncation itself.
# Raised again to 8000 after a 9-role resume produced syntactically
# valid but content-incomplete JSON: education/certifications/
# career_highlights all came back as empty arrays even though the
# source resume genuinely has all three, while all 9 experience entries
# were written out in full — the model appears to "wrap up" into valid
# but empty trailing sections once it senses it's running low on room,
# rather than truncating mid-token the way it did the first time. That
# fix paired the token increase with reordering the prompt's schema so
# "experience" was written LAST, on the theory that whichever section is
# written last is the one at risk, so put the longest one there and let
# the shorter categories above it finish first.
#
# Reversed 2026-08-05: descriptions had been compressed to one sentence
# each specifically to make everything fit, which fixed the missing-
# sections bug but produced descriptions with none of the original
# bullet-point detail — a real, separate complaint once real resumes
# were reviewed. The prompt now asks for full per-role bullets instead
# of one-sentence summaries (see RESUME_EXTRACTION_PROMPT_TEMPLATE), and
# "experience" moved from last to right after "skills" in the schema
# order, since it's now both the longest AND the most important section
# to protect from truncation — if a very long resume still runs low on
# room, "career_highlights" (last again, least critical, often already
# redundant with per-role descriptions) is the one left incomplete
# instead. Raised to 8192 (Claude's standard per-call output ceiling
# without an extended-output beta header, which this adapter does not
# set) for a little extra headroom given descriptions now run
# considerably longer than a single sentence — Ollama/Groq have no such
# hard ceiling, so this is really about staying under Anthropic's.
_MAX_RESPONSE_TOKENS = 8192
# OllamaProvider's own default (600s) proved too short here once the
# extraction prompt grew a worked example to fix skill/category
# splitting quality — a real qwen2.5:7b run against a full resume was
# observed live taking somewhere between 900s and 1800s with the longer
# prompt. Anthropic ignores this override (hosted, fast; no reason to
# wait 30 minutes on a genuine failure there) — it only matters for
# Ollama's local CPU inference. See LLMRequest.timeout_seconds.
_LLM_TIMEOUT_SECONDS = 1800.0
# Certifications are the one section observed live to be genuinely
# hard, across every fix attempted so far: a plain "count carefully"
# instruction, a model-self-reported count, and a two-step "transcribe
# every name, then enrich" split (RESUME_EXTRACTION_PROMPT_TEMPLATE's
# "certification_names_found" array) ALL failed identically — the same
# two names ("Digital Product Management", "Generative AI Leader")
# dropped from the same 13-item list, on both Groq's
# llama-3.3-70b-versatile and a local qwen2.5:7b. That pattern (same
# failure, different models, different prompt strategies) means this
# isn't a counting/attention gap prompting can fix — it looks like a
# semantic bias in the model's own judgment of "does this look like a
# real certification" (both dropped names read like generic role/skill
# phrases, unlike their kept neighbor "Google Cloud Digital Leader",
# which has an obvious vendor prefix). See
# app/application/resume_intelligence/certification_line_parser.py for
# the actual fix: a deterministic, delimiter-based parse of the resume's
# own Certifications section, used as ground truth instead of trusting
# the model to both notice AND count every name. A retry is still
# attempted once (cheap, and a second attempt does sometimes get it
# right), but the parser's count — not the model's own — decides whether
# one is warranted, and _backfill_missing_certifications below is the
# real safety net for whatever a retry still doesn't fix.
_MAX_EXTRACTION_ATTEMPTS = 2

_CONTENT_TYPE_EXTENSIONS = {
    "application/pdf": "pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
}

_JSON_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL)
_TRAILING_COMMA_RE = re.compile(r",(\s*[}\]])")


class ResumeExtractionService:
    def __init__(
        self,
        resumes: ResumeRepository,
        storage: PrivateObjectStorageRepository,
        extractor: ResumeTextExtractor,
        llm_service: LLMServiceInterface,
    ) -> None:
        self._resumes = resumes
        self._storage = storage
        self._extractor = extractor
        self._llm = llm_service

    async def upload_and_extract(
        self,
        *,
        tenant_id: UUID,
        user_id: UUID,
        filename: str,
        content: bytes,
        content_type: str,
        target_role_id: UUID | None = None,
    ) -> Resume:
        if content_type not in _CONTENT_TYPE_EXTENSIONS:
            raise ValidationError(
                f"Unsupported resume type '{content_type}'. Allowed: PDF, DOCX.",
                code="UNSUPPORTED_RESUME_TYPE",
            )
        if len(content) > _MAX_RESUME_SIZE_BYTES:
            raise ValidationError(
                f"Resume exceeds the {_MAX_RESUME_SIZE_BYTES // (1024 * 1024)}MB limit.",
                code="RESUME_TOO_LARGE",
            )

        resume_id = uuid.uuid4()
        extension = _CONTENT_TYPE_EXTENSIONS[content_type]
        key = f"resumes/{tenant_id}/{user_id}/{resume_id}.{extension}"
        await self._storage.upload_private(key=key, content=content, content_type=content_type)

        now = datetime.now(UTC)
        raw_text: str | None = None
        extracted_data: dict[str, object] | None = None
        error_message: str | None = None

        llm_text: str | None = None
        try:
            raw_text = await asyncio.to_thread(
                self._extractor.extract_text, content=content, content_type=content_type
            )
            if not raw_text.strip():
                raise ValidationError(
                    "No readable text found in this file.", code="RESUME_EMPTY_TEXT"
                )

            # Ground truth, computed once from the resume's own text —
            # see certification_line_parser.py's module docstring for
            # why this replaces trusting the model to notice AND count
            # every name itself.
            heuristic_cert_names = extract_certification_names(raw_text)

            parsed_raw: dict[str, object] = {}
            for attempt in range(1, _MAX_EXTRACTION_ATTEMPTS + 1):
                llm_text = await self._llm.generate(
                    use_case=_RESUME_EXTRACTION_USE_CASE,
                    input_variables={"resume_text": raw_text[:_MAX_PROMPT_CHARS]},
                    tenant_id=tenant_id,
                    user_id=user_id,
                    max_tokens=_MAX_RESPONSE_TOKENS,
                    # Deterministic, not creative — correctness matters far
                    # more than variety for structured extraction. Non-zero
                    # sampling was observed live to make a small local model
                    # (qwen2.5:7b) inconsistently omit fields (e.g. a
                    # resume's headline) that a greedy/deterministic decode
                    # reliably caught on the same input.
                    temperature=0.0,
                    timeout_seconds=_LLM_TIMEOUT_SECONDS,
                )
                parsed_raw = _parse_llm_json(llm_text)
                still_incomplete = _certifications_look_incomplete(
                    parsed_raw, heuristic_count=len(heuristic_cert_names)
                )
                if not still_incomplete or attempt == _MAX_EXTRACTION_ATTEMPTS:
                    break
                logger.warning(
                    "resume_extraction_certifications_undercount_retrying",
                    heuristic_count=len(heuristic_cert_names),
                    actual=len(_as_list(parsed_raw.get("certifications"))),
                    attempt=attempt,
                )
            extracted_data = _normalize_extracted_data(parsed_raw)

            existing_certifications = _as_list(extracted_data["certifications"])
            missing_names = _missing_certification_names(
                heuristic_cert_names, existing_certifications
            )
            if missing_names:
                backfilled = await self._backfill_missing_certifications(
                    missing_names, tenant_id=tenant_id, user_id=user_id
                )
                extracted_data["certifications"] = [*existing_certifications, *backfilled]

            status = "parsed"
        except (CareerCompassError, ValueError) as exc:
            # llm_text is logged in full specifically for JSON parse
            # failures, so a real syntax mistake in the model's own
            # output can actually be inspected afterward — the first
            # time this happened live, a 2000-char truncation cut the
            # log off well before the actual error position the
            # exception reported, making the root cause unconfirmable
            # after the fact even with this logging in place. Backend-
            # only structured logging, never user-facing, so the full
            # text (a single resume's response, not unbounded) is safe
            # to log in full rather than guessing at a truncation length
            # that might cut off the interesting part again.
            logger.warning(
                "resume_extraction_failed",
                code=getattr(exc, "code", None),
                error=str(exc),
                llm_response=llm_text,
            )
            status = "failed"
            error_message = str(exc)

        resume = Resume(
            id=resume_id,
            tenant_id=tenant_id,
            user_id=user_id,
            original_filename=filename,
            file_key=key,
            content_type=content_type,
            file_size_bytes=len(content),
            status=status,
            raw_text=raw_text,
            extracted_data=extracted_data,
            error_message=error_message,
            target_role_id=target_role_id,
            created_at=now,
            updated_at=now,
        )
        return await self._resumes.create(resume)

    async def _backfill_missing_certifications(
        self, missing_names: list[str], *, tenant_id: UUID, user_id: UUID
    ) -> list[dict[str, object]]:
        """Asks the LLM to name an issuing_organization for a small,
        already-known list of certification names — a much narrower task
        than full extraction (see
        CERTIFICATION_ISSUER_BACKFILL_PROMPT_TEMPLATE in
        scripts/seed_platform_defaults.py for why that narrowness
        matters). Best-effort: any failure here (a provider error,
        malformed JSON, a name the model's response happens to omit)
        just means that name doesn't get backfilled this round — the
        rest of the resume's extraction has already succeeded by this
        point, and this bonus enrichment step has no business failing
        the whole upload over itself.
        """
        try:
            llm_text = await self._llm.generate(
                use_case=_CERTIFICATION_ISSUER_BACKFILL_USE_CASE,
                input_variables={
                    "cert_names": "\n".join(f"- {name}" for name in missing_names)
                },
                tenant_id=tenant_id,
                user_id=user_id,
                max_tokens=1024,
                temperature=0.0,
                timeout_seconds=_LLM_TIMEOUT_SECONDS,
            )
            issuers = _parse_llm_json(llm_text)
        except (CareerCompassError, ValueError) as exc:
            logger.warning(
                "resume_extraction_certification_backfill_failed",
                error=str(exc),
                missing_names=missing_names,
            )
            return []

        now = datetime.now(UTC)
        backfilled: list[dict[str, object]] = []
        for name in missing_names:
            issuer = issuers.get(name)
            if not isinstance(issuer, str) or not issuer.strip():
                continue
            backfilled.append(
                {
                    "name": name,
                    "issuing_organization": issuer.strip(),
                    "issue_date": None,
                    "expiration_date": None,
                    "credential_id": None,
                    "credential_url": None,
                }
            )
        if len(backfilled) < len(missing_names):
            logger.warning(
                "resume_extraction_certification_backfill_partial",
                requested=missing_names,
                backfilled=[b["name"] for b in backfilled],
                timestamp=now.isoformat(),
            )
        return backfilled

    async def get_owned_or_raise(
        self, *, tenant_id: UUID, user_id: UUID, resume_id: UUID
    ) -> Resume:
        resume = await self._resumes.get_by_id(tenant_id, resume_id)
        if resume is None or resume.user_id != user_id:
            raise NotFoundError("Resume not found.", code="RESUME_NOT_FOUND")
        return resume

    async def list_for_current_user(self, *, tenant_id: UUID, user_id: UUID) -> list[Resume]:
        return await self._resumes.list_for_user(tenant_id, user_id)

    async def discard(self, *, tenant_id: UUID, user_id: UUID, resume_id: UUID) -> None:
        resume = await self._resumes.get_by_id(tenant_id, resume_id)
        if resume is None or resume.user_id != user_id:
            # Idempotent from the caller's perspective, same as ObjectStorageRepository.delete().
            return
        await self._resumes.soft_delete(tenant_id, resume_id)


def _parse_llm_json(text: str) -> dict[str, object]:
    """The extraction prompt instructs strict JSON-only output, but
    models sometimes wrap it in a markdown code fence anyway — strip
    that first, then take the substring between the first '{' and the
    last '}' before parsing, so stray leading/trailing prose doesn't
    break json.loads.
    """
    fence_match = _JSON_FENCE_RE.search(text)
    candidate = fence_match.group(1) if fence_match else text

    start = candidate.find("{")
    if start == -1:
        # No opening brace anywhere - the model didn't attempt JSON at
        # all (e.g. a refusal or unrelated prose), a different failure
        # class from a genuinely truncated JSON response below.
        raise ValueError("The AI did not return recognizable JSON.")

    end = candidate.rfind("}")
    # A genuinely complete response ends (after trimming whitespace) with
    # its own closing '}' - checked on the *un-sliced* candidate, before
    # the [start:end+1] slice below would already strip any trailing
    # prose a model added after an otherwise-complete JSON object (that
    # case parses fine on its own and never reaches the except block
    # below, so this flag only ever matters once parsing has genuinely
    # failed). No closing '}' at all, or one present but not at the very
    # end, means the response was cut off mid-generation - almost always
    # because the resume needed more output tokens than the provider
    # allowed for this request, not a stray formatting slip a
    # trailing-comma fix could repair.
    looks_truncated = end == -1 or not candidate.rstrip().endswith("}")
    truncated_message = (
        "Your resume has too much content for the AI to process in a single "
        "request. Try shortening some sections (e.g. combine or trim older/less "
        "relevant roles) and upload again."
    )

    if end == -1 or end < start:
        if looks_truncated:
            raise ValueError(truncated_message)
        raise ValueError("The AI did not return recognizable JSON.")

    candidate = candidate[start : end + 1]
    try:
        parsed = json.loads(candidate)
    except json.JSONDecodeError:
        # A trailing comma before a closing brace/bracket
        # (`"x": 1,}` / `[1, 2,]`) is a common small-model slip and safe
        # to fix mechanically — it never changes what the model actually
        # said, unlike guessing at a missing colon or bracket would.
        # Only retried once; if this doesn't fix it, surface the
        # *original* error below rather than a confusing second one.
        try:
            parsed = json.loads(_TRAILING_COMMA_RE.sub(r"\1", candidate))
        except json.JSONDecodeError as exc:
            if looks_truncated:
                raise ValueError(truncated_message) from exc
            raise ValueError(f"The AI's response was not valid JSON: {exc}") from exc

    if not isinstance(parsed, dict):
        raise ValueError("The AI's response was not a JSON object.")
    return parsed


def _certifications_look_incomplete(parsed: dict[str, object], *, heuristic_count: int) -> bool:
    """True when `certifications` has fewer entries than either (a) the
    resume's own text suggests via `certification_line_parser`'s
    deterministic parse (`heuristic_count` — the authoritative signal,
    computed independently of anything the model says), or (b) the
    model's own self-reported `certification_names_found` transcription
    array, kept as a secondary signal since it costs nothing to check
    and occasionally still catches something the heuristic parse missed
    (e.g. a Certifications heading this module's regex doesn't
    recognize). Only ever used to decide whether to retry the whole
    extraction once more.

    A still-earlier version of this check relied SOLELY on a
    model-self-reported integer count — verified live NOT to work: the
    model simply echoed the length of whatever it had already written to
    `certifications` rather than independently re-deriving the count, so
    the "check" always trivially passed even when items were genuinely
    missing. `heuristic_count` doesn't have that failure mode, since
    Python computed it, not the model.
    """
    actual = len(_as_list(parsed.get("certifications")))
    if actual < heuristic_count:
        return True
    names_found = parsed.get("certification_names_found")
    if isinstance(names_found, list) and actual < len(names_found):
        return True
    return False


def _normalize_certification_name_for_matching(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", name.lower())


def _missing_certification_names(
    heuristic_names: list[str], extracted_certifications: object
) -> list[str]:
    """Names `certification_line_parser` found in the resume's own text
    that never made it into the final `certifications` array at all —
    even after a retry. Matched loosely (case/punctuation-insensitive,
    substring either direction) since the model's own chosen wording for
    a name it DID extract correctly won't always match the heuristic
    parse's verbatim source text character-for-character.
    """
    existing = [
        str(item["name"])
        for item in _as_list(extracted_certifications)
        if isinstance(item, dict) and item.get("name")
    ]
    existing_normalized = [_normalize_certification_name_for_matching(n) for n in existing]

    missing: list[str] = []
    for name in heuristic_names:
        target = _normalize_certification_name_for_matching(name)
        if not target:
            continue
        if any(target == e or target in e or e in target for e in existing_normalized):
            continue
        missing.append(name)
    return missing


def _clean_str(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    trimmed = value.strip()
    return trimmed or None


def _as_list(value: object) -> list[object]:
    return value if isinstance(value, list) else []


# Fallback formats tried, in order, when a date string isn't already
# strict ISO "YYYY-MM-DD" — smaller/local models (unlike Claude) are far
# less reliable at following the prompt's format instruction exactly,
# and commonly return "Apr 2023"-style dates instead.
_DATE_FALLBACK_FORMATS = ("%b %Y", "%B %Y", "%Y-%m", "%m/%Y", "%m-%Y", "%Y")


def _clean_date(value: object) -> str | None:
    """Normalizes a date string to strict ISO "YYYY-MM-DD", or drops it
    entirely if it can't be confidently parsed — never passes a raw,
    non-ISO string through. A raw pass-through here previously crashed
    ResumeResponse's Pydantic validation the moment the extracted data
    was read back (a real bug caught live against a genuine successful
    Ollama extraction, not by review: the *upload* response itself
    500'd because Pydantic's `date` field rejected "Apr 2023"). Missing
    day/month information is never guessed at beyond "the 1st of the
    month" for month-level precision, or "the 1st of January" for
    year-only — matching the extraction prompt's own instruction for
    the model's own year-only case, applied here defensively for
    whatever precision the model actually returned.
    """
    text = _clean_str(value)
    if text is None:
        return None
    try:
        return date.fromisoformat(text).isoformat()
    except ValueError:
        pass
    for fmt in _DATE_FALLBACK_FORMATS:
        try:
            parsed = datetime.strptime(text, fmt)
        except ValueError:
            continue
        # None of these formats specify a day (or, for "%Y", a month
        # either) — strptime defaults the unspecified fields to the 1st,
        # which is exactly the "month/year-only -> the 1st" behavior we
        # want, so no extra logic is needed here.
        return date(parsed.year, parsed.month, parsed.day).isoformat()
    return None


def _normalize_extracted_data(parsed: dict[str, object]) -> dict[str, object]:
    """The LLM's JSON output is free-form model output, not a validated
    contract — this fills in missing top-level keys with safe defaults
    and drops individual list items missing their required fields,
    rather than failing the entire resume over one malformed entry (a
    missing date on one job shouldn't discard every other extracted
    section). The result is guaranteed to match ExtractedResumeData's
    shape (app/api/v1/resume_intelligence/schemas.py) for response
    serialization.

    One thing this must NOT do silently: a weaker model can return
    syntactically valid JSON that still doesn't match the required
    field names (e.g. "position"/"achievements" instead of the
    specified "title"/"description") — every item in that section then
    fails its required-field check above and gets dropped, one at a
    time, with nothing to distinguish it from "the resume genuinely has
    no experience." Observed live: qwen2.5:3b returned a real 9-entry
    "experience" array with its own invented field names, silently
    normalized down to zero entries, while the resume's Education
    section (whose required field name the model happened to guess
    right) came through fine — the user saw a "successful" parse with
    every section but Education empty, no error at all. `_check_dropped_section`
    below catches this specific shape (items were present but ALL got
    discarded) and raises rather than returning a falsely-successful result.
    """

    def _check_dropped_section(name: str, raw_items: list[object], kept_count: int) -> None:
        if raw_items and kept_count == 0:
            raise ValueError(
                f"The AI's response for '{name}' didn't match the required format "
                "(e.g. wrong field names) and had to be discarded rather than save "
                "incomplete data. Try uploading again, or try a different AI model "
                "in Settings > AI Model."
            )

    raw_skills = _as_list(parsed.get("skills"))
    skills = []
    for item in raw_skills:
        if not isinstance(item, dict):
            continue
        name = _clean_str(item.get("name"))
        if not name:
            continue
        skills.append({"name": name, "category": _clean_str(item.get("category"))})
    _check_dropped_section("skills", raw_skills, len(skills))

    raw_experience = _as_list(parsed.get("experience"))
    experience = []
    for item in raw_experience:
        if not isinstance(item, dict):
            continue
        title, company = _clean_str(item.get("title")), _clean_str(item.get("company"))
        if not title or not company:
            continue
        experience.append(
            {
                "title": title,
                "company": company,
                "location": _clean_str(item.get("location")),
                "start_date": _clean_date(item.get("start_date")),
                "end_date": _clean_date(item.get("end_date")),
                "description": _clean_str(item.get("description")),
            }
        )
    _check_dropped_section("experience", raw_experience, len(experience))

    raw_education = _as_list(parsed.get("education"))
    education = []
    for item in raw_education:
        if not isinstance(item, dict):
            continue
        institution = _clean_str(item.get("institution"))
        if not institution:
            continue
        education.append(
            {
                "institution": institution,
                "degree": _clean_str(item.get("degree")),
                "field_of_study": _clean_str(item.get("field_of_study")),
                "start_date": _clean_date(item.get("start_date")),
                "end_date": _clean_date(item.get("end_date")),
                "description": _clean_str(item.get("description")),
            }
        )
    _check_dropped_section("education", raw_education, len(education))

    raw_certifications = _as_list(parsed.get("certifications"))
    certifications = []
    for item in raw_certifications:
        if not isinstance(item, dict):
            continue
        name, issuer = _clean_str(item.get("name")), _clean_str(item.get("issuing_organization"))
        if not name or not issuer:
            continue
        certifications.append(
            {
                "name": name,
                "issuing_organization": issuer,
                "issue_date": _clean_date(item.get("issue_date")),
                "expiration_date": _clean_date(item.get("expiration_date")),
                "credential_id": _clean_str(item.get("credential_id")),
                "credential_url": _clean_str(item.get("credential_url")),
            }
        )
    _check_dropped_section("certifications", raw_certifications, len(certifications))

    raw_career_highlights = _as_list(parsed.get("career_highlights"))
    career_highlights = []
    for item in raw_career_highlights:
        if not isinstance(item, dict):
            continue
        title = _clean_str(item.get("title"))
        if not title:
            continue
        career_highlights.append(
            {
                "title": title,
                "company": _clean_str(item.get("company")),
                "description": _clean_str(item.get("description")),
                "occurred_on": _clean_date(item.get("occurred_on")),
            }
        )
    _check_dropped_section("career_highlights", raw_career_highlights, len(career_highlights))

    raw_key_achievements = _as_list(parsed.get("key_achievements"))
    key_achievements = []
    for item in raw_key_achievements:
        if not isinstance(item, dict):
            continue
        title = _clean_str(item.get("title"))
        if not title:
            continue
        key_achievements.append(
            {
                "title": title,
                "company": _clean_str(item.get("company")),
                "description": _clean_str(item.get("description")),
                "occurred_on": _clean_date(item.get("occurred_on")),
            }
        )
    _check_dropped_section("key_achievements", raw_key_achievements, len(key_achievements))

    return {
        "headline": _clean_str(parsed.get("headline")),
        "summary": _clean_str(parsed.get("summary")),
        "skills": skills,
        "experience": experience,
        "education": education,
        "certifications": certifications,
        "career_highlights": career_highlights,
        "key_achievements": key_achievements,
    }
