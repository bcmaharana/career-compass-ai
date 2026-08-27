"""Fetches the full profile field set from Platform Identity at
platform-handoff time, using the very platform token PlatformHandoffService
just verified as the bearer.

Deliberately a one-time call at an already-synchronous, already-network
-touching event (the handoff itself), not a new per-request dependency —
ADR-001's "no live network call back per request" is about ordinary API
traffic, which this isn't. Best-effort: a failure here (network error,
unconfigured base URL, unexpected response shape) returns None rather
than raising — JIT provisioning must still succeed with whatever local
data already exists (or defaults, on first-ever creation) even if the
Hub happens to be unreachable at that exact moment.
"""

from __future__ import annotations

from dataclasses import dataclass

import httpx

from app.core.config import get_settings


@dataclass(frozen=True, slots=True)
class PlatformProfileFields:
    salutation: str | None
    first_name: str
    middle_name: str | None
    last_name: str
    handle: str | None
    phone_number: str | None
    country: str | None
    language: str | None
    address_line1: str | None
    address_line2: str | None
    city: str | None
    state: str | None
    postal_code: str | None
    visa_status: str | None
    linkedin_url: str | None
    other_professional_url: str | None


async def fetch_platform_profile(platform_token: str) -> PlatformProfileFields | None:
    settings = get_settings()
    if not settings.platform_identity_base_url:
        return None

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(
                f"{settings.platform_identity_base_url.rstrip('/')}/api/v1/auth/me/profile",
                headers={"Authorization": f"Bearer {platform_token}"},
            )
            response.raise_for_status()
            body = response.json()
    except (httpx.HTTPError, ValueError):
        return None

    try:
        return PlatformProfileFields(
            salutation=body["salutation"],
            first_name=body["first_name"],
            middle_name=body["middle_name"],
            last_name=body["last_name"],
            handle=body["handle"],
            phone_number=body["phone_number"],
            country=body["country"],
            language=body["language"],
            address_line1=body["address_line1"],
            address_line2=body["address_line2"],
            city=body["city"],
            state=body["state"],
            postal_code=body["postal_code"],
            visa_status=body["visa_status"],
            linkedin_url=body["linkedin_url"],
            other_professional_url=body["other_professional_url"],
        )
    except KeyError:
        return None
