"""Interview Topic application service.

Topics are scoped by user_id plus a many-to-many set of tagged scopes
(scope_target_role_ids — None means Master, a real id means a specific
Target Role; see app/domain/interview_prep/entities.py's module
docstring for the full multi-scope-tagging design) — same
not-found-not-forbidden ownership pattern CareerGoalService/
LearningItemService already use for the ownership half.

Content is a freeform `blocks` document (2026-08-24 — see
app/domain/content_blocks/entities.py), the same row/column model
ShowcasePageService uses: every structural change (add/remove/reorder a
block, add/remove a column, edit a column) is a whole-array PATCH through
update(), not a dedicated endpoint per operation. Image columns write to
the private object storage bucket (see
app/domain/resume_intelligence/storage.py's PrivateObjectStorageRepository)
rather than the public profile-photo bucket — a topic image could be a
personal notes screenshot, not necessarily meant to be public — so
image_url is never persisted, only image_key; get_presigned_image_urls()
resolves every image column's URL fresh, on every read.
"""

from __future__ import annotations

import uuid
from dataclasses import replace
from datetime import UTC, datetime
from uuid import UUID

from app.core.exceptions import CareerCompassError, NotFoundError, ValidationError
from app.core.rich_text import sanitize_rich_text
from app.domain.interview_prep.entities import ArticleBlock, InterviewTopic, is_safe_reference_url
from app.domain.interview_prep.repositories import Direction, InterviewTopicRepository
from app.domain.resume_intelligence.storage import PrivateObjectStorageRepository

ALLOWED_IMAGE_CONTENT_TYPES = frozenset({"image/jpeg", "image/png", "image/webp"})
MAX_IMAGE_SIZE_BYTES = 5 * 1024 * 1024  # 5MB — same limit as profile photos
_EXTENSION_BY_CONTENT_TYPE = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp"}


def _dedupe_scopes(scope_target_role_ids: list[UUID | None]) -> list[UUID | None]:
    """Preserves order while dropping duplicates — a plain `list(set(...))`
    would both lose order and choke on `None` sorting inconsistently."""
    return list(dict.fromkeys(scope_target_role_ids))


def _sanitize_blocks(blocks: list[ArticleBlock]) -> list[ArticleBlock]:
    """Server-side re-sanitization/validation of every column, regardless
    of what the client sent — the same enforcement-point convention
    ShowcasePageService.update() already established for its own blocks."""
    for block in blocks:
        for column in block.columns:
            if column.type == "external_link" and column.external_url:
                if not is_safe_reference_url(column.external_url):
                    raise ValidationError(
                        "That link's URL isn't allowed.", code="UNSAFE_REFERENCE_LINK_URL"
                    )
    return [
        replace(
            block,
            columns=[
                replace(column, html=sanitize_rich_text(column.html))
                if column.type == "rich_text"
                else column
                for column in block.columns
            ],
        )
        for block in blocks
    ]


