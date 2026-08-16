"""Interview Topic application service.

Topics are scoped directly by user_id, optionally tied to a Target Role
(target_role_id) — same not-found-not-forbidden ownership pattern
CareerGoalService/LearningItemService already use. Image upload writes
to the private object storage bucket (see
app/domain/resume_intelligence/storage.py's PrivateObjectStorageRepository)
rather than the public profile-photo bucket — a topic image could be a
personal notes screenshot, not necessarily meant to be public.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from uuid import UUID

from app.core.exceptions import CareerCompassError, NotFoundError, ValidationError
from app.core.rich_text import sanitize_rich_text
from app.domain.interview_prep.entities import InterviewTopic, ReferenceLink
from app.domain.interview_prep.repositories import Direction, InterviewTopicRepository
from app.domain.resume_intelligence.storage import PrivateObjectStorageRepository

ALLOWED_IMAGE_CONTENT_TYPES = frozenset({"image/jpeg", "image/png", "image/webp"})
MAX_IMAGE_SIZE_BYTES = 5 * 1024 * 1024  # 5MB — same limit as profile photos
_EXTENSION_BY_CONTENT_TYPE = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp"}


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
        target_role_id: UUID | None,
        name: str,
        section: str | None,
        discussion: str | None,
    ) -> InterviewTopic:
        now = datetime.now(UTC)
        return await self._topics.create(
            InterviewTopic(
                id=uuid.uuid4(),
                tenant_id=tenant_id,
                user_id=user_id,
                target_role_id=target_role_id,
                name=name,
                section=section,
                discussion=sanitize_rich_text(discussion),
                display_order=0,  # overwritten by the repository on create
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
        discussion: str | None,
        reference_links: list[ReferenceLink],
    ) -> InterviewTopic:
        topic = await self.get_owned_or_raise(tenant_id=tenant_id, user_id=user_id, topic_id=topic_id)
        topic.name = name
        topic.section = section
        topic.discussion = sanitize_rich_text(discussion)
        topic.reference_links = reference_links
        return await self._topics.update(topic)

    async def delete(self, *, tenant_id: UUID, user_id: UUID, topic_id: UUID) -> None:
        topic = await self.get_owned_or_raise(tenant_id=tenant_id, user_id=user_id, topic_id=topic_id)
        if topic.image_key is not None:
            try:
                await self._storage.delete_private(key=topic.image_key)
            except CareerCompassError:
                # Best-effort — the DB row is the source of truth for
                # "does this topic have an image," same reasoning
                # CareerProfileService.delete_photo already established.
                pass
        await self._topics.soft_delete(tenant_id, topic_id)

    async def move(
        self, *, tenant_id: UUID, user_id: UUID, topic_id: UUID, direction: Direction
    ) -> None:
        await self.get_owned_or_raise(tenant_id=tenant_id, user_id=user_id, topic_id=topic_id)
        await self._topics.move(tenant_id, topic_id, direction)

    async def upload_image(
        self,
        *,
        tenant_id: UUID,
        user_id: UUID,
        topic_id: UUID,
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

        # Overwrite the previous image, if any, rather than accumulating
        # objects — same "regenerating replaces, doesn't accumulate a
        # history" model as CareerProfile.photo_url.
        if topic.image_key is not None:
            try:
                await self._storage.delete_private(key=topic.image_key)
            except CareerCompassError:
                pass

        extension = _EXTENSION_BY_CONTENT_TYPE[content_type]
        key = f"interview-topics/{tenant_id}/{topic.id}.{extension}"
        await self._storage.upload_private(key=key, content=content, content_type=content_type)
        topic.image_key = key
        return await self._topics.update(topic)

    async def delete_image(self, *, tenant_id: UUID, user_id: UUID, topic_id: UUID) -> InterviewTopic:
        topic = await self.get_owned_or_raise(tenant_id=tenant_id, user_id=user_id, topic_id=topic_id)
        if topic.image_key is not None:
            try:
                await self._storage.delete_private(key=topic.image_key)
            except CareerCompassError:
                pass
        topic.image_key = None
        return await self._topics.update(topic)

    async def get_presigned_image_url(self, topic: InterviewTopic) -> str | None:
        if topic.image_key is None:
            return None
        return await self._storage.get_presigned_url(key=topic.image_key, expires_in_seconds=300)
