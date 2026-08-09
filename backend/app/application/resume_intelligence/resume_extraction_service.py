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
from app.application.resume_intelligence.headline_fallback_parser import (
    extract_headline_fallback,
)
from app.application.resume_intelligence.skills_section_detector import (
    has_dedicated_skills_section,
)
from app.core.exceptions import CareerCompassError, NotFoundError, ValidationError
from app.core.logging import get_logger
from app.domain.resume_intelligence.entities import Resume
from app.domain.resume_intelligence.repositories import ResumeRepository
from app.domain.resume_intelligence.storage import PrivateObjectStorageRepository
from app.domain.resume_intelligence.text_extraction import ResumeTextExtractor

logger = get_logger(__name__)

_RESUME_EXTRACTION_USE_CASE = "resume_extraction"
# The literal, honest fallback for a certification's issuing_organization
# whenever the resume's own text doesn't state one — see
# _verified_issuer's docstring for why this app no longer trusts
# general-knowledge inference for this field at all, even for
# "well-known" credentials.
_NOT_SPECIFIED_ISSUER = "Not specified in resume"
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
            extracted_data = _normalize_extracted_data(parsed_raw, raw_text)

            existing_certifications = _as_list(extracted_data["certifications"])
            missing_names = _missing_certification_names(
                heuristic_cert_names, existing_certifications
            )
            if missing_names:
                backfilled = self._backfill_missing_certifications(missing_names)
                extracted_data["certifications"] = [*existing_certifications, *backfilled]

            if not extracted_data.get("headline"):
                fallback_headline = extract_headline_fallback(raw_text)
                if fallback_headline:
                    logger.info(
                        "resume_extraction_headline_fallback_applied",
                        headline=fallback_headline,
                    )
                    extracted_data["headline"] = fallback_headline

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

    def _backfill_missing_certifications(
        self, missing_names: list[str]
    ) -> list[dict[str, object]]:
        """Pairs each name `certification_line_parser`'s deterministic
        ground truth found but the model's own certifications array
        never did, even after a retry, with the honest "not specified"
        fallback — deterministic, no LLM call.

        This used to ask the LLM to name a real issuing_organization for
        these names via a small, separate call. Removed after a real,
        explicitly requested product change: a name reaching this path
        already means neither the model's first-pass extraction NOR the
        heuristic parse found it paired with an issuer anywhere in the
        resume's own text, so asking a second time for the same
        unstated information only reproduces the exact problem
        `_verified_issuer` exists to close for the main extraction path
        too — see that function's docstring.
        """
        return [
            {
                "name": name,
                "issuing_organization": _NOT_SPECIFIED_ISSUER,
                "issue_date": None,
                "expiration_date": None,
                "credential_id": None,
                "credential_url": None,
            }
            for name in missing_names
        ]

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


# Decorative branding symbols a model can drop while otherwise
# reproducing a line verbatim — real bug caught live: the source text
# had "SAFe® programs", the model wrote "SAFe programs" (every actual
# word intact, just the trademark symbol gone), which broke an
# otherwise-exact match in _restore_bullet_markers below since a plain
# lowercase+whitespace normalization doesn't account for it. None of
# these carry meaning for a text-matching comparison, so stripping them
# can only help every caller of this shared normalizer, not just bullets.
_DECORATIVE_SYMBOLS_RE = re.compile(r"[®™©]")


def _normalize_for_source_check(text: str) -> str:
    text = _DECORATIVE_SYMBOLS_RE.sub("", text)
    return re.sub(r"\s+", " ", text.lower()).strip()


# Below this length a substring check is too easy to satisfy by
# coincidence (e.g. a short, generic title matching unrelated source
# text) to safely use as an "is this real" signal either way — such
# entries are left alone rather than risking a false-positive drop.
_MIN_LENGTH_FOR_SOURCE_VERIFICATION = 15


def _appears_in_source(candidate: str, raw_text_normalized: str) -> bool:
    """True if `candidate`'s text can be found, close to verbatim, inside
    the resume's own raw text. Used as a deterministic check on
    "career_highlights"/"key_achievements" entries: unlike the rest of
    the schema, both are supposed to be extractive (copied from a real
    line in the resume, not composed), so anything that doesn't actually
    appear in the source is either a hallucination or a section the
    model invented by pattern-matching the prompt's own worked example
    — both observed live. Short candidates are left unverified (see
    _MIN_LENGTH_FOR_SOURCE_VERIFICATION) rather than risking a
    false-positive drop of something real but brief.
    """
    normalized = _normalize_for_source_check(candidate)
    if len(normalized) < _MIN_LENGTH_FOR_SOURCE_VERIFICATION:
        return True
    return normalized in raw_text_normalized


