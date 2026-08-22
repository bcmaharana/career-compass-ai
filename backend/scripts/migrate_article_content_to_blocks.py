"""One-time backfill: converts existing interview_topics rows' fixed
discussion/image_key/reference_links content into the equivalent
freeform `blocks` document (the same row/column content-block model
ShowcasePage uses — see app/domain/content_blocks/entities.py), run
between the two `article_content_blocks` migrations
(`be55f657c85d` adds the new `blocks` column;
`151c0de9eca1` drops the three old columns and REFUSES to run if this
script hasn't migrated every row with real old-shape content first).

Produces, in order, for each topic that has any old content: one
rich_text block for `discussion` (if non-empty), one image block for
`image_key` (if set), then one external_link block per `reference_link`
— matching the original TopicCard sub-card order (Discussion, Image,
Reference Links) so a migrated Article reads the same as before.

Idempotent: a row whose `blocks` column is already non-empty is left
untouched — safe to re-run, e.g. once per environment (dev now, prod at
deploy time), matching migrate_showcase_blocks_to_columns.py's own
convention. Every row's conversion is verified in-process before being
written: the built blocks are walked back into a
(discussion, image_key, reference_links)-shaped tuple and compared
field-by-field (and reference-link-by-reference-link, in order) against
the original row — the UPDATE is skipped (and a loud error raised,
aborting the whole run without writing anything further) rather than
applied if that comparison doesn't match exactly, since this table can
hold real, irreplaceable user content.

Cross-tenant read+write across every tenant's rows — same RLS caveat as
every other cross-tenant backfill in this codebase. RLS is disabled for
exactly the duration of this table's own backfill, then re-enabled and
re-forced — never left disabled. Connects via `migrations_database_url`
(the `compass` superuser/table-owner role) — only the table owner can
run DISABLE/ENABLE/FORCE ROW LEVEL SECURITY at all.

Run once per environment, BEFORE applying the `151c0de9eca1` migration:

    python scripts/migrate_article_content_to_blocks.py
    alembic upgrade head
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


def _new_column(**fields: Any) -> dict[str, Any]:
    base = {
        "id": str(uuid.uuid4()),
        "label": "",
        "html": None,
        "image_url": None,
        "image_key": None,
        "video_embed_url": None,
        "article_topic_id": None,
        "external_url": None,
    }
    base.update(fields)
    return base


def _build_blocks(
    discussion: str | None, image_key: str | None, reference_links: list[dict[str, str]]
) -> list[dict[str, Any]]:
    blocks: list[dict[str, Any]] = []
    if discussion:
        blocks.append(
            {
                "id": str(uuid.uuid4()),
                "columns": [_new_column(type="rich_text", label="Discussion", html=discussion)],
            }
        )
    if image_key:
        blocks.append(
            {
                "id": str(uuid.uuid4()),
                "columns": [_new_column(type="image", label="Image", image_key=image_key)],
            }
        )
    for link in reference_links:
        blocks.append(
            {
                "id": str(uuid.uuid4()),
                "columns": [
                    _new_column(
                        type="external_link", label=link["label"], external_url=link["url"]
                    )
                ],
            }
        )
    return blocks


def _verify_conversion_preserves_content(
    discussion: str | None,
    image_key: str | None,
    reference_links: list[dict[str, str]],
    blocks: list[dict[str, Any]],
) -> bool:
    """Flattens `blocks` back out and checks it reconstructs exactly the
    same (discussion, image_key, reference_links) the original row had —
    only the freshly-generated block/column ids have no original
    counterpart to compare against."""
    expected_len = (1 if discussion else 0) + (1 if image_key else 0) + len(reference_links)
    if len(blocks) != expected_len:
        return False

    index = 0
    if discussion:
        column = blocks[index]["columns"][0]
        if column["type"] != "rich_text" or column["html"] != discussion:
            return False
        index += 1
    if image_key:
        column = blocks[index]["columns"][0]
        if column["type"] != "image" or column["image_key"] != image_key:
            return False
        index += 1
    for link in reference_links:
        column = blocks[index]["columns"][0]
        if (
            column["type"] != "external_link"
            or column["external_url"] != link["url"]
            or column["label"] != link["label"]
        ):
            return False
        index += 1
    return True


async def _migrate_interview_topics(session: AsyncSession) -> tuple[int, int]:
    await session.execute(text("ALTER TABLE interview_topics DISABLE ROW LEVEL SECURITY"))
    try:
        rows = (
            await session.execute(
                text(
                    "SELECT id, discussion, image_key, reference_links, blocks "
                    "FROM interview_topics"
                )
            )
        ).fetchall()

        updated = 0
        skipped_already_migrated = 0
        for row in rows:
            raw_blocks = row.blocks
            existing_blocks: list[dict[str, Any]] = (
                json.loads(raw_blocks) if isinstance(raw_blocks, str) else raw_blocks
            )
            if existing_blocks:
                skipped_already_migrated += 1
                continue

            raw_links = row.reference_links
            reference_links: list[dict[str, str]] = (
                json.loads(raw_links) if isinstance(raw_links, str) else raw_links
            )
            if not row.discussion and not row.image_key and not reference_links:
                continue  # nothing to migrate for this row — leaves blocks == []

            blocks = _build_blocks(row.discussion, row.image_key, reference_links)
            if not _verify_conversion_preserves_content(
                row.discussion, row.image_key, reference_links, blocks
            ):
                logger.error("article_conversion_verification_failed", topic_id=str(row.id))
                raise AssertionError(
                    f"Conversion of interview_topics content for topic {row.id} did not "
                    "verify as content-preserving — aborting without writing."
                )

            await session.execute(
                text("UPDATE interview_topics SET blocks = CAST(:blocks AS json) WHERE id = :id"),
                {"blocks": json.dumps(blocks), "id": row.id},
            )
            updated += 1
        return updated, skipped_already_migrated
    finally:
        await session.execute(text("ALTER TABLE interview_topics ENABLE ROW LEVEL SECURITY"))
        await session.execute(text("ALTER TABLE interview_topics FORCE ROW LEVEL SECURITY"))


async def migrate_article_content_to_blocks() -> None:
    async with _session_factory() as session:
        updated, skipped = await _migrate_interview_topics(session)
        await session.commit()
    logger.info(
        "migrate_article_content_to_blocks_complete",
        rows_updated=updated,
        rows_already_migrated=skipped,
    )


if __name__ == "__main__":
    asyncio.run(migrate_article_content_to_blocks())
