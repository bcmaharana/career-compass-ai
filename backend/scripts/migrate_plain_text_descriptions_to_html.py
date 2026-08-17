"""One-time backfill: converts existing plain-text description-style
fields (Career Profile's headline/summary, Experience/Education/Career
Goal/Career Highlight/Key Achievement descriptions, Peer Endorsement's
testimonial content, Learning Item notes) into the equivalent sanitized
rich-text HTML now expected by RichTextEditor/RichTextDisplay
(frontend/src/components/ui/rich-text-editor.tsx) — see
app.core.rich_text.plain_text_to_rich_html for the exact conversion
logic (reimplements ExperienceSection.tsx's DescriptionText bullet-
grouping in Python).

Idempotent: plain_text_to_rich_html() is a no-op on any value that
already contains a "<" (i.e. already-migrated HTML), so a second run
updates nothing — safe to re-run, e.g. once per environment (dev now,
prod at deploy time).

Cross-tenant read+write across every tenant's rows — same RLS caveat as
every other cross-tenant backfill in this codebase (see e.g. Alembic
migration 1007d872b535's own comment): a plain script session has no
app.tenant_id context set, so RLS would otherwise make every SELECT
below return zero rows and block the UPDATEs too. Each table's RLS is
disabled for exactly the duration of its own backfill, then re-enabled
and re-forced — never left disabled.

Connects via `migrations_database_url` (the `compass` superuser/table
-owner role), not the app's own `async_session_factory`
(app/adapters/db/base.py, pinned to the restricted `compass_app` role)
— same reasoning and same fallback-to-database_url-if-unset behavior as
alembic/env.py: only the table owner can run
DISABLE/ENABLE/FORCE ROW LEVEL SECURITY at all, confirmed live (a first
attempt through the restricted role failed outright with
"InsufficientPrivilege: must be owner of table career_profiles").

Run once per environment:

    python scripts/migrate_plain_text_descriptions_to_html.py
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import app.adapters.db.base  # noqa: F401  # sets the Windows asyncio event-loop
# policy (must happen before asyncio.run() creates one) — not otherwise
# used here, this script builds its own engine (see below) against
# migrations_database_url rather than that module's app-role engine.
from app.core.config import get_settings
from app.core.logging import get_logger
from app.core.rich_text import plain_text_to_rich_html

logger = get_logger(__name__)

_settings = get_settings()
_engine = create_async_engine(_settings.migrations_database_url or _settings.database_url)
_session_factory = async_sessionmaker(_engine, expire_on_commit=False)


@dataclass(frozen=True, slots=True)
class FieldTarget:
    table: str
    column: str


TARGETS: tuple[FieldTarget, ...] = (
    FieldTarget("career_profiles", "headline"),
    FieldTarget("career_profiles", "summary"),
    FieldTarget("experiences", "description"),
    FieldTarget("educations", "description"),
    FieldTarget("career_goals", "description"),
    FieldTarget("career_highlights", "description"),
    FieldTarget("key_achievements", "description"),
    FieldTarget("peer_endorsements", "content"),
    FieldTarget("learning_items", "notes"),
)


async def _migrate_field(session: AsyncSession, target: FieldTarget) -> int:
    await session.execute(text(f"ALTER TABLE {target.table} DISABLE ROW LEVEL SECURITY"))
    try:
        rows = (
            await session.execute(
                text(
                    f"SELECT id, {target.column} AS value FROM {target.table} "
                    f"WHERE {target.column} IS NOT NULL"
                )
            )
        ).fetchall()

        updated = 0
        for row in rows:
            converted = plain_text_to_rich_html(row.value)
            if converted == row.value:
                continue  # already HTML (no-op), or unchanged for some other reason
            await session.execute(
                text(f"UPDATE {target.table} SET {target.column} = :value WHERE id = :id"),
                {"value": converted, "id": row.id},
            )
            updated += 1
        return updated
    finally:
        await session.execute(text(f"ALTER TABLE {target.table} ENABLE ROW LEVEL SECURITY"))
        await session.execute(text(f"ALTER TABLE {target.table} FORCE ROW LEVEL SECURITY"))


async def migrate_plain_text_descriptions_to_html() -> None:
    async with _session_factory() as session:
        for target in TARGETS:
            updated = await _migrate_field(session, target)
            logger.info(
                "migrated_field_to_html",
                table=target.table,
                column=target.column,
                rows_updated=updated,
            )
        await session.commit()
    logger.info("migrate_plain_text_descriptions_to_html_complete")


if __name__ == "__main__":
    asyncio.run(migrate_plain_text_descriptions_to_html())