def _verified_issuer(issuer: str, raw_text_normalized: str) -> str:
    """The issuing_organization the model reported is trusted only if the
    resume's own raw text actually contains it — otherwise it's treated
    as unverifiable general-knowledge inference and overwritten with the
    honest `_NOT_SPECIFIED_ISSUER` fallback.

    A real, explicitly requested product change: this app previously let
    the model fill in a specific real-world issuer for "well-known"
    credentials (e.g. "PMP" -> "PMI (Project Management Institute)")
    even when the resume itself never stated one, reasoning that a
    widely-documented fact is safe to state confidently. Live testing
    against a real resume proved that reasoning wrong in practice: some
    of those confident answers were right (PMP -> PMI), but others were
    subtly incorrect (a real "SSGB" certification attributed to the
    wrong issuing body; "Google Cloud Digital Leader" attributed to
    "Google Web", not a real organization) — with nothing distinguishing
    a correct guess from a wrong one to the person reading it. An honest
    "not specified" for every certification the resume itself is silent
    on is strictly better than a mix of right and confidently-wrong
    answers with no way to tell which is which.

    Deliberately does NOT exempt short issuer strings the way
    `_appears_in_source` exempts short candidates above — the risk here
    runs the opposite direction. For career_highlights/key_achievements,
    a short candidate risks a false-positive REJECTION of something
    real but brief. Here, a short issuer (most real ones are: "PMI",
    "AWS", "ICAgile") risks a false-positive ACCEPTANCE of a fabricated
    one via pure coincidence — exempting it from verification would
    defeat the entire point of this check.
    """
    if issuer == _NOT_SPECIFIED_ISSUER:
        return issuer
    if _normalize_for_source_check(issuer) in raw_text_normalized:
        return issuer
    return _NOT_SPECIFIED_ISSUER


def _bulleted_source_lines_normalized(raw_text: str) -> list[str]:
    """Every line of `raw_text` that starts with the resume text
    extractor's own "• " bullet-prefix convention
    (app/adapters/parsing/resume_text_extractor.py), with the marker
    stripped and the rest normalized — the ground truth
    `_restore_bullet_markers` below checks a model's output line
    against, in both directions: to decide whether a missing "• "
    should be put back, and whether one that's present shouldn't be.
    """
    lines = []
    for line in raw_text.split("\n"):
        stripped = line.strip()
        if stripped.startswith("• "):
            lines.append(_normalize_for_source_check(stripped[2:]))
    return lines


def _restore_bullet_markers(description: str, bulleted_source_lines: list[str]) -> str:
    """Corrects a description's "• " markers to match which lines were
    ACTUALLY bulleted in the source text, in BOTH directions — adding a
    marker the model dropped from a line that genuinely was bulleted,
    and just as importantly, removing one the model wrongly added to a
    line that wasn't.

    Two real bugs caught live, both from the same underlying prompt
    instruction not holding reliably across models: (1) Groq's
    llama-3.3-70b-versatile kept every line's content, order, and the
    newlines between them intact, but stripped the "• " prefix from
    literally every line. (2) qwen2.5:3b did the OPPOSITE on a
    two-role resume where only the second role had a genuine intro
    line before its bullets — having correctly bulleted every line of
    the FIRST role (which really was 100% bulleted in the source), it
    then over-generalized that pattern onto the second role's plain
    intro line too, bulleting a line the source never bulleted. An
    earlier, ADD-only version of this function couldn't fix case (2) at
    all — it only ever restored a missing marker, never questioned one
    that was already present — so a wrongly-bulleted line sailed
    through untouched. Rather than chase another prompt tweak for
    either provider's quirk, both directions are decided
    deterministically from the resume's own text.

    Matching is intentionally one-directional now (candidate content
    must equal, or be contained within, a genuine bulleted source
    line) — NOT the reverse (a genuine bulleted line contained within
    the candidate). That reverse direction was in an earlier version of
    this check and is a real false-positive risk: a long candidate line
    (like a plain intro paragraph) could coincidentally contain some
    unrelated short bulleted line's text as a substring, which would
    have wrongly marked an intro line as "should be bulleted" — a
    concrete instance of exactly the "candidate matches unrelated
    resume content" failure this design is meant to avoid.

    Short lines are corrected in NEITHER direction (same reasoning as
    `_MIN_LENGTH_FOR_SOURCE_VERIFICATION` elsewhere in this file) — a
    short line's bullet status can't be confidently verified either
    way from a coincidental match, so the model's own choice for it is
    trusted as-is, exactly as it always was before either bug existed.
    """
    if not bulleted_source_lines and "• " not in description:
        return description

    corrected_lines = []
    changed = False
    for line in description.split("\n"):
        stripped = line.strip()
        if not stripped:
            corrected_lines.append(line)
            continue
        is_bulleted = stripped.startswith("• ")
        content = stripped[2:] if is_bulleted else stripped
        normalized = _normalize_for_source_check(content)
        if len(normalized) < _MIN_LENGTH_FOR_SOURCE_VERIFICATION:
            corrected_lines.append(line)
            continue

        should_be_bulleted = any(
            normalized == src or normalized in src for src in bulleted_source_lines
        )
        if should_be_bulleted and not is_bulleted:
            corrected_lines.append(f"• {content}")
            changed = True
        elif is_bulleted and not should_be_bulleted:
            corrected_lines.append(content)
            changed = True
        else:
            corrected_lines.append(line)
    return "\n".join(corrected_lines) if changed else description


