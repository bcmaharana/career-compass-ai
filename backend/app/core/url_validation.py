"""Small helpers for user-provided external links."""

from __future__ import annotations

from urllib.parse import urlsplit


def safe_http_url(value: str | None) -> str | None:
    if not value:
        return None
    try:
        parsed = urlsplit(value)
    except ValueError:
        return None
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.hostname:
        return None
    return value
