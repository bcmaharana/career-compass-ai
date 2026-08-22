"""Unit tests for InterviewTopicService — fake repository/storage, no
database, no real object storage. Mirrors the fake-repository pattern
established in tests/unit/test_target_role_service.py.

FakeInterviewTopicRepository simulates the real many-to-many scope-tag
join table as a plain `dict[topic_id, dict[target_role_id, display_order]]`
— close enough to the real SqlAlchemyInterviewTopicRepository's shape
(same list_for_scope/move/remove_scope semantics) without a database.
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
        self.tags: dict[uuid.UUID, dict[uuid.UUID | None, int]] = {}
        self._order_counters: dict[tuple[uuid.UUID, uuid.UUID | None], int] = {}

    def _next_order(self, user_id: uuid.UUID, target_role_id: uuid.UUID | None) -> int:
        key = (user_id, target_role_id)
        self._order_counters[key] = self._order_counters.get(key, 0) + 1
        return self._order_counters[key]

    async def create(self, topic: InterviewTopic) -> InterviewTopic:
        self.topics[topic.id] = topic
        self.tags[topic.id] = {
            rid: self._next_order(topic.user_id, rid) for rid in topic.scope_target_role_ids
        }
        return topic

    async def get_by_id(self, tenant_id: uuid.UUID, topic_id: uuid.UUID) -> InterviewTopic | None:
        topic = self.topics.get(topic_id)
        if topic is None or topic.tenant_id != tenant_id:
            return None
        topic.scope_target_role_ids = list(self.tags.get(topic_id, {}).keys())
        return topic

    async def list_for_scope(
        self, tenant_id: uuid.UUID, user_id: uuid.UUID, target_role_id: uuid.UUID | None
    ) -> list[InterviewTopic]:
        matches: list[tuple[int, InterviewTopic]] = []
        for topic_id, tag_map in self.tags.items():
            if target_role_id not in tag_map:
                continue
            topic = self.topics.get(topic_id)
            if topic is None or topic.tenant_id != tenant_id or topic.user_id != user_id:
                continue
            matches.append((tag_map[target_role_id], topic))
        matches.sort(key=lambda pair: pair[0])
        for _, topic in matches:
            topic.scope_target_role_ids = list(self.tags[topic.id].keys())
        return [topic for _, topic in matches]

    async def update(self, topic: InterviewTopic) -> InterviewTopic:
        self.topics[topic.id] = topic
        current = self.tags.setdefault(topic.id, {})
        desired = set(topic.scope_target_role_ids)
        for rid in list(current.keys()):
            if rid not in desired:
                del current[rid]
        for rid in desired - set(current.keys()):
            current[rid] = self._next_order(topic.user_id, rid)
        return topic

    async def soft_delete(self, tenant_id: uuid.UUID, topic_id: uuid.UUID) -> None:
        self.topics.pop(topic_id, None)
        self.tags.pop(topic_id, None)

    async def remove_scope(
        self, tenant_id: uuid.UUID, topic_id: uuid.UUID, target_role_id: uuid.UUID | None
    ) -> None:
        if topic_id in self.tags:
            self.tags[topic_id].pop(target_role_id, None)

    async def move(
        self, tenant_id: uuid.UUID, topic_id: uuid.UUID, target_role_id: uuid.UUID | None, direction: str
    ) -> None:
        items = await self.list_for_scope(tenant_id, self.topics[topic_id].user_id, target_role_id)
        index = next((i for i, t in enumerate(items) if t.id == topic_id), None)
        if index is None:
            return
        neighbor_index = index - 1 if direction == "up" else index + 1
        if neighbor_index < 0 or neighbor_index >= len(items):
            return
        neighbor_id = items[neighbor_index].id
        self.tags[topic_id][target_role_id], self.tags[neighbor_id][target_role_id] = (
            self.tags[neighbor_id][target_role_id],
            self.tags[topic_id][target_role_id],
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
        name="System Design",
        scope_target_role_ids=[None],
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
            name="System Design",
            section="Technical",
            discussion="Notes here.",
            scope_target_role_ids=[None],
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
            name="System Design",
            section=None,
            discussion='<i>Notes</i><script>alert(1)</script>',
            scope_target_role_ids=[None],
        )

        assert topic.discussion == "<i>Notes</i>alert(1)"

    async def test_rejects_an_empty_scope_list(self) -> None:
        tenant_id, user_id = uuid.uuid4(), uuid.uuid4()
        service = InterviewTopicService(FakeInterviewTopicRepository(), FakePrivateObjectStorage())

        with pytest.raises(ValidationError):
            await service.add(
                tenant_id=tenant_id,
                user_id=user_id,
                name="System Design",
                section=None,
                discussion=None,
                scope_target_role_ids=[],
            )

    async def test_tags_into_multiple_scopes_including_master_and_a_role(self) -> None:
        tenant_id, user_id = uuid.uuid4(), uuid.uuid4()
        role_id = uuid.uuid4()
        repo = FakeInterviewTopicRepository()
        service = InterviewTopicService(repo, FakePrivateObjectStorage())

        topic = await service.add(
            tenant_id=tenant_id,
            user_id=user_id,
            name="Cross-tagged topic",
            section=None,
            discussion=None,
            scope_target_role_ids=[None, role_id],
        )

        assert set(topic.scope_target_role_ids) == {None, role_id}
        master_list = await repo.list_for_scope(tenant_id, user_id, None)
        role_list = await repo.list_for_scope(tenant_id, user_id, role_id)
        assert [t.id for t in master_list] == [topic.id]
        assert [t.id for t in role_list] == [topic.id]

    async def test_duplicate_scopes_are_deduplicated(self) -> None:
        tenant_id, user_id = uuid.uuid4(), uuid.uuid4()
        role_id = uuid.uuid4()
        repo = FakeInterviewTopicRepository()
        service = InterviewTopicService(repo, FakePrivateObjectStorage())

        topic = await service.add(
            tenant_id=tenant_id,
            user_id=user_id,
            name="Deduped topic",
            section=None,
            discussion=None,
            scope_target_role_ids=[role_id, role_id, role_id],
        )

        assert topic.scope_target_role_ids == [role_id]


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
            scope_target_role_ids=[None],
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
            scope_target_role_ids=[None],
        )

        assert updated.reference_links == [ReferenceLink(url="https://example.com", label="Example")]

    async def test_update_rejects_a_javascript_scheme_reference_link(self) -> None:
        tenant_id, user_id = uuid.uuid4(), uuid.uuid4()
        repo = FakeInterviewTopicRepository()
        topic = await repo.create(_make_topic(tenant_id, user_id))
        service = InterviewTopicService(repo, FakePrivateObjectStorage())

        with pytest.raises(ValidationError):
            await service.update(
                tenant_id=tenant_id,
                user_id=user_id,
                topic_id=topic.id,
                name=topic.name,
                section=None,
                discussion=None,
                reference_links=[
                    ReferenceLink(url="javascript:alert(document.cookie)", label="Evil")
                ],
                scope_target_role_ids=[None],
            )

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
                scope_target_role_ids=[None],
            )

    async def test_update_rejects_an_empty_scope_list(self) -> None:
        tenant_id, user_id = uuid.uuid4(), uuid.uuid4()
        repo = FakeInterviewTopicRepository()
        topic = await repo.create(_make_topic(tenant_id, user_id))
        service = InterviewTopicService(repo, FakePrivateObjectStorage())

        with pytest.raises(ValidationError):
            await service.update(
                tenant_id=tenant_id,
                user_id=user_id,
                topic_id=topic.id,
                name=topic.name,
                section=None,
                discussion=None,
                reference_links=[],
                scope_target_role_ids=[],
            )

    async def test_update_can_add_a_scope_tag(self) -> None:
        tenant_id, user_id = uuid.uuid4(), uuid.uuid4()
        role_id = uuid.uuid4()
        repo = FakeInterviewTopicRepository()
        topic = await repo.create(_make_topic(tenant_id, user_id))  # Master only
        service = InterviewTopicService(repo, FakePrivateObjectStorage())

        updated = await service.update(
            tenant_id=tenant_id,
            user_id=user_id,
            topic_id=topic.id,
            name=topic.name,
            section=None,
            discussion=None,
            reference_links=[],
            scope_target_role_ids=[None, role_id],
        )

        assert set(updated.scope_target_role_ids) == {None, role_id}
        role_list = await repo.list_for_scope(tenant_id, user_id, role_id)
        assert [t.id for t in role_list] == [topic.id]

    async def test_update_can_remove_the_original_scope_entirely(self) -> None:
        tenant_id, user_id = uuid.uuid4(), uuid.uuid4()
        role_id = uuid.uuid4()
        repo = FakeInterviewTopicRepository()
        topic = await repo.create(_make_topic(tenant_id, user_id))  # Master only
        service = InterviewTopicService(repo, FakePrivateObjectStorage())

        updated = await service.update(
            tenant_id=tenant_id,
            user_id=user_id,
            topic_id=topic.id,
            name=topic.name,
            section=None,
            discussion=None,
            reference_links=[],
            scope_target_role_ids=[role_id],
        )

        assert updated.scope_target_role_ids == [role_id]
        master_list = await repo.list_for_scope(tenant_id, user_id, None)
        assert master_list == []

    async def test_delete_removes_everywhere_when_only_one_scope(self) -> None:
        tenant_id, user_id = uuid.uuid4(), uuid.uuid4()
        repo = FakeInterviewTopicRepository()
        topic = await repo.create(_make_topic(tenant_id, user_id))
        service = InterviewTopicService(repo, FakePrivateObjectStorage())

        await service.delete(
            tenant_id=tenant_id,
            user_id=user_id,
            topic_id=topic.id,
            target_role_id=None,
            delete_everywhere=False,
        )

        assert topic.id not in repo.topics

    async def test_delete_from_just_this_scope_leaves_the_topic_visible_elsewhere(self) -> None:
        tenant_id, user_id = uuid.uuid4(), uuid.uuid4()
        role_id = uuid.uuid4()
        repo = FakeInterviewTopicRepository()
        topic = await repo.create(_make_topic(tenant_id, user_id, scope_target_role_ids=[None, role_id]))
        service = InterviewTopicService(repo, FakePrivateObjectStorage())

        await service.delete(
            tenant_id=tenant_id,
            user_id=user_id,
            topic_id=topic.id,
            target_role_id=None,
            delete_everywhere=False,
        )

        assert topic.id in repo.topics
        master_list = await repo.list_for_scope(tenant_id, user_id, None)
        role_list = await repo.list_for_scope(tenant_id, user_id, role_id)
        assert master_list == []
        assert [t.id for t in role_list] == [topic.id]

    async def test_delete_everywhere_removes_it_from_every_tagged_scope(self) -> None:
        tenant_id, user_id = uuid.uuid4(), uuid.uuid4()
        role_id = uuid.uuid4()
        repo = FakeInterviewTopicRepository()
        topic = await repo.create(_make_topic(tenant_id, user_id, scope_target_role_ids=[None, role_id]))
        service = InterviewTopicService(repo, FakePrivateObjectStorage())

        await service.delete(
            tenant_id=tenant_id,
            user_id=user_id,
            topic_id=topic.id,
            target_role_id=None,
            delete_everywhere=True,
        )

        assert topic.id not in repo.topics

    async def test_delete_best_effort_removes_image(self) -> None:
        tenant_id, user_id = uuid.uuid4(), uuid.uuid4()
        repo = FakeInterviewTopicRepository()
        topic = await repo.create(_make_topic(tenant_id, user_id, image_key="interview-topics/x.jpg"))
        storage = FakePrivateObjectStorage()
        service = InterviewTopicService(repo, storage)

        await service.delete(
            tenant_id=tenant_id,
            user_id=user_id,
            topic_id=topic.id,
            target_role_id=None,
            delete_everywhere=False,
        )

        assert storage.deleted_keys == ["interview-topics/x.jpg"]
        assert topic.id not in repo.topics

    async def test_delete_survives_storage_failure(self) -> None:
        tenant_id, user_id = uuid.uuid4(), uuid.uuid4()
        repo = FakeInterviewTopicRepository()
        topic = await repo.create(_make_topic(tenant_id, user_id, image_key="interview-topics/x.jpg"))
        storage = FakePrivateObjectStorage(fail_delete=True)
        service = InterviewTopicService(repo, storage)

        await service.delete(
            tenant_id=tenant_id,
            user_id=user_id,
            topic_id=topic.id,
            target_role_id=None,
            delete_everywhere=False,
        )

        assert topic.id not in repo.topics


class TestMove:
    async def test_move_swaps_display_order_within_scope(self) -> None:
        tenant_id, user_id = uuid.uuid4(), uuid.uuid4()
        repo = FakeInterviewTopicRepository()
        first = await repo.create(_make_topic(tenant_id, user_id, name="First"))
        second = await repo.create(_make_topic(tenant_id, user_id, name="Second"))
        service = InterviewTopicService(repo, FakePrivateObjectStorage())

        await service.move(
            tenant_id=tenant_id, user_id=user_id, topic_id=second.id, target_role_id=None, direction="up"
        )

        ordered = await repo.list_for_scope(tenant_id, user_id, None)
        assert [t.id for t in ordered] == [second.id, first.id]

    async def test_move_is_independent_per_scope(self) -> None:
        tenant_id, user_id = uuid.uuid4(), uuid.uuid4()
        role_id = uuid.uuid4()
        repo = FakeInterviewTopicRepository()
        # Both topics tagged to Master AND role_id, in the same relative order.
        first = await repo.create(
            _make_topic(tenant_id, user_id, name="First", scope_target_role_ids=[None, role_id])
        )
        second = await repo.create(
            _make_topic(tenant_id, user_id, name="Second", scope_target_role_ids=[None, role_id])
        )
        service = InterviewTopicService(repo, FakePrivateObjectStorage())

        # Move "second" up only within the role_id scope.
        await service.move(
            tenant_id=tenant_id,
            user_id=user_id,
            topic_id=second.id,
            target_role_id=role_id,
            direction="up",
        )

        role_ordered = await repo.list_for_scope(tenant_id, user_id, role_id)
        master_ordered = await repo.list_for_scope(tenant_id, user_id, None)
        assert [t.id for t in role_ordered] == [second.id, first.id]
        assert [t.id for t in master_ordered] == [first.id, second.id]


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


class TestSetPublic:
    async def test_flips_the_flag_on(self) -> None:
        tenant_id, user_id = uuid.uuid4(), uuid.uuid4()
        repo = FakeInterviewTopicRepository()
        topic = await repo.create(_make_topic(tenant_id, user_id))
        service = InterviewTopicService(repo, FakePrivateObjectStorage())

        updated = await service.set_public(
            tenant_id=tenant_id, user_id=user_id, topic_id=topic.id, is_public=True
        )

        assert updated.is_public is True

    async def test_flips_the_flag_off(self) -> None:
        tenant_id, user_id = uuid.uuid4(), uuid.uuid4()
        repo = FakeInterviewTopicRepository()
        topic = await repo.create(_make_topic(tenant_id, user_id, is_public=True))
        service = InterviewTopicService(repo, FakePrivateObjectStorage())

        updated = await service.set_public(
            tenant_id=tenant_id, user_id=user_id, topic_id=topic.id, is_public=False
        )

        assert updated.is_public is False

    async def test_requires_ownership(self) -> None:
        tenant_id, user_id, other_user = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
        repo = FakeInterviewTopicRepository()
        topic = await repo.create(_make_topic(tenant_id, user_id))
        service = InterviewTopicService(repo, FakePrivateObjectStorage())

        with pytest.raises(NotFoundError):
            await service.set_public(
                tenant_id=tenant_id, user_id=other_user, topic_id=topic.id, is_public=True
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
