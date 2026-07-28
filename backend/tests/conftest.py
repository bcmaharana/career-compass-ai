"""Shared pytest fixtures.

Critical ordering: .env.test is loaded here, at module scope, before any
`app.*` module is imported anywhere in the test suite — including by
other fixture files. Settings are cached (see app.core.config.get_settings)
and several modules (app.adapters.db.base) create real engine objects at
*import* time, so if a test database URL isn't in the environment before
that first import happens, integration tests would silently run against
whatever DATABASE_URL the developer's shell happens to have set — which
could be the local dev database. Loading .env.test at the very top of
this file, before the `from app.main import app` below, is what
guarantees that never happens.
"""

from __future__ import annotations

import os
from collections.abc import AsyncGenerator
from pathlib import Path

from dotenv import load_dotenv

_TEST_ENV_PATH = Path(__file__).resolve().parent.parent / ".env.test"
load_dotenv(_TEST_ENV_PATH, override=True)

import pytest  # noqa: E402
import pytest_asyncio  # noqa: E402
from alembic.config import Config  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402

from alembic import command  # noqa: E402
from app.main import app  # noqa: E402 -- must follow load_dotenv above


def _alembic_config() -> Config:
    backend_dir = Path(__file__).resolve().parent.parent
    cfg = Config(str(backend_dir / "alembic.ini"))
    cfg.set_main_option("script_location", str(backend_dir / "alembic"))
    return cfg


@pytest.fixture(scope="session")
def apply_migrations_and_seed() -> None:
    """Runs once per test session: applies all migrations to the test
    database (career_compass_test, per .env.test) and seeds the global
    platform permissions/roles every identity test depends on.

    Uses the real Alembic `command.upgrade` API (the same code path
    `alembic upgrade head` runs on the CLI) rather than creating tables
    directly from ORM metadata — this way, integration tests exercise the
    actual migration history, RLS policies included, not an idealized
    schema that skips them.
    """
    assert "career_compass_test" in os.environ["DATABASE_URL"], (
        "Refusing to run migrations: DATABASE_URL does not point at the "
        "test database. Check that .env.test loaded correctly."
    )

    command.upgrade(_alembic_config(), "head")

    # Imported here, not at module level, so DATABASE_URL is guaranteed
    # to already be pointed at the test DB before this module (which
    # creates its own engine at import time via app.adapters.db.base) is
    # first imported.
    import asyncio

    from scripts.seed_platform_defaults import seed_platform_defaults

    asyncio.run(seed_platform_defaults())


@pytest_asyncio.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    """An async HTTP client wired directly against the FastAPI app,
    without binding a real network port.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"
