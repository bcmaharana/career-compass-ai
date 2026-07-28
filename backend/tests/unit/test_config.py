"""Unit test for Settings — no infrastructure required.

Demonstrates the unit-test pattern: pure Python, no DB, no HTTP client,
fast enough to run on every save.
"""

from __future__ import annotations

import pytest

from app.core.config import Settings, get_settings


@pytest.mark.unit
def test_settings_have_sensible_defaults() -> None:
    settings = Settings(_env_file=None)  # type: ignore[call-arg]

    assert settings.app_name == "career-compass-ai"
    assert settings.jwt_algorithm == "HS256"
    assert settings.jwt_access_token_expire_minutes == 60


@pytest.mark.unit
def test_get_settings_is_cached() -> None:
    first = get_settings()
    second = get_settings()

    assert first is second  # lru_cache should return the same instance


@pytest.mark.unit
def test_is_production_flag_reflects_app_env() -> None:
    prod_settings = Settings(_env_file=None, app_env="production")  # type: ignore[call-arg]
    local_settings = Settings(_env_file=None, app_env="local")  # type: ignore[call-arg]

    assert prod_settings.is_production is True
    assert local_settings.is_production is False
    assert local_settings.is_local is True
