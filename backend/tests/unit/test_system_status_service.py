"""Unit tests for SystemStatusService (Dashboard System Status widget).

Checker functions are constructor-injected fakes, the same
fake-injection convention every other service in this codebase uses via
its repository Protocol — see SystemStatusService's own docstring.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.adapters.ai_providers.groq_provider import GroqRateLimitSnapshot
from app.adapters.system_status.checkers import ServiceCheckResult
from app.application.system_status.system_status_service import SystemStatusService
from app.core.config import Settings


def _settings() -> Settings:
    return Settings(_env_file=None)  # type: ignore[call-arg]


async def _up() -> ServiceCheckResult:
    return ServiceCheckResult(status="up")


async def _up_with_settings(settings: Settings) -> ServiceCheckResult:
    return ServiceCheckResult(status="up")


def _up_sync(settings: Settings) -> ServiceCheckResult:
    return ServiceCheckResult(status="up", detail="API key configured")


@pytest.mark.unit
class TestSystemStatusService:
    async def test_all_up(self) -> None:
        service = SystemStatusService(
            _settings(),
            postgres_check=_up,
            redis_check=_up_with_settings,
            minio_check=_up_with_settings,
            ollama_check=_up_with_settings,
            anthropic_check=_up_sync,
            groq_check=_up_sync,
        )

        result = await service.check_all()

        assert {s.name for s in result.services} == {
            "postgres",
            "redis",
            "minio",
            "ollama",
            "anthropic",
            "groq",
        }
        assert all(s.status == "up" for s in result.services)
        assert all(s.fix_command is None for s in result.services)

    async def test_one_service_down_does_not_affect_others(self) -> None:
        async def redis_down(settings: Settings) -> ServiceCheckResult:
            return ServiceCheckResult(status="down", detail="Connection refused")

        service = SystemStatusService(
            _settings(),
            postgres_check=_up,
            redis_check=redis_down,
            minio_check=_up_with_settings,
            ollama_check=_up_with_settings,
            anthropic_check=_up_sync,
        )

        result = await service.check_all()
        by_name = {s.name: s for s in result.services}

        assert by_name["redis"].status == "down"
        assert by_name["redis"].detail == "Connection refused"
        assert by_name["redis"].fix_command == (
            "docker compose -f infra/docker-compose.yml restart redis"
        )
        # Every other service is unaffected.
        assert by_name["postgres"].status == "up"
        assert by_name["minio"].status == "up"
        assert by_name["ollama"].status == "up"
        assert by_name["anthropic"].status == "up"

    async def test_ollama_down_reports_non_docker_fix_command(self) -> None:
        async def ollama_down(settings: Settings) -> ServiceCheckResult:
            return ServiceCheckResult(status="down", detail="All connection attempts failed")

        service = SystemStatusService(
            _settings(),
            postgres_check=_up,
            redis_check=_up_with_settings,
            minio_check=_up_with_settings,
            ollama_check=ollama_down,
            anthropic_check=_up_sync,
        )

        result = await service.check_all()
        ollama_status = next(s for s in result.services if s.name == "ollama")

        assert ollama_status.status == "down"
        # Not a docker command - Ollama runs on the host, outside Compose.
        assert "docker" not in ollama_status.fix_command
        assert "ollama serve" in ollama_status.fix_command

    async def test_anthropic_not_configured(self) -> None:
        def anthropic_not_configured(settings: Settings) -> ServiceCheckResult:
            return ServiceCheckResult(status="not_configured", detail="ANTHROPIC_API_KEY is not set")

        service = SystemStatusService(
            _settings(),
            postgres_check=_up,
            redis_check=_up_with_settings,
            minio_check=_up_with_settings,
            ollama_check=_up_with_settings,
            anthropic_check=anthropic_not_configured,
        )

        result = await service.check_all()
        anthropic_status = next(s for s in result.services if s.name == "anthropic")

        assert anthropic_status.status == "not_configured"
        assert anthropic_status.fix_command is not None

    async def test_groq_not_configured(self) -> None:
        def groq_not_configured(settings: Settings) -> ServiceCheckResult:
            return ServiceCheckResult(status="not_configured", detail="GROQ_API_KEY is not set")

        service = SystemStatusService(
            _settings(),
            postgres_check=_up,
            redis_check=_up_with_settings,
            minio_check=_up_with_settings,
            ollama_check=_up_with_settings,
            anthropic_check=_up_sync,
            groq_check=groq_not_configured,
        )

        result = await service.check_all()
        groq_status = next(s for s in result.services if s.name == "groq")

        assert groq_status.status == "not_configured"
        assert groq_status.fix_command is not None

    async def test_groq_rate_limit_is_reported_when_available(self) -> None:
        snapshot = GroqRateLimitSnapshot(
            limit_requests=1000,
            remaining_requests=827,
            reset_requests="2m59.56s",
            limit_tokens=12000,
            remaining_tokens=11850,
            reset_tokens="7.66s",
            observed_at=datetime.now(UTC),
        )

        def groq_with_usage(settings: Settings) -> ServiceCheckResult:
            return ServiceCheckResult(
                status="up", detail="API key configured", rate_limit=snapshot
            )

        service = SystemStatusService(
            _settings(),
            postgres_check=_up,
            redis_check=_up_with_settings,
            minio_check=_up_with_settings,
            ollama_check=_up_with_settings,
            anthropic_check=_up_sync,
            groq_check=groq_with_usage,
        )

        result = await service.check_all()
        groq_status = next(s for s in result.services if s.name == "groq")

        assert groq_status.rate_limit is snapshot
        assert groq_status.rate_limit.remaining_requests == 827

    async def test_groq_rate_limit_absent_before_any_real_call(self) -> None:
        # _up_sync (used as the default groq_check fake throughout this
        # file) reports no rate_limit at all - the same "no usage data
        # yet this session" state a freshly-restarted backend is in
        # before its first real Groq call.
        service = SystemStatusService(
            _settings(),
            postgres_check=_up,
            redis_check=_up_with_settings,
            minio_check=_up_with_settings,
            ollama_check=_up_with_settings,
            anthropic_check=_up_sync,
            groq_check=_up_sync,
        )

        result = await service.check_all()
        groq_status = next(s for s in result.services if s.name == "groq")

        assert groq_status.rate_limit is None

    async def test_checked_at_is_populated(self) -> None:
        service = SystemStatusService(
            _settings(),
            postgres_check=_up,
            redis_check=_up_with_settings,
            minio_check=_up_with_settings,
            ollama_check=_up_with_settings,
            anthropic_check=_up_sync,
        )

        result = await service.check_all()

        assert result.checked_at is not None
