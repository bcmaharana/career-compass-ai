"""Deterministic backstop for resume headline extraction.

Observed live: even after the extraction prompt was fixed to explicitly
tell the model not to skip "headline" just because it overlaps with
"summary" (see RESUME_EXTRACTION_PROMPT_TEMPLATE's "headline" field
guidance in scripts/seed_platform_defaults.py), a small local model
(qwen2.5:7b) still returned a null headline on the exact resume that
fix targeted — a genuine model-capability limitation, not a remaining
prompt-wording gap, since a much larger hosted model (Groq's
llama-3.3-70b-versatile) extracted the same line correctly.

Same reasoning as certification_line_parser.py: rather than continuing
to tune prompt wording against a model that isn't reliably following a
subtle instruction, use the resume's own layout as ground truth. A
resume's headline, when present, is conventionally the line directly
under the person's name and before the first section heading — this
never requires understanding the *content* of that line, only its
position, which is a much easier signal for deterministic code than
for an LLM already juggling a long, multi-section extraction task.
"""

from __future__ import annotations

import re

_SECTION_HEADING_PHRASES = {
    "summary",
    "executive summary",
    "professional summary",
    "career summary",
    "profile",
    "about",
    "objective",
    "experience",
    "professional experience",
    "work experience",
    "employment history",
    "education",
    "certifications",
    "licenses",
    "licenses & certifications",
    "licenses and certifications",
    "skills",
    "core competencies",
    "technical skills",
    "areas of expertise",
    "career highlights",
    "highlights",
    "key achievements",
    "achievements",
    "awards",
    "recognition",
    "recognitions",
    "projects",
    "publications",
    "volunteer",
    "volunteering",
    "references",
    "contact",
}

_EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_PHONE_RE = re.compile(r"\+?\d[\d\-.\s()]{7,}\d")
_URL_RE = re.compile(r"https?://|linkedin\.com|www\.", re.IGNORECASE)

_MIN_HEADLINE_LENGTH = 3
_MAX_HEADLINE_LENGTH = 200
_MAX_LINES_AFTER_NAME_TO_SCAN = 3


def _is_known_section_heading_phrase(line: str) -> bool:
    """Unambiguous: only matches an exact phrase from the known-headings
    list, never the broader short-all-caps heuristic below — a person's
    name is just as commonly short and all-caps on a resume ("JANE DOE",
    "BISHNU MAHARANA"), so that heuristic can't safely be applied to
    line 0, where it's still genuinely ambiguous whether the line is a
    name or a heading. An exact phrase match has no such ambiguity.
    """
    stripped = line.strip().strip(":").strip()
    return bool(stripped) and stripped.lower() in _SECTION_HEADING_PHRASES


def _looks_like_section_heading(line: str) -> bool:
    stripped = line.strip().strip(":").strip()
    if not stripped:
        return False
    if stripped.lower() in _SECTION_HEADING_PHRASES:
        return True
    # A short, all-caps line (no lowercase letters at all) reads as a
    # section heading even if its exact wording isn't in the known-phrase
    # list above (resumes use plenty of heading variants) — but a long
    # all-caps line is more likely a name or an all-caps headline
    # ("SENIOR PRODUCT MANAGER"), so this only applies to short lines.
    # Only ever applied to candidate headline lines (after the assumed
    # name), never to line 0 itself — see _is_known_section_heading_phrase
    # for why that line needs the stricter, unambiguous check instead.
    if stripped == stripped.upper() and len(stripped.split()) <= 5 and any(
        c.isalpha() for c in stripped
    ):
        return True
    return False


def _looks_like_contact_line(line: str) -> bool:
    return bool(_EMAIL_RE.search(line) or _PHONE_RE.search(line) or _URL_RE.search(line))


def extract_headline_fallback(raw_text: str) -> str | None:
    """Returns the resume's own headline line, or None if none is found.

    Only ever called when the LLM's own "headline" came back null — see
    resume_extraction_service.py. Scans a small window of lines right
    after the (assumed) name line, skipping over contact-info lines
    (order varies: some resumes put contact info before the headline,
    some after) and stopping as soon as a section heading is reached
    (nothing past that point can be a headline). Deliberately
    conservative — a false "no headline found" is safe (matches today's
    behavior), a false positive (returning a contact line or a random
    sentence as the headline) is not, so the scan window is kept small
    and every candidate is checked against both the heading and
    contact-line patterns before being accepted.
    """
    lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
    if len(lines) < 2:
        return None

    # lines[0] is assumed to be the person's name and always skipped —
    # but only once it's confirmed to actually look like one. Real bug
    # caught live: a resume text that starts directly with a section
    # heading (e.g. a deliberately partial upload beginning mid-résumé
    # at "PROFESSIONAL EXPERIENCE", with no name/headline/contact block
    # above it at all) was skipped over unconditionally as "the name",
    # and the very next line — the first job's own "Company | Title |
    # Location | Dates" header — got returned as the "headline" instead.
    # If line 0 is itself already a heading, this resume simply doesn't
    # have the Name/Headline/Contact structure this function assumes,
    # and nothing after it should be guessed at either.
    if _is_known_section_heading_phrase(lines[0]):
        return None

    for line in lines[1 : 1 + _MAX_LINES_AFTER_NAME_TO_SCAN]:
        if _looks_like_section_heading(line):
            return None
        if _looks_like_contact_line(line):
            continue
        if _MIN_HEADLINE_LENGTH <= len(line) <= _MAX_HEADLINE_LENGTH:
            return line
    return None
