"""One-time backfill: populates `name`/`headline`/`summary` (the
2026-08-24 top-bar fields — see app/domain/showcase_page/entities.py's
own docstring) on any existing showcase_pages row that predates this
feature and so has them NULL. ShowcasePageService.get_or_create() only
ever seeds these at TRUE first-creation time — an already-existing page
(this app has one real page in prod, created before this feature
shipped) is never revisited by that seeding logic, so it would otherwise
sit with a permanently blank top bar rather than the same
Master-fallback-aware seed every brand-new page gets.

Computes exactly the same values ShowcasePageService.get_or_create()
would have seeded: the owning User's display_name (a Python property —
salutation + first_name + last_name — hence a real script rather than a
raw SQL backfill), and the resolved CareerProfile's headline/summary,
with the same Master-fallback rule (a Target Role Profile with no
headline/summary of its own falls back to Master's) `blocks` itself
already uses.

Idempotent: only touches rows where `name IS NULL` — a page already
backfilled (or one created after this feature shipped, which already
has these fields populated at creation) is left untouched. Safe to
re-run.

Cross-tenant read+write across every tenant's rows — same RLS caveat as
every other cross-tenant backfill in this codebase. RLS is disabled for
exactly the duration of each table's own read/write, then re-enabled and
re-forced — never left disabled. Connects via `migrations_database_url`
(the `compass` superuser/table-owner role) — only the table owner can
run DISABLE/ENABLE/FORCE ROW LEVEL SECURITY at all.

Run once per environment:

    python scripts/backfill_showcase_page_header.py
"""

from __future__ import annotations

import asyncio

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import app.adapters.db.base  # noqa: F401  # sets the Windows asyncio event-loop
# policy (must happen before asyncio.run() creates one) — not otherwise
# used here, this script builds its own engine (see below) against
# migrations_database_url rather than that module's app-role engine.
from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

_settings = get_settings()
_engine = create_async_engine(_settings.migrations_database_url or _settings.database_url)
_session_factory = async_sessionmaker(_engine, expire_on_commit=False)

_TABLES = ("showcase_pages", "users", "career_profiles")


def _display_name(salutation: str | None, first_name: str, last_name: str) -> str:
    """Mirrors app/domain/identity/entities.py's User.display_name
    property exactly — not derivable via plain SQL since it's Python
    logic, hence this being a real script rather than a raw UPDATE."""
    parts = [part for part in (salutation, first_name, last_name) if part]
    return " ".join(parts)


async def _resolve_profile(
    session: AsyncSession, *, tenant_id: object, user_id: object, target_role_id: object
) -> tuple[str | None, str | None]:
    row = (
        await session.execute(
            text(
                "SELECT headline, summary FROM career_profiles "
                "WHERE tenant_id = :tenant_id AND user_id = :user_id "
                "AND target_role_id IS NOT DISTINCT FROM :target_role_id"
            ),
            {"tenant_id": tenant_id, "user_id": user_id, "target_role_id": target_role_id},
        )
    ).first()
    return (row.headline, row.summary) if row is not None else (None, None)


async def _backfill(session: AsyncSession) -> tuple[int, int]:
    for table in _TABLES:
        await session.execute(text(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY"))
    try:
        rows = (
            await session.execute(
                text(
                    "SELECT id, tenant_id, user_id, target_role_id FROM showcase_pages "
                    "WHERE name IS NULL"
                )
            )
        ).fetchall()

        updated = 0
        for row in rows:
            user_row = (
                await session.execute(
                    text(
                        "SELECT salutation, first_name, last_name FROM users "
                        "WHERE tenant_id = :tenant_id AND id = :user_id"
                    ),
                    {"tenant_id": row.tenant_id, "user_id": row.user_id},
                )
            ).first()
            if user_row is None:
                logger.warning(
                    "backfill_showcase_page_header_missing_user",
                    page_id=str(row.id),
                    user_id=str(row.user_id),
                )
                continue
            name = _display_name(user_row.salutation, user_row.first_name, user_row.last_name)

            headline, summary = await _resolve_profile(
                session,
                tenant_id=row.tenant_id,
                user_id=row.user_id,
                target_role_id=row.target_role_id,
            )
            if not headline and not summary:
                # Same Master-fallback rule ShowcasePageService.get_or_create()
                # already applies for `blocks` — a Target Role Profile with
                # nothing of its own falls back to Master's.
                headline, summary = await _resolve_profile(
                    session, tenant_id=row.tenant_id, user_id=row.user_id, target_role_id=None
                )

            await session.execute(
                text(
                    "UPDATE showcase_pages SET name = :name, headline = :headline, "
                    "summary = :summary WHERE id = :id"
                ),
                {"name": name or None, "headline": headline, "summary": summary, "id": row.id},
            )
            updated += 1
        return updated, len(rows) - updated
    finally:
        for table in _TABLES:
            await session.execute(text(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY"))
            await session.execute(text(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY"))


async def backfill_showcase_page_header() -> None:
    async with _session_factory() as session:
        updated, skipped = await _backfill(session)
        await session.commit()
    logger.info(
        "backfill_showcase_page_header_complete", rows_updated=updated, rows_skipped=skipped
    )


if __name__ == "__main__":
    asyncio.run(backfill_showcase_page_header())
