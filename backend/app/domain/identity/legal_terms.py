"""Terms of Service / Privacy Policy version tracking.

A plain version string, not a full versioning/re-consent system — this
codebase has no requirement (yet) to re-prompt existing users when the
documents change, only to record which version a *new* signup agreed
to at the moment they did. Bump this string whenever the documents
change materially; the value itself has no meaning beyond being a
stable label future code (or a human) can compare against.
"""

from __future__ import annotations

CURRENT_TERMS_VERSION = "2026-08-11"
