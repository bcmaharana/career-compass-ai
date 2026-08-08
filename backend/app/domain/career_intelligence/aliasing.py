"""Pure alias-normalization logic — no framework, no database.

Mirrors app/domain/identity/authorization.py's pattern: domain logic that
isn't a dataclass but is still framework-free business logic, unit
tested without a database (see tests/unit/test_alias_normalization.py).
"""

from __future__ import annotations

import re

_DISALLOWED_CHARACTERS = re.compile(r"[^\w\s-]")
_WHITESPACE_RUN = re.compile(r"\s+")


def normalize_alias_text(text: str) -> str:
    """Lowercase, collapse internal whitespace, strip punctuation except
    internal hyphens — per cikg-skill-ontology.md's normalization rule.

    Deliberately simple (no stemming/lemmatization): "Node.js" normalizes
    to "nodejs" (distinct from "Node js" -> "node js"), and "co-founder"
    keeps its hyphen rather than collapsing to "cofounder". Aggressive
    normalization risks false-positive matches across genuinely different
    skills more than it helps — ambiguous cases are what human-confirmed
    aliases (cikg-content-governance.md) are for, not this function.
    """
    lowered = text.lower()
    without_punctuation = _DISALLOWED_CHARACTERS.sub("", lowered)
    return _WHITESPACE_RUN.sub(" ", without_punctuation).strip()