class InterviewTopicService:
    def __init__(
        self, topics: InterviewTopicRepository, storage: PrivateObjectStorageRepository
    ) -> None:
        self._topics = topics
        self._storage = storage

    async def get_owned_or_raise(
        self, *, tenant_id: UUID, user_id: UUID, topic_id: UUID
    ) -> InterviewTopic:
        topic = await self._topics.get_by_id(tenant_id, topic_id)
        if topic is None or topic.user_id != user_id:
            raise NotFoundError("Interview topic not found.", code="INTERVIEW_TOPIC_NOT_FOUND")
        return topic

    async def add(
        self,
        *,
        tenant_id: UUID,
        user_id: UUID,
        name: str,
        section: str | None,
        scope_target_role_ids: list[UUID | None],
    ) -> InterviewTopic:
        deduped = _dedupe_scopes(scope_target_role_ids)
        if not deduped:
            raise ValidationError(
                "A topic must be tagged to at least one scope.", code="SCOPE_REQUIRED"
            )
        now = datetime.now(UTC)
        return await self._topics.create(
            InterviewTopic(
                id=uuid.uuid4(),
                tenant_id=tenant_id,
                user_id=user_id,
                name=name,
                section=section,
                scope_target_role_ids=deduped,
                created_at=now,
                updated_at=now,
            )
        )

    async def list_for_scope(
        self, *, tenant_id: UUID, user_id: UUID, target_role_id: UUID | None
    ) -> list[InterviewTopic]:
        return await self._topics.list_for_scope(tenant_id, user_id, target_role_id)

    async def update(
        self,
        *,
        tenant_id: UUID,
        user_id: UUID,
        topic_id: UUID,
        name: str,
        section: str | None,
        blocks: list[ArticleBlock],
        scope_target_role_ids: list[UUID | None],
    ) -> InterviewTopic:
        deduped = _dedupe_scopes(scope_target_role_ids)
        if not deduped:
            raise ValidationError(
                "A topic must be tagged to at least one scope.", code="SCOPE_REQUIRED"
            )
        topic = await self.get_owned_or_raise(tenant_id=tenant_id, user_id=user_id, topic_id=topic_id)

        # Any image column removed in this update (or the whole block it
        # lived in) should have its object storage cleaned up too — same
        # "an edit that drops a column's image doesn't leak the object"
        # reasoning ShowcasePageService doesn't need (public bucket, no
        # separate key to track) but this private-bucket domain does.
        previous_keys = {
            column.image_key
            for block in topic.blocks
            for column in block.columns
            if column.type == "image" and column.image_key
        }
        next_keys = {
            column.image_key
            for block in blocks
            for column in block.columns
            if column.type == "image" and column.image_key
        }
        for stale_key in previous_keys - next_keys:
            try:
                await self._storage.delete_private(key=stale_key)
            except CareerCompassError:
                pass  # best-effort — DB is the source of truth, same as delete()/upload_image() below

        topic.name = name
        topic.section = section
        topic.blocks = _sanitize_blocks(blocks)
        topic.scope_target_role_ids = deduped
        return await self._topics.update(topic)

    async def delete(
        self,
        *,
        tenant_id: UUID,
        user_id: UUID,
        topic_id: UUID,
        target_role_id: UUID | None,
        delete_everywhere: bool,
    ) -> None:
        """Deletes the topic entirely if `delete_everywhere` is true, or
        if it's only tagged to `target_role_id` in the first place (a
        single-scope topic has no meaningful "just this scope" option —
        removing its only scope leaves it invisible everywhere, which is
        the same outcome as deleting it, so this always takes the full
        delete path rather than leaving an orphaned zero-scope row).
        Otherwise, untags it from just `target_role_id`, leaving it
        intact under its other tagged scopes — the caller (API layer)
        is expected to have already asked the user which behavior they
        want when the topic has more than one tag; see
        InterviewTopicResponse.scope_target_role_ids for how the
        frontend knows whether to ask at all.
        """
        topic = await self.get_owned_or_raise(tenant_id=tenant_id, user_id=user_id, topic_id=topic_id)
        if delete_everywhere or len(topic.scope_target_role_ids) <= 1:
            for block in topic.blocks:
                for column in block.columns:
                    if column.type == "image" and column.image_key:
                        try:
                            await self._storage.delete_private(key=column.image_key)
                        except CareerCompassError:
                            # Best-effort — the DB row is the source of truth for
                            # "does this topic have an image," same reasoning
                            # CareerProfileService.delete_photo already established.
                            pass
            await self._topics.soft_delete(tenant_id, topic_id)
        else:
            await self._topics.remove_scope(tenant_id, topic_id, target_role_id)

    async def move(
        self,
        *,
        tenant_id: UUID,
        user_id: UUID,
        topic_id: UUID,
        target_role_id: UUID | None,
        direction: Direction,
    ) -> None:
        await self.get_owned_or_raise(tenant_id=tenant_id, user_id=user_id, topic_id=topic_id)
        await self._topics.move(tenant_id, topic_id, target_role_id, direction)

    async def upload_image(
        self,
        *,
        tenant_id: UUID,
        user_id: UUID,
        topic_id: UUID,
        column_id: UUID,
        content: bytes,
        content_type: str,
    ) -> InterviewTopic:
        if content_type not in ALLOWED_IMAGE_CONTENT_TYPES:
            raise ValidationError(
                f"Unsupported image type '{content_type}'. Allowed: "
                f"{sorted(ALLOWED_IMAGE_CONTENT_TYPES)}",
                code="UNSUPPORTED_IMAGE_TYPE",
            )
        if len(content) > MAX_IMAGE_SIZE_BYTES:
            raise ValidationError(
                f"Image exceeds the {MAX_IMAGE_SIZE_BYTES // (1024 * 1024)}MB limit.",
                code="IMAGE_TOO_LARGE",
            )
        topic = await self.get_owned_or_raise(tenant_id=tenant_id, user_id=user_id, topic_id=topic_id)

        column = next(
            (c for block in topic.blocks for c in block.columns if c.id == column_id), None
        )
        if column is None:
            raise NotFoundError(
                "Interview topic image column not found.", code="INTERVIEW_TOPIC_COLUMN_NOT_FOUND"
            )

        # Overwrite the previous image, if any, rather than accumulating
        # objects — same "regenerating replaces, doesn't accumulate a
        # history" model as CareerProfile.photo_url.
        if column.image_key is not None:
            try:
                await self._storage.delete_private(key=column.image_key)
            except CareerCompassError:
                pass

        extension = _EXTENSION_BY_CONTENT_TYPE[content_type]
        key = f"interview-topics/{tenant_id}/{topic.id}/{column_id}.{extension}"
        await self._storage.upload_private(key=key, content=content, content_type=content_type)
        column.image_key = key
        return await self._topics.update(topic)

    async def get_presigned_image_urls(self, topic: InterviewTopic) -> dict[UUID, str]:
        urls: dict[UUID, str] = {}
        for block in topic.blocks:
            for column in block.columns:
                if column.type == "image" and column.image_key:
                    urls[column.id] = await self._storage.get_presigned_url(
                        key=column.image_key, expires_in_seconds=300
                    )
        return urls

    async def set_public(
        self, *, tenant_id: UUID, user_id: UUID, topic_id: UUID, is_public: bool
    ) -> InterviewTopic:
        """A dedicated action, not folded into update() — same
        "content-heavy fields get their own sub-action" convention this
        domain already established. Does NOT itself mint a
        public_share_links row — that's PublicSharingService's job
        (app/application/showcase_page/), the same split
        ShowcasePageService.set_public follows."""
        topic = await self.get_owned_or_raise(
            tenant_id=tenant_id, user_id=user_id, topic_id=topic_id
        )
        topic.is_public = is_public
        return await self._topics.update(topic)