# An award/recognition NAME is short — a long "title" between the dash
# and colon more likely means they're just ordinary punctuation inside a
# ONE-shape plain sentence, not this specific "Company - Award: Detail"
# two-part structure. Same word-count-based confidence guard already
# established for certification list items in
# certification_line_parser.py.
_MAX_KEY_ACHIEVEMENT_TITLE_WORDS = 6


def _split_key_achievement(title: str) -> dict[str, str] | None:
    """If `title` matches the prompt's own "Company - Award Name:
    Description" shape for a key achievement (a dash separating a
    company from an award name, THEN a colon separating the award name
    from its detail — see RESUME_EXTRACTION_PROMPT_TEMPLATE's Step 2
    worked example), returns the three-way split. Returns None if it
    doesn't match closely enough to be confident, leaving the entry as
    a genuine plain career_highlights line untouched.
    """
    if " - " not in title:
        return None
    company, rest = title.split(" - ", 1)
    if ": " not in rest:
        return None
    award_title, description = rest.split(": ", 1)
    company, award_title, description = company.strip(), award_title.strip(), description.strip()
    if not company or not award_title or not description:
        return None
    if len(award_title.split()) > _MAX_KEY_ACHIEVEMENT_TITLE_WORDS:
        return None
    return {"company": company, "title": award_title, "description": description}


def _reclassify_misplaced_key_achievements(
    career_highlights: list[dict[str, str | None]],
) -> tuple[list[dict[str, str | None]], list[dict[str, str | None]]]:
    """Moves a career_highlights entry into key_achievements if its
    "title" is really an unsplit "Company - Award Name: Description"
    line — the model wrote the WHOLE line into "title" with "company"
    and "description" both left null, instead of recognizing the shape
    and splitting it per the prompt's own Step 2 rule.

    Real bug caught live on qwen2.5:3b: three genuine "Company - Award:
    Description" recognition lines (e.g. "Bank of America - Honorary
    Mention: Recognized for training 2,000+ employees on Agile
    delivery") all landed in career_highlights as single unsplit
    strings, leaving key_achievements empty even though the resume had
    real award content. Only entries with company AND description both
    null are candidates — a career_highlights entry the model already
    populated those fields for is a different, less suspicious shape
    and is left alone.
    """
    kept_highlights: list[dict[str, str | None]] = []
    reclassified: list[dict[str, str | None]] = []
    for item in career_highlights:
        if item["company"] is not None or item["description"] is not None:
            kept_highlights.append(item)
            continue
        split = _split_key_achievement(str(item["title"]))
        if split is None:
            kept_highlights.append(item)
            continue
        reclassified.append(
            {
                "title": split["title"],
                "company": split["company"],
                "description": split["description"],
                "occurred_on": item["occurred_on"],
            }
        )
    return kept_highlights, reclassified


