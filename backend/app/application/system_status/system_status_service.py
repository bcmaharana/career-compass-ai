"""Dashboard System Status widget's application service.

Checks every runtime dependency this app has (Postgres, Redis, MinIO,
Ollama, Anthropic, Groq) and reports live status. Deliberately status-only —
no server-side restart execution. See
app/adapters/system_status/checkers.py's module docstring for why:
actually restarting Postgres/Redis/MinIO/the backend itself would
require mounting the Docker socket into the backend container
(effectively root on the host), and Ollama runs on the host outside
Docker Compose entirely, so the backend has no path to restart it at
all without a net-new host-side helper component. Both explicit,
confirmed product decisions, not oversights.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime

from app.adapters.ai_providers.groq_provider import GroqRateLimitSnapshot
from app.adapters.system_status.checkers import (
    ServiceCheckResult,
    check_anthropic,
    check_groq,
    check_minio,
    check_ollama,
    check_postgres,
    check_redis,
)
from app.core.config import Settings

_POSTGRES_FIX = "docker compose -f infra/docker-compose.yml restart postgres"
_REDIS_FIX = "docker compose -f infra/docker-compose.yml restart redis"
_MINIO_FIX = "docker compose -f infra/docker-compose.yml restart minio"
_OLLAMA_FIX = "ollama serve   (or launch the Ollama app)"
_ANTHROPIC_FIX = "Set ANTHROPIC_API_KEY in backend/.env, then restart the backend container"
_GROQ_FIX = "Set GROQ_API_KEY in backend/.env, then restart the backend container"


@dataclass(slots=True)
class ServiceStatus:
    name: str
    label: str
    status: str  # "up" | "down" | "not_configured"
    detail: str | None
    fix_command: str | None  # only set when status != "up"
    rate_limit: GroqRateLimitSnapshot | None = None  # only ever set for "groq"


@dataclass(slots=True)
class SystemStatusResult:
    services: list[ServiceStatus]
    checked_at: datetime


class SystemStatusService:
    """Checker functions are constructor-injected (defaulting to the
    real adapters in checkers.py) purely so unit tests can substitute
    fakes per-service — the same fake-injection convention every other
    service in this codebase uses via its repository Protocol; there's
    no repository here, so the checker callables fill that role instead.
    """

    def __init__(
        self,
        settings: Settings,
        *,
        postgres_check: Callable[[], Awaitable[ServiceCheckResult]] = check_postgres,
        redis_check: Callable[[Settings], Awaitable[ServiceCheckResult]] = check_redis,
        minio_check: Callable[[Settings], Awaitable[ServiceCheckResult]] = check_minio,
        ollama_check: Callable[[Settings], Awaitable[ServiceCheckResult]] = check_ollama,
        anthropic_check: Callable[[Settings], ServiceCheckResult] = check_anthropic,
        groq_check: Callable[[Settings], ServiceCheckResult] = check_groq,
    ) -> None:
        self._settings = settings
        self._postgres_check = postgres_check
        self._redis_check = redis_check
        self._minio_check = minio_check
        self._ollama_check = ollama_check
        self._anthropic_check = anthropic_check
        self._groq_check = groq_check

    async def check_all(self) -> SystemStatusResult:
        postgres_result, redis_result, minio_result, ollama_result = await asyncio.gather(
            self._postgres_check(),
            self._redis_check(self._settings),
            self._minio_check(self._settings),
            self._ollama_check(self._settings),
        )
        anthropic_result = self._anthropic_check(self._settings)
        groq_result = self._groq_check(self._settings)

        services = [
            self._to_status("postgres", "PostgreSQL", postgres_result, _POSTGRES_FIX),
            self._to_status("redis", "Redis", redis_result, _REDIS_FIX),
            self._to_status("minio", "MinIO", minio_result, _MINIO_FIX),
            self._to_status("ollama", "Ollama", ollama_result, _OLLAMA_FIX),
            self._to_status("anthropic", "Anthropic API", anthropic_result, _ANTHROPIC_FIX),
            self._to_status("groq", "Groq API", groq_result, _GROQ_FIX),
        ]
        return SystemStatusResult(services=services, checked_at=datetime.now(UTC))

    @staticmethod
    def _to_status(
        name: str, label: str, result: ServiceCheckResult, fix_command: str
    ) -> ServiceStatus:
        return ServiceStatus(
            name=name,
            label=label,
            status=result.status,
            detail=result.detail,
            fix_command=None if result.status == "up" else fix_command,
            rate_limit=result.rate_limit,
        )
