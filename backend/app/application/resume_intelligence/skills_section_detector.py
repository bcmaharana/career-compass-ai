"""Deterministic check for whether a resume's extracted text has a
dedicated Skills/Core Competencies section at all.

Exists because of a real bug caught live: on a resume with no such
section (only Executive Summary, Certifications, and Professional
Experience), the LLM invented a "skills" list anyway by mining noun
phrases out of the Executive Summary's prose — chopping a sentence like
"Skilled in coaching executives, RTEs, Product Managers, Scrum Masters,
Product Owners, and engineering teams to align strategy with execution
through SAFe practices, Lean Portfolio Management, flow metrics, and
measurable outcome-based governance" into half a dozen fake atomic
"skill" entries, plus lifting a near-duplicate of the headline/first
certification name. A prompt instruction ("an empty skills array is
correct when no dedicated section exists") was already tried for this
exact failure mode and did not hold against qwen2.5:7b — per this
codebase's own established rule, a second failure of the same
prompt-only fix on the same failure mode means add a deterministic
backstop instead of tuning the prompt further.

Deliberately only answers "does a skills-like heading exist anywhere,"
not "what are the skills" — unlike certification_line_parser.py, there
is no reliable delimiter-based way to enumerate skill names themselves
(a real skills section can be a flat comma list, one-per-line, or
grouped under sub-headings), so this is used purely as a gate: if no
such heading is found, the model's entire "skills" output for this
resume is discarded rather than trusted.
"""

from __future__ import annotations

import re

_HEADING_STRIP_CHARS = ": -–—"

_BULLET_PREFIX_RE = re.compile(
    r"^[•\-*◦‣●○▪·»]\s+|^\d+[.)]\s+|^[a-zA-Z][.)]\s+"
)

# Matched against the WHOLE line (fullmatch, not search), same reasoning
# as certification_line_parser.py's own heading regex: a content line
# like "Skilled in coaching executives..." contains "skill" as a
# substring too, and must never be mistaken for a heading — a genuine
# heading is (almost) nothing but the heading phrase itself.
_SKILLS_HEADING_RE = re.compile(
    r"^(core|key|technical|professional|relevant)?\s*"
    r"(competenc(y|ies)|skills?|expertise)"
    r"(\s*(&|and)?\s*(competenc(y|ies)|skills?))?$"
    r"|^areas?\s+of\s+(expertise|skills?)$",
    re.IGNORECASE,
)


def has_dedicated_skills_section(raw_text: str) -> bool:
    """True if any line of `raw_text` (already-extracted plain text) is,
    on its own, recognizable as a Skills/Core Competencies/Areas of
    Expertise section heading. Never raises — a defensive gate, not
    something that should ever block extraction on its own.
    """
    for line in raw_text.split("\n"):
        text = _BULLET_PREFIX_RE.sub("", line).strip().strip(_HEADING_STRIP_CHARS).strip()
        if not text:
            continue
        if _SKILLS_HEADING_RE.match(text):
            return True
    return False