def _unreverse_skill_name_category(
    skills: list[dict[str, str | None]],
) -> list[dict[str, str | None]]:
    """Swaps "name" and "category" back for a skill entry where they've
    been reversed — a subheading (e.g. "Agile & Scaling") written into
    "name" instead of "category", with the actual individual skill
    (e.g. "SAFe 6") written into "category" instead.

    Real bug caught live on qwen2.5:3b, and a striking case of the
    prompt's own worked example leaking into a weak model's output: the
    prompt has an explicit worked example showing this EXACT reversal
    as one of the wrong outputs to avoid — literally
    `{"name": "Agile & Scaling", "category": "SAFe 6"}` — and the model
    reproduced that precise wrong shape for real, on a resume whose own
    "CORE COMPETENCIES" section genuinely uses "Agile & Scaling" as one
    of its subheadings. Whether that's the model copying the prompt's
    own illustrative text or just genuinely confusing which field is
    which, an explicit negative example clearly wasn't enough to
    prevent it, so this is decided deterministically instead.

    Detection doesn't need the source text at all — it uses a simple,
    reliable property of a REVERSED list: a subheading is shared by
    several individual skills, so it legitimately repeats across
    entries; an individual skill name essentially never does. Whichever
    field value repeats across 2+ entries is therefore the subheading,
    regardless of which JSON key the model put it under — if that
    repeated value is sitting in "name" (with "category" holding the
    entry-specific value instead), the two are swapped back.
    """
    name_counts: dict[str, int] = {}
    for skill in skills:
        name = skill["name"]
        if isinstance(name, str):
            name_counts[name] = name_counts.get(name, 0) + 1

    fixed: list[dict[str, str | None]] = []
    for skill in skills:
        name, category = skill["name"], skill["category"]
        if isinstance(name, str) and name_counts.get(name, 0) > 1 and category:
            fixed.append({"name": category, "category": name})
        else:
            fixed.append(skill)
    return fixed


def _duplicates_an_experience_bullet(
    candidate: str, experience: list[dict[str, str | None]]
) -> bool:
    """True if `candidate` is already fully captured inside one of the
    experience entries' own "description" text. A resume bullet
    genuinely belonging to a specific role's description sometimes also
    gets copied into "career_highlights"/"key_achievements" as a
    separate entry — observed live on a real resume — even though the
    prompt explicitly says highlights/achievements are separate from
    per-role bullets. Rather than only asking the model not to do this,
    this catches it deterministically: real content passes the
    _appears_in_source check above (it IS in the resume), so it needs
    its own check.
    """
    normalized = _normalize_for_source_check(candidate)
    if len(normalized) < _MIN_LENGTH_FOR_SOURCE_VERIFICATION:
        return False
    for item in experience:
        description = item.get("description")
        if isinstance(description, str) and normalized in _normalize_for_source_check(description):
            return True
    return False


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


