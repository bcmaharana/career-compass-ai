"""Live reachability probes for this app's runtime dependencies.

Only place SQLAlchemy/redis/httpx get imported for this purpose — every
checker below deliberately never raises. A dependency being unreachable
is an expected, common outcome here (that's the whole point of the
check), not an error condition for the caller to handle — same "one bad
item doesn't take the rest down" philosophy as ResumeMergeService's
per-item skip logic elsewhere in this codebase. Each function returns a
ServiceCheckResult describing what it found instead.

No domain/repository layer backs this module — there's no persisted,
tenant-owned entity here, just live pings against five infra endpoints,
so the usual domain/repository split every other feature uses would be
pure overhead. A deliberate, narrow exception to the layering rule.
"""

from __future__ import annotations

from dataclasses import dataclass

import httpx
import redis.asyncio as redis
from sqlalchemy import text

from app.adapters.ai_providers.groq_provider import (
    GroqRateLimitSnapshot,
    get_last_rate_limit_snapshot,
)
from app.adapters.db.base import engine
from app.core.config import Settings

_TIMEOUT_SECONDS = 3.0


@dataclass(slots=True)
class ServiceCheckResult:
    status: str  # "up" | "down" | "not_configured"
    detail: str | None = None
    # Only ever populated for Groq today - see check_groq(). Generic on
    # this shared result type rather than a Groq-specific return type so
    # SystemStatusService doesn't need a special case for one service.
    rate_limit: GroqRateLimitSnapshot | None = None


async def check_postgres() -> ServiceCheckResult:
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return ServiceCheckResult(status="up")
    except Exception as exc:  # noqa: BLE001 - deliberately broad, see module docstring
        return ServiceCheckResult(status="down", detail=str(exc))


async def check_redis(settings: Settings) -> ServiceCheckResult:
    # redis-py ships without a py.typed marker for this constructor, so
    # mypy sees it as untyped even under strict mode — a genuine
    # third-party stub gap, not a real type-safety issue here.
    client = redis.from_url(  # type: ignore[no-untyped-call]
        settings.redis_url, socket_connect_timeout=_TIMEOUT_SECONDS
    )
    try:
        await client.ping()
        return ServiceCheckResult(status="up")
    except Exception as exc:  # noqa: BLE001
        return ServiceCheckResult(status="down", detail=str(exc))
    finally:
        await client.aclose()


async def check_minio(settings: Settings) -> ServiceCheckResult:
    url = f"{settings.object_storage_endpoint}/minio/health/live"
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT_SECONDS) as client:
            response = await client.get(url)
            response.raise_for_status()
        return ServiceCheckResult(status="up")
    except Exception as exc:  # noqa: BLE001
        return ServiceCheckResult(status="down", detail=str(exc))


async def check_ollama(settings: Settings) -> ServiceCheckResult:
    url = f"{settings.ollama_base_url}/api/tags"
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT_SECONDS) as client:
            response = await client.get(url)
            response.raise_for_status()
        return ServiceCheckResult(status="up")
    except Exception as exc:  # noqa: BLE001
        return ServiceCheckResult(status="down", detail=str(exc))


def check_anthropic(settings: Settings) -> ServiceCheckResult:
    # No live API call — every request costs real tokens/quota, and this
    # gets polled repeatedly from the Dashboard for no real benefit.
    # Configured-vs-not is the useful signal here; actual reachability
    # is exercised for real the moment a chat/coach/resume-extraction
    # call is made.
    if settings.anthropic_api_key:
        return ServiceCheckResult(status="up", detail="API key configured")
    return ServiceCheckResult(status="not_configured", detail="ANTHROPIC_API_KEY is not set")


def check_groq(settings: Settings) -> ServiceCheckResult:
    # Same reasoning as check_anthropic — Groq's free tier is rate-
    # limited (30 RPM/14,400 RPD), not worth spending on a 15s dashboard
    # poll just to prove reachability. rate_limit below costs nothing
    # extra either: it's whatever groq_provider.py already captured off
    # the headers of the last real chat-completion call this backend
    # process made, not a fresh probe.
    if not settings.groq_api_key:
        return ServiceCheckResult(status="not_configured", detail="GROQ_API_KEY is not set")
    return ServiceCheckResult(
        status="up", detail="API key configured", rate_limit=get_last_rate_limit_snapshot()
    )
