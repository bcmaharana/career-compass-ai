"""Unit tests for InterviewTopicService — fake repository/storage, no
database, no real object storage. Mirrors the fake-repository pattern
established in tests/unit/test_target_role_service.py.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest

from app.application.interview_prep.interview_topic_service import (
    MAX_IMAGE_SIZE_BYTES,
    InterviewTopicService,
)
from app.core.exceptions import CareerCompassError, NotFoundError, ValidationError
from app.domain.interview_prep.entities import InterviewTopic, ReferenceLink

pytestmark = pytest.mark.unit


class FakeInterviewTopicRepository:
    def __init__(self) -> None:
        self.topics: dict[uuid.UUID, InterviewTopic] = {}
        self._order_counter = 0

    async def create(self, topic: InterviewTopic) -> InterviewTopic:
        self._order_counter += 1
        topic.display_order = self._order_counter
        self.topics[topic.id] = topic
        return topic

    async def get_by_id(self, tenant_id: uuid.UUID, topic_id: uuid.UUID) -> InterviewTopic | None:
        topic = self.topics.get(topic_id)
        return topic if topic and topic.tenant_id == tenant_id else None

    async def list_for_scope(
        self, tenant_id: uuid.UUID, user_id: uuid.UUID, target_role_id: uuid.UUID | None
    ) -> list[InterviewTopic]:
        return sorted(
            (
                t
                for t in self.topics.values()
                if t.tenant_id == tenant_id
                and t.user_id == user_id
                and t.target_role_id == target_role_id
            ),
            key=lambda t: t.display_order,
        )

    async def update(self, topic: InterviewTopic) -> InterviewTopic:
        self.topics[topic.id] = topic
        return topic

    async def soft_delete(self, tenant_id: uuid.UUID, topic_id: uuid.UUID) -> None:
        self.topics.pop(topic_id, None)

    async def move(self, tenant_id: uuid.UUID, topic_id: uuid.UUID, direction: str) -> None:
        items = await self.list_for_scope(
            tenant_id, self.topics[topic_id].user_id, self.topics[topic_id].target_role_id
        )
        index = next(i for i, t in enumerate(items) if t.id == topic_id)
        neighbor_index = index - 1 if direction == "up" else index + 1
        if neighbor_index < 0 or neighbor_index >= len(items):
            return
        items[index].display_order, items[neighbor_index].display_order = (
            items[neighbor_index].display_order,
            items[index].display_order,
        )


class FakePrivateObjectStorage:
    def __init__(self, *, fail_delete: bool = False) -> None:
        self.uploaded: dict[str, bytes] = {}
        self.deleted_keys: list[str] = []
        self._fail_delete = fail_delete

    async def upload_private(self, *, key: str, content: bytes, content_type: str) -> None:
        self.uploaded[key] = content

    async def get_presigned_url(
        self, *, key: str, expires_in_seconds: int = 300, download_filename: str | None = None
    ) -> str:
        return f"https://fake-private-bucket/{key}?expires={expires_in_seconds}"

    async def delete_private(self, *, key: str) -> None:
        if self._fail_delete:
            raise CareerCompassError(f"simulated failure deleting '{key}'")
        self.deleted_keys.append(key)


def _make_topic(tenant_id: uuid.UUID, user_id: uuid.UUID, **kwargs: object) -> InterviewTopic:
    now = datetime.now(UTC)
    defaults: dict[str, object] = dict(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        user_id=user_id,
        target_role_id=None,
        name="System Design",
        display_order=0,
        created_at=now,
        updated_at=now,
    )
    defaults.update(kwargs)
    return InterviewTopic(**defaults)  # type: ignore[arg-type]


class TestAdd:
    async def test_adds_a_topic_in_the_given_scope(self) -> None:
        tenant_id, user_id = uuid.uuid4(), uuid.uuid4()
        repo = FakeInterviewTopicRepository()
        service = InterviewTopicService(repo, FakePrivateObjectStorage())

        topic = await service.add(
            tenant_id=tenant_id,
            user_id=user_id,
            target_role_id=None,
            name="System Design",
            section="Technical",
            discussion="Notes here.",
        )

        assert topic.name == "System Design"
        assert topic.section == "Technical"
        assert repo.topics[topic.id] is topic

    async def test_discussion_is_sanitized_on_save(self) -> None:
        tenant_id, user_id = uuid.uuid4(), uuid.uuid4()
        repo = FakeInterviewTopicRepository()
        service = InterviewTopicService(repo, FakePrivateObjectStorage())

        topic = await service.add(
            tenant_id=tenant_id,
            user_id=user_id,
            target_role_id=None,
            name="System Design",
            section=None,
            discussion='<i>Notes</i><script>alert(1)</script>',
        )

        assert topic.discussion == "<i>Notes</i>alert(1)"


class TestUpdateAndDelete:
    async def test_update_sanitizes_discussion(self) -> None:
        tenant_id, user_id = uuid.uuid4(), uuid.uuid4()
        repo = FakeInterviewTopicRepository()
        topic = await repo.create(_make_topic(tenant_id, user_id))
        service = InterviewTopicService(repo, FakePrivateObjectStorage())

        updated = await service.update(
            tenant_id=tenant_id,
            user_id=user_id,
            topic_id=topic.id,
            name=topic.name,
            section=None,
            discussion='<span style="color: red; background: url(x)">colored</span>',
            reference_links=[],
        )

        assert updated.discussion == '<span style="color: red;">colored</span>'

    async def test_update_saves_reference_links(self) -> None:
        tenant_id, user_id = uuid.uuid4(), uuid.uuid4()
        repo = FakeInterviewTopicRepository()
        topic = await repo.create(_make_topic(tenant_id, user_id))
        service = InterviewTopicService(repo, FakePrivateObjectStorage())

        updated = await service.update(
            tenant_id=tenant_id,
            user_id=user_id,
            topic_id=topic.id,
            name=topic.name,
            section=None,
            discussion=None,
            reference_links=[ReferenceLink(url="https://example.com", label="Example")],
        )

        assert updated.reference_links == [ReferenceLink(url="https://example.com", label="Example")]

    async def test_update_requires_ownership(self) -> None:
        tenant_id, user_id, other_user = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
        repo = FakeInterviewTopicRepository()
        topic = await repo.create(_make_topic(tenant_id, user_id))
        service = InterviewTopicService(repo, FakePrivateObjectStorage())

        with pytest.raises(NotFoundError):
            await service.update(
                tenant_id=tenant_id,
                user_id=other_user,
                topic_id=topic.id,
                name="Renamed",
                section=None,
                discussion=None,
                reference_links=[],
            )

    async def test_delete_best_effort_removes_image(self) -> None:
        tenant_id, user_id = uuid.uuid4(), uuid.uuid4()
        repo = FakeInterviewTopicRepository()
        topic = await repo.create(_make_topic(tenant_id, user_id, image_key="interview-topics/x.jpg"))
        storage = FakePrivateObjectStorage()
        service = InterviewTopicService(repo, storage)

        await service.delete(tenant_id=tenant_id, user_id=user_id, topic_id=topic.id)

        assert storage.deleted_keys == ["interview-topics/x.jpg"]
        assert topic.id not in repo.topics

    async def test_delete_survives_storage_failure(self) -> None:
        tenant_id, user_id = uuid.uuid4(), uuid.uuid4()
        repo = FakeInterviewTopicRepository()
        topic = await repo.create(_make_topic(tenant_id, user_id, image_key="interview-topics/x.jpg"))
        storage = FakePrivateObjectStorage(fail_delete=True)
        service = InterviewTopicService(repo, storage)

        await service.delete(tenant_id=tenant_id, user_id=user_id, topic_id=topic.id)

        assert topic.id not in repo.topics


class TestMove:
    async def test_move_swaps_display_order_within_scope(self) -> None:
        tenant_id, user_id = uuid.uuid4(), uuid.uuid4()
        repo = FakeInterviewTopicRepository()
        first = await repo.create(_make_topic(tenant_id, user_id, name="First"))
        second = await repo.create(_make_topic(tenant_id, user_id, name="Second"))
        service = InterviewTopicService(repo, FakePrivateObjectStorage())

        await service.move(tenant_id=tenant_id, user_id=user_id, topic_id=second.id, direction="up")

        ordered = await repo.list_for_scope(tenant_id, user_id, None)
        assert [t.id for t in ordered] == [second.id, first.id]


class TestUploadImage:
    async def test_uploads_and_stores_the_key(self) -> None:
        tenant_id, user_id = uuid.uuid4(), uuid.uuid4()
        repo = FakeInterviewTopicRepository()
        topic = await repo.create(_make_topic(tenant_id, user_id))
        storage = FakePrivateObjectStorage()
        service = InterviewTopicService(repo, storage)

        updated = await service.upload_image(
            tenant_id=tenant_id,
            user_id=user_id,
            topic_id=topic.id,
            content=b"fake-bytes",
            content_type="image/png",
        )

        assert updated.image_key is not None
        assert updated.image_key in storage.uploaded

    async def test_replacing_an_image_deletes_the_old_one(self) -> None:
        tenant_id, user_id = uuid.uuid4(), uuid.uuid4()
        repo = FakeInterviewTopicRepository()
        topic = await repo.create(_make_topic(tenant_id, user_id, image_key="interview-topics/old.jpg"))
        storage = FakePrivateObjectStorage()
        service = InterviewTopicService(repo, storage)

        await service.upload_image(
            tenant_id=tenant_id,
            user_id=user_id,
            topic_id=topic.id,
            content=b"new-bytes",
            content_type="image/png",
        )

        assert "interview-topics/old.jpg" in storage.deleted_keys

    async def test_rejects_unsupported_content_type(self) -> None:
        tenant_id, user_id = uuid.uuid4(), uuid.uuid4()
        repo = FakeInterviewTopicRepository()
        topic = await repo.create(_make_topic(tenant_id, user_id))
        service = InterviewTopicService(repo, FakePrivateObjectStorage())

        with pytest.raises(ValidationError):
            await service.upload_image(
                tenant_id=tenant_id,
                user_id=user_id,
                topic_id=topic.id,
                content=b"data",
                content_type="application/pdf",
            )

    async def test_rejects_oversized_image(self) -> None:
        tenant_id, user_id = uuid.uuid4(), uuid.uuid4()
        repo = FakeInterviewTopicRepository()
        topic = await repo.create(_make_topic(tenant_id, user_id))
        service = InterviewTopicService(repo, FakePrivateObjectStorage())

        with pytest.raises(ValidationError):
            await service.upload_image(
                tenant_id=tenant_id,
                user_id=user_id,
                topic_id=topic.id,
                content=b"x" * (MAX_IMAGE_SIZE_BYTES + 1),
                content_type="image/png",
            )


class TestPresignedImageUrl:
    async def test_returns_none_when_no_image(self) -> None:
        tenant_id, user_id = uuid.uuid4(), uuid.uuid4()
        service = InterviewTopicService(FakeInterviewTopicRepository(), FakePrivateObjectStorage())
        topic = _make_topic(tenant_id, user_id)

        assert await service.get_presigned_image_url(topic) is None

    async def test_resolves_a_url_when_image_set(self) -> None:
        tenant_id, user_id = uuid.uuid4(), uuid.uuid4()
        service = InterviewTopicService(FakeInterviewTopicRepository(), FakePrivateObjectStorage())
        topic = _make_topic(tenant_id, user_id, image_key="interview-topics/x.jpg")

        url = await service.get_presigned_image_url(topic)

        assert url is not None
        assert "interview-topics/x.jpg" in url