def _normalize_extracted_data(parsed: dict[str, object], raw_text: str) -> dict[str, object]:
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

    Two more deterministic checks, added after prompt-only fixes for the
    same failure modes were each observed live to fail on a small local
    model, even after being explicitly instructed against: (1) "skills"
    entries that duplicate a "certifications" name are dropped — a
    resume with no dedicated skills section was observed reusing the
    just-extracted certifications list to fill "skills" anyway, twice,
    despite the prompt explicitly saying an empty list is correct there.
    (2) "career_highlights"/"key_achievements" entries are dropped
    unless their text can actually be found in the resume's own raw
    text, AND aren't already fully contained in an experience entry's
    own description — the first catches a genuine hallucination (the
    model reproducing this exact prompt's own fictional worked example
    almost verbatim instead of leaving the list empty), the second
    catches a real resume bullet legitimately extracted into
    "experience" also getting duplicated into a separate highlight/
    achievement entry, which the prompt explicitly prohibits but a weak
    model did anyway.
    """
    raw_text_normalized = _normalize_for_source_check(raw_text)
    bulleted_source_lines = _bulleted_source_lines_normalized(raw_text)

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
    skills = _unreverse_skill_name_category(skills)
    # Deterministic override, not a drop-detection check like the one
    # above: a resume with no Skills/Core Competencies heading anywhere
    # gets an empty skills list regardless of what the model returned —
    # see skills_section_detector.py's docstring for the real, live bug
    # this closes (noun phrases mined out of Executive Summary prose,
    # chopped into fake atomic "skill" entries).
    if not has_dedicated_skills_section(raw_text):
        skills = []

    def _cleaned_description(raw: object) -> str | None:
        description = _clean_str(raw)
        if description is None:
            return None
        return _restore_bullet_markers(description, bulleted_source_lines)

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
                "description": _cleaned_description(item.get("description")),
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
                "description": _cleaned_description(item.get("description")),
            }
        )
    _check_dropped_section("education", raw_education, len(education))

    raw_certifications = _as_list(parsed.get("certifications"))
    certifications = []
    for item in raw_certifications:
        if not isinstance(item, dict):
            continue
        name = _clean_str(item.get("name"))
        if not name:
            continue
        # A missing/null issuer defaults to the honest fallback in code
        # rather than dropping the whole entry — a real bug caught live:
        # a weaker model (qwen2.5:3b) correctly extracted every
        # certification name but wrote null for issuing_organization on
        # all of them instead of the literal "Not specified in resume"
        # string the prompt asks for, which used to silently discard
        # every certification (requiring a non-empty issuer to even keep
        # the entry) and trip the "all dropped" safety check, failing
        # the whole upload. Now that "not specified" is the expected
        # common case rather than a rare fallback (see
        # _verified_issuer's docstring), a missing issuer is not a
        # reason to lose the certification name itself.
        issuer = _clean_str(item.get("issuing_organization")) or _NOT_SPECIFIED_ISSUER
        certifications.append(
            {
                "name": name,
                "issuing_organization": _verified_issuer(issuer, raw_text_normalized),
                "issue_date": _clean_date(item.get("issue_date")),
                "expiration_date": _clean_date(item.get("expiration_date")),
                "credential_id": _clean_str(item.get("credential_id")),
                "credential_url": _clean_str(item.get("credential_url")),
            }
        )
    _check_dropped_section("certifications", raw_certifications, len(certifications))
    # Deterministic override, mirroring the skills-section rule above: a
    # resume with no dedicated Certifications/Licenses heading anywhere
    # gets an empty certifications list regardless of what the model
    # returned. Real bug caught live: a resume with only a Professional
    # Experience section (no Certifications section at all) produced 7
    # fake certifications — the model confused "certification programs
    # this person DELIVERS to others" (a training/coaching service,
    # described in an experience bullet like "Delivered SAFe®
    # certification programs, including Leading SAFe, Scrum Master,
    # ...") with "certifications this person HOLDS". Reuses
    # certification_line_parser's own heading-detection rather than a
    # new one — it already returns [] when no such heading exists.
    if not extract_certification_names(raw_text):
        certifications = []

    if certifications:
        certification_names_normalized = [
            _normalize_certification_name_for_matching(str(c["name"])) for c in certifications
        ]
        # Substring either direction, not exact-set membership — a real
        # bug caught live: the model can paraphrase the same credential
        # slightly differently between the two fields (e.g. skill "SAFe
        # 6 Practice Consultant" vs. certification "Advanced SAFe 6
        # Practice Consultant"), which an exact match silently let
        # through into Core Competencies. Same loosened-matching
        # rationale already established by _missing_certification_names
        # above, applied here in the opposite direction.
        #
        # Short names are exempted entirely (even from the exact-match
        # case) — real regression caught live: a genuine resume that
        # deliberately lists "LeSS" and "SAFe 6" as BOTH a Core
        # Competencies skill AND (separately) a held certification had
        # both wrongly dropped from skills — "LeSS" via an exact name
        # collision, "SAFe 6" as a coincidental substring of the much
        # longer "Advanced SAFe 6 Practice Consultant". A short
        # acronym/term matching a certification name is much more likely
        # to be exactly this legitimate dual-mention than a genuine
        # duplicate — the same false-positive risk already guarded
        # against for issuer verification above, applied here too.
        skills = [
            s
            for s in skills
            if len(_normalize_certification_name_for_matching(str(s["name"])))
            < _MIN_LENGTH_FOR_SOURCE_VERIFICATION
            or not any(
                _normalize_certification_name_for_matching(str(s["name"])) == cert_name
                or _normalize_certification_name_for_matching(str(s["name"])) in cert_name
                or cert_name in _normalize_certification_name_for_matching(str(s["name"]))
                for cert_name in certification_names_normalized
            )
        ]

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

    # Reclassification runs BEFORE the content-verification filters below
    # so both final lists get filtered uniformly, regardless of which
    # list an entry originally landed in.
    career_highlights, misplaced = _reclassify_misplaced_key_achievements(career_highlights)
    key_achievements = [*key_achievements, *misplaced]

    # Content-verification filters run AFTER the schema-mismatch check
    # above, deliberately — these drop items for being unverifiable or
    # duplicates, a different signal from "wrong field names", and must
    # never be mistaken for the all-dropped schema-mismatch case that
    # check exists to catch.
    career_highlights = [
        item
        for item in career_highlights
        if _appears_in_source(str(item["title"]), raw_text_normalized)
        and not _duplicates_an_experience_bullet(str(item["title"]), experience)
    ]
    key_achievements = [
        item
        for item in key_achievements
        if _appears_in_source(str(item["title"]), raw_text_normalized)
        and not _duplicates_an_experience_bullet(str(item["title"]), experience)
    ]

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
