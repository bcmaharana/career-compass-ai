"""Request/response schemas for the Dashboard System Status widget."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class RateLimitInfoResponse(BaseModel):
    """Groq's rate-limit headers off its last real API call this backend
    process made — see GroqRateLimitSnapshot's docstring for why
    request/token track separate (daily/per-minute) buckets and why the
    reset fields are unparsed duration strings, not seconds.
    """

    limit_requests: int | None
    remaining_requests: int | None
    reset_requests: str | None
    limit_tokens: int | None
    remaining_tokens: int | None
    reset_tokens: str | None
    observed_at: datetime


class ServiceStatusResponse(BaseModel):
    name: str
    label: str
    status: str
    detail: str | None
    fix_command: str | None
    rate_limit: RateLimitInfoResponse | None = None


class SystemStatusResponse(BaseModel):
    services: list[ServiceStatusResponse]
    checked_at: datetime
