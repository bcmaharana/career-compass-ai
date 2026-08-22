"""Default public-sharing handle derivation (2026-08-22).

Pure text logic only — no DB access, no uniqueness checking (that's
PublicShareLinkService.get_or_create_key's job, since it's the one place
that actually knows how to check for a collision and append a numeric
suffix). Kept separate so the rule itself ("First/Middle/Last initials,
'0' if no middle name") is unit-testable without a database.
"""

from __future__ import annotations


def derive_default_handle_base(
    first_name: str, middle_name: str | None, last_name: str
) -> str:
    """First/Middle/Last initials, uppercased — "0" standing in for a
    missing middle name (direct 2026-08-22 request), e.g. "Bishnu Chandra
    Maharana" -> "BCM", "Bishnu Maharana" -> "B0M". Falls back to "X" for
    a name part that's somehow empty (shouldn't happen in practice —
    first_name/last_name are required fields — but a pure function should
    never raise on unexpected input it can trivially tolerate instead)."""

    def initial(name: str | None) -> str:
        stripped = (name or "").strip()
        return stripped[0].upper() if stripped else "X"

    first = initial(first_name)
    middle = middle_name.strip()[0].upper() if middle_name and middle_name.strip() else "0"
    last = initial(last_name)
    return f"{first}{middle}{last}"
