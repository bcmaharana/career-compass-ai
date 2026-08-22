"""One-time backfill: converts existing showcase_pages.blocks rows from
the old flat-block shape (each block itself carried one piece of
content: type/label/html/image_url/video_embed_url/article_topic_id/
external_url) to the new row-of-columns shape introduced for
multi-column Showcase Page support — each block ("row") now holds a
"columns" list, and every pre-existing block becomes a 1-column row
with a freshly-generated column id. See
app/domain/showcase_page/entities.py's module docstring for the full
row/column design, and
app/adapters/db/repositories/showcase_page.py's _blocks_to_json/
_blocks_from_json for the exact target JSON shape this script produces.

Idempotent: a block dict that already has a "columns" key is left
untouched — safe to re-run, e.g. once per environment (dev now, prod at
deploy time), matching migrate_plain_text_descriptions_to_html.py's own
convention.

Every row's conversion is verified in-process before being written:
the pre-conversion block list is flattened back out of the post
-conversion column list and compared field-by-field (id, type, label,
html, image_url, video_embed_url, article_topic_id, external_url) —
the UPDATE for a given row is skipped (and a loud error logged) rather
than applied if that comparison doesn't match exactly, since this
table can hold real, irreplaceable user content.

Cross-tenant read+write across every tenant's rows — same RLS caveat
as every other cross-tenant backfill in this codebase (see e.g.
migrate_plain_text_descriptions_to_html.py's own comment): a plain
script session has no app.tenant_id context set, so RLS would
otherwise make the SELECT below return zero rows and block the UPDATE
too. RLS is disabled for exactly the duration of this table's own
backfill, then re-enabled and re-forced — never left disabled.

Connects via `migrations_database_url` (the `compass` superuser/table
-owner role), not the app's own `async_session_factory` — only the
table owner can run DISABLE/ENABLE/FORCE ROW LEVEL SECURITY at all,
same reasoning as migrate_plain_text_descriptions_to_html.py.

Run once per environment:

    python scripts/migrate_showcase_blocks_to_columns.py
"""

from __future__ import annotations

import asyncio
import json
import uuid
from typing import Any

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

_COLUMN_CONTENT_FIELDS = (
    "type",
    "label",
    "html",
    "image_url",
    "video_embed_url",
    "article_topic_id",
    "external_url",
)


def _is_already_migrated(block: dict[str, Any]) -> bool:
    return "columns" in block


def _flat_block_to_column(block: dict[str, Any]) -> dict[str, Any]:
    column = {field: block.get(field) for field in _COLUMN_CONTENT_FIELDS}
    column["id"] = str(uuid.uuid4())
    return column


def _convert_blocks(blocks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        block
        if _is_already_migrated(block)
        else {"id": block["id"], "columns": [_flat_block_to_column(block)]}
        for block in blocks
    ]


def _verify_conversion_preserves_content(
    original: list[dict[str, Any]], converted: list[dict[str, Any]]
) -> bool:
    """Flattens the converted (1-column-per-old-block) rows back out and
    checks every content field matches the original block exactly —
    only the freshly-generated column id has no original counterpart to
    compare against."""
    if len(original) != len(converted):
        return False
    for original_block, converted_block in zip(original, converted, strict=True):
        if original_block.get("id") != converted_block.get("id"):
            return False
        if _is_already_migrated(original_block):
            if original_block != converted_block:
                return False
            continue
        columns = converted_block.get("columns")
        if not isinstance(columns, list) or len(columns) != 1:
            return False
        column = columns[0]
        for field in _COLUMN_CONTENT_FIELDS:
            if original_block.get(field) != column.get(field):
                return False
    return True


async def _migrate_showcase_pages(session: AsyncSession) -> tuple[int, int]:
    await session.execute(text("ALTER TABLE showcase_pages DISABLE ROW LEVEL SECURITY"))
    try:
        rows = (
            await session.execute(text("SELECT id, blocks FROM showcase_pages"))
        ).fetchall()

        updated = 0
        skipped_already_migrated = 0
        for row in rows:
            # The DBAPI may hand back the JSON column as an already-parsed
            # list (if it auto-decodes json/jsonb) or as a raw JSON string
            # (if it doesn't, since this raw text() SELECT bypasses
            # SQLAlchemy's own JSON type decorator) — handle both rather
            # than assuming one.
            raw_value = row.blocks
            original_blocks: list[dict[str, Any]] = (
                json.loads(raw_value) if isinstance(raw_value, str) else raw_value
            )
            if all(_is_already_migrated(block) for block in original_blocks):
                skipped_already_migrated += 1
                continue

            converted_blocks = _convert_blocks(original_blocks)
            if not _verify_conversion_preserves_content(original_blocks, converted_blocks):
                logger.error(
                    "showcase_page_conversion_verification_failed",
                    page_id=str(row.id),
                )
                raise AssertionError(
                    f"Conversion of showcase_pages.blocks for page {row.id} did not "
                    "verify as content-preserving — aborting without writing."
                )

            await session.execute(
                text("UPDATE showcase_pages SET blocks = CAST(:blocks AS json) WHERE id = :id"),
                {"blocks": json.dumps(converted_blocks), "id": row.id},
            )
            updated += 1
        return updated, skipped_already_migrated
    finally:
        await session.execute(text("ALTER TABLE showcase_pages ENABLE ROW LEVEL SECURITY"))
        await session.execute(text("ALTER TABLE showcase_pages FORCE ROW LEVEL SECURITY"))


async def migrate_showcase_blocks_to_columns() -> None:
    async with _session_factory() as session:
        updated, skipped = await _migrate_showcase_pages(session)
        await session.commit()
    logger.info(
        "migrate_showcase_blocks_to_columns_complete",
        rows_updated=updated,
        rows_already_migrated=skipped,
    )


if __name__ == "__main__":
    asyncio.run(migrate_showcase_blocks_to_columns())
