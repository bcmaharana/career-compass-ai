"""SQLAlchemy engine, session factory, and tenant-context helper.

This is the one module allowed to know about SQLAlchemy's async engine
setup. Everything else — repositories included — receives an already
-configured AsyncSession.

Tenant scoping (see docs/architecture/multi-tenancy-design.md): RLS
policies on tenant-owned tables check `current_setting('app.tenant_id')`.
`set_tenant_context` issues `SET LOCAL app.tenant_id = ...` on the current
transaction so every query within it is automatically scoped. This must
be called *before* any tenant-owned table is touched in that transaction.
"""

from __future__ import annotations

import asyncio
import sys
from collections.abc import AsyncGenerator
from uuid import UUID

from sqlalchemy import MetaData, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.config import get_settings

if sys.platform == "win32":
    # psycopg's async mode cannot run under Windows' default
    # ProactorEventLoop — it requires a SelectorEventLoop. This must be
    # set before any event loop is created (by pytest-asyncio, by
    # uvicorn, or by anything else), so it lives here: this module is
    # imported before any async engine or session is touched, by both
    # the application (app.main) and the test suite (tests.conftest).
    # Without this, every async database call fails on Windows with
    # "Psycopg cannot use the 'ProactorEventLoop' to run in async mode."
    # — this is a Windows/psycopg interaction, not specific to this
    # codebase; see https://www.psycopg.org/psycopg3/docs/advanced/async.html
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

_settings = get_settings()

engine = create_async_engine(
    _settings.database_url,
    pool_size=_settings.database_pool_size,
    pool_pre_ping=True,
)

async_session_factory = async_sessionmaker(engine, expire_on_commit=False)


NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """Declarative base for all ORM models.

    Naming convention (snake_case, explicit constraint names) is set here
    so Alembic autogenerate produces consistent, reviewable migration
    diffs rather than database-assigned default names.
    """

    metadata = MetaData(naming_convention=NAMING_CONVENTION)


async def set_tenant_context(session: AsyncSession, tenant_id: UUID) -> None:
    """Bind the given tenant_id to the current transaction so RLS
    policies scope every subsequent query in it.

    Uses set_config('app.tenant_id', <value>, true) rather than a plain
    `SET LOCAL app.tenant_id = :tenant_id` statement. This isn't a style
    preference: `SET LOCAL` does not accept bound/parameterized values in
    Postgres at all — passing one raises a syntax error at the point
    `psycopg` tries to send it as a parameterized statement. This was
    caught by actually running the register-tenant flow against a real
    database, not by review — the naive version imports, type-checks,
    and passes lint cleanly, and only fails the moment it executes.
    `set_config()` is an ordinary function call and accepts a bound
    parameter normally; its third argument (`true`) makes the setting
    transaction-local, matching what `SET LOCAL` would have done.
    """
    await session.execute(
        text("SELECT set_config('app.tenant_id', :tenant_id, true)"),
        {"tenant_id": str(tenant_id)},
    )


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Plain session dependency — no tenant context applied.

    Used for pre-tenant-context flows (tenant registration, login) where
    the application service itself calls set_tenant_context explicitly
    once it knows which tenant is in play. Protected, authenticated
    routes should use get_tenant_scoped_session (app/api/dependencies.py)
    instead, which applies tenant context automatically from the
    caller's JWT.
    """
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
