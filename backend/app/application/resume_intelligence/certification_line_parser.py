"""Deterministic parser for the Certifications section of a resume's
extracted plain text.

Exists specifically because LLM-driven extraction has been observed,
live, silently dropping the same 2 certification names from a 13-item
flat list — across two unrelated model families (Groq's
llama-3.3-70b-versatile and a local qwen2.5:7b) and three different
prompt designs (a plain instruction, a self-reported count, a two-step
transcribe-then-enrich split). The common thread every time: both
dropped names ("Digital Product Management", "Generative AI Leader")
read like generic skill/role phrases rather than branded credentials,
unlike their neighbor on the same line ("Google Cloud Digital Leader",
always kept — it has an obvious vendor prefix). That pattern —
identical failure, different models, different prompt strategies —
points at a semantic classification bias in the model's own judgment of
"does this look like a real certification," not an attention/counting
gap. No amount of "count carefully" prompting argues a model out of a
bias it isn't aware it has.

This module sidesteps that judgment call entirely for the one thing
Python can do unambiguously: splitting a delimiter-separated list line
into items. It's used two ways by resume_extraction_service.py — as a
ground truth to decide whether the LLM's own certifications array looks
short (more reliable than trusting the model's self-report, which was
tried and observed live to just echo back whatever the model had
already written), and as a source of names to union in afterward, each
paired with the honest "not specified" issuer.

Deliberately NOT trying to also resolve issuing_organization here.
This module used to hand off to a separate LLM call for that (using
real-world knowledge, e.g. "PMP" -> "PMI") — removed after a real,
explicitly requested product change: issuing_organization is now only
ever taken from what the resume text itself states (see
resume_extraction_service.py's `_verified_issuer`), never inferred, so
there's nothing for a lookup call to legitimately backfill here either.
"""

from __future__ import annotations

import re

_HEADING_STRIP_CHARS = ": -–—"

# Recognizes a standalone line as a Certifications-section heading, in
# whatever synonymous wording a resume uses. Matched against the WHOLE
# line (fullmatch, not search) deliberately — a content line like "AWS
# Certified Solutions Architect" contains "certif" as a substring too,
# and must never be mistaken for a heading; a genuine heading is
# (almost) nothing but the heading phrase itself.
_CERTIFICATIONS_HEADING_RE = re.compile(
    r"^(licenses?\s*(&|and)?\s*)?"
    r"(certifications?|credentials?)"
    r"(\s*(&|and)?\s*(training|licenses?|credentials?))?$",
    re.IGNORECASE,
)

# Marks the END of the certifications section on the next line matching
# any OTHER recognized heading. Not an exhaustive list of every possible
# resume section title — an unrecognized heading wording just makes the
# section run a line or two long, which risks over-including a
# non-certification line, never silently dropping a real certification
# (the failure mode this module exists to catch).
_OTHER_SECTION_HEADING_RE = re.compile(
    r"^((executive|professional)\s+)?summary$"
    r"|^profile$|^about(\s+me)?$"
    r"|^((professional|work|relevant)\s+)?experience$|^employment(\s+history)?$"
    r"|^education(al\s+background)?$"
    r"|^(core\s+)?(competenc(y|ies)|skills?|technical\s+skills)$"
    r"|^(career\s+)?highlights$"
    r"|^(key\s+)?achievements$|^recognitions?$|^awards?$"
    r"|^projects?$|^publications?$|^languages?$|^references?$"
    r"|^(volunteer(ing)?|community)\s*(experience|work)?$|^interests?$"
    r"|^objective$",
    re.IGNORECASE,
)

# A leading bullet/numbering marker on its own line — "• " (Word's
# own bullet, per resume_text_extractor.py's "• " prefix
# convention), plus the common plain-text equivalents a hand-typed or
# non-Word-sourced resume might use instead.
_BULLET_PREFIX_RE = re.compile(
    r"^[•\-*◦‣●○▪·»]\s+|^\d+[.)]\s+|^[a-zA-Z][.)]\s+"
)

# Delimiters that are never plausibly part of a single certification
# name, so any occurrence is treated as a hard separator with no further
# checks — covers pipe, semicolon, slash, and every bullet-style
# character a resume might use to separate items *within* one line
# (not just at the start of one). Deliberately excludes "," and "&",
# which legitimately appear inside real names/sentences (see below).
_STRONG_DELIMITER_RE = re.compile(
    r"\s*[|;/•·‣●○▪»→]\s*"
)
_TRAILING_AND_RE = re.compile(r"\s*,?\s+and\s+", re.IGNORECASE)
_YEAR_RE = re.compile(r"^(19|20)\d{2}$")
_MAX_LIST_ITEM_WORDS = 6


def _is_heading_line(line: str) -> str | None:
    """Returns "certifications" / "other" / None, after stripping any
    bullet marker and trailing punctuation — headings are rarely
    bulleted in practice, but stripping defensively costs nothing.
    """
    text = _BULLET_PREFIX_RE.sub("", line).strip().strip(_HEADING_STRIP_CHARS).strip()
    if not text:
        return None
    if _CERTIFICATIONS_HEADING_RE.match(text):
        return "certifications"
    if _OTHER_SECTION_HEADING_RE.match(text):
        return "other"
    return None


def _split_certification_line(line: str) -> list[str]:
    """Splits one line of certifications-section text into individual
    certification names. Three shapes, tried in order:

    1. A "strong" delimiter (pipe, semicolon, slash, or a mid-line
       bullet character) anywhere in the line — unambiguous, split on
       every occurrence.
    2. Comma-separated with no strong delimiter — only treated as a flat
       list if EVERY resulting segment is short (<=6 words) and none is
       a bare year, which would instead indicate a single "Name, Issuer,
       Year" entry (e.g. "AWS Certified Solutions Architect - Amazon Web
       Services, 2023") rather than a list of names; a trailing " and "
       is normalized to a comma first so "PMP, CSM and SSGB" splits into
       three, not two.
    3. Anything else — the whole (bullet-stripped) line is one
       certification name, most commonly a resume that lists one
       certification per physical line already.
    """
    text = _BULLET_PREFIX_RE.sub("", line).strip()
    if not text:
        return []

    if _STRONG_DELIMITER_RE.search(text):
        return [p.strip() for p in _STRONG_DELIMITER_RE.split(text) if p.strip()]

    if "," in text:
        normalized = _TRAILING_AND_RE.sub(", ", text)
        parts = [p.strip() for p in normalized.split(",") if p.strip()]
        looks_like_flat_list = len(parts) >= 2 and all(
            len(p.split()) <= _MAX_LIST_ITEM_WORDS and not _YEAR_RE.match(p) for p in parts
        )
        if looks_like_flat_list:
            return parts
        return [text]

    return [text]


def extract_certification_names(raw_text: str) -> list[str]:
    """Best-effort, delimiter-based extraction of every individual
    certification name mentioned under a Certifications-like heading in
    `raw_text` (already-extracted plain text — see
    app/adapters/parsing/resume_text_extractor.py). Returns [] if no
    such heading is found. Never raises — this is a defensive ground
    truth, not something that should ever block extraction on its own.
    Order-preserving, deduped case-insensitively (a name repeated across
    two lines, or within one, counts once).
    """
    names: list[str] = []
    seen: set[str] = set()
    in_section = False

    for line in raw_text.split("\n"):
        heading = _is_heading_line(line)
        if heading == "certifications":
            in_section = True
            continue
        if heading == "other":
            in_section = False
            continue
        if not in_section:
            continue
        for name in _split_certification_line(line):
            key = name.lower()
            if key not in seen:
                seen.add(key)
                names.append(name)

    return names
