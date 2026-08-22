"""Unit tests for InterviewTopicService — fake repository/storage, no
database, no real object storage. Mirrors the fake-repository pattern
established in tests/unit/test_target_role_service.py.

FakeInterviewTopicRepository simulates the real many-to-many scope-tag
join table as a plain `dict[topic_id, dict[target_role_id, display_order]]`
— close enough to the real SqlAlchemyInterviewTopicRepository's shape
(same list_for_scope/move/remove_scope semantics) without a database.

Content is a freeform `blocks` document (2026-08-24 restructuring —
see app/domain/content_blocks/entities.py) rather than the old fixed
discussion/image_key/reference_links shape; the small `_rich_text_block`/
`_image_block`/`_external_link_block` helpers below build single-column
rows for test data, mirroring how the real frontend/API constructs one
column per new block.
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
from app.domain.interview_prep.entities import ArticleBlock, ArticleColumn, InterviewTopic

pytestmark = pytest.mark.unit


def _rich_text_block(html: str | None, *, label: str = "Discussion") -> ArticleBlock:
    return ArticleBlock(
        id=uuid.uuid4(),
        columns=[ArticleColumn(id=uuid.uuid4(), type="rich_text", label=label, html=html)],
    )


def _image_block(*, image_key: str | None = None, label: str = "Image") -> ArticleBlock:
    return ArticleBlock(
        id=uuid.uuid4(),
        columns=[ArticleColumn(id=uuid.uuid4(), type="image", label=label, image_key=image_key)],
    )


def _external_link_block(url: str, label: str) -> ArticleBlock:
    return ArticleBlock(
        id=uuid.uuid4(),
        columns=[
            ArticleColumn(id=uuid.uuid4(), type="external_link", label=label, external_url=url)
        ],
    )


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
            scope_target_role_ids=[None],
        )

        assert topic.name == "System Design"
        assert topic.section == "Technical"
        assert topic.blocks == []
        assert repo.topics[topic.id] is topic

    async def test_rejects_an_empty_scope_list(self) -> None:
        tenant_id, user_id = uuid.uuid4(), uuid.uuid4()
        service = InterviewTopicService(FakeInterviewTopicRepository(), FakePrivateObjectStorage())

        with pytest.raises(ValidationError):
            await service.add(
                tenant_id=tenant_id,
                user_id=user_id,
                name="System Design",
                section=None,
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
            scope_target_role_ids=[role_id, role_id, role_id],
        )

        assert topic.scope_target_role_ids == [role_id]


class TestUpdateAndDelete:
    async def test_update_sanitizes_rich_text_block_html(self) -> None:
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
            blocks=[_rich_text_block('<span style="color: red; background: url(x)">colored</span>')],
            scope_target_role_ids=[None],
        )

        assert updated.blocks[0].columns[0].html == '<span style="color: red;">colored</span>'

    async def test_update_saves_an_external_link_block(self) -> None:
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
            blocks=[_external_link_block("https://example.com", "Example")],
            scope_target_role_ids=[None],
        )

        column = updated.blocks[0].columns[0]
        assert column.external_url == "https://example.com"
        assert column.label == "Example"

    async def test_update_rejects_a_javascript_scheme_external_link(self) -> None:
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
                blocks=[_external_link_block("javascript:alert(document.cookie)", "Evil")],
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
                blocks=[],
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
                blocks=[],
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
            blocks=[],
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
            blocks=[],
            scope_target_role_ids=[role_id],
        )

        assert updated.scope_target_role_ids == [role_id]
        master_list = await repo.list_for_scope(tenant_id, user_id, None)
        assert master_list == []

    async def test_update_removing_an_image_column_deletes_its_object(self) -> None:
        tenant_id, user_id = uuid.uuid4(), uuid.uuid4()
        repo = FakeInterviewTopicRepository()
        topic = await repo.create(
            _make_topic(
                tenant_id, user_id, blocks=[_image_block(image_key="interview-topics/x/old.jpg")]
            )
        )
        storage = FakePrivateObjectStorage()
        service = InterviewTopicService(repo, storage)

        updated = await service.update(
            tenant_id=tenant_id,
            user_id=user_id,
            topic_id=topic.id,
            name=topic.name,
            section=None,
            blocks=[],  # image block removed entirely
            scope_target_role_ids=[None],
        )

        assert updated.blocks == []
        assert storage.deleted_keys == ["interview-topics/x/old.jpg"]

    async def test_update_keeping_an_image_column_does_not_delete_its_object(self) -> None:
        tenant_id, user_id = uuid.uuid4(), uuid.uuid4()
        repo = FakeInterviewTopicRepository()
        image_block = _image_block(image_key="interview-topics/x/keep.jpg")
        topic = await repo.create(_make_topic(tenant_id, user_id, blocks=[image_block]))
        storage = FakePrivateObjectStorage()
        service = InterviewTopicService(repo, storage)

        await service.update(
            tenant_id=tenant_id,
            user_id=user_id,
            topic_id=topic.id,
            name=topic.name,
            section=None,
            blocks=[image_block],  # unchanged
            scope_target_role_ids=[None],
        )

        assert storage.deleted_keys == []

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

    async def test_delete_best_effort_removes_every_image_column(self) -> None:
        tenant_id, user_id = uuid.uuid4(), uuid.uuid4()
        repo = FakeInterviewTopicRepository()
        topic = await repo.create(
            _make_topic(
                tenant_id,
                user_id,
                blocks=[
                    _image_block(image_key="interview-topics/x/a.jpg"),
                    ArticleBlock(
                        id=uuid.uuid4(),
                        columns=[
                            ArticleColumn(
                                id=uuid.uuid4(),
                                type="image",
                                label="Second",
                                image_key="interview-topics/x/b.jpg",
                            ),
                            ArticleColumn(id=uuid.uuid4(), type="rich_text", label="Text", html="<p>hi</p>"),
                        ],
                    ),
                ],
            )
        )
        storage = FakePrivateObjectStorage()
        service = InterviewTopicService(repo, storage)

        await service.delete(
            tenant_id=tenant_id,
            user_id=user_id,
            topic_id=topic.id,
            target_role_id=None,
            delete_everywhere=False,
        )

        assert set(storage.deleted_keys) == {"interview-topics/x/a.jpg", "interview-topics/x/b.jpg"}
        assert topic.id not in repo.topics

    async def test_delete_survives_storage_failure(self) -> None:
        tenant_id, user_id = uuid.uuid4(), uuid.uuid4()
        repo = FakeInterviewTopicRepository()
        topic = await repo.create(
            _make_topic(tenant_id, user_id, blocks=[_image_block(image_key="interview-topics/x.jpg")])
        )
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
    async def test_uploads_and_stores_the_key_on_the_right_column(self) -> None:
        tenant_id, user_id = uuid.uuid4(), uuid.uuid4()
        repo = FakeInterviewTopicRepository()
        image_block = _image_block()
        topic = await repo.create(_make_topic(tenant_id, user_id, blocks=[image_block]))
        storage = FakePrivateObjectStorage()
        service = InterviewTopicService(repo, storage)
        column_id = image_block.columns[0].id

        updated = await service.upload_image(
            tenant_id=tenant_id,
            user_id=user_id,
            topic_id=topic.id,
            column_id=column_id,
            content=b"fake-bytes",
            content_type="image/png",
        )

        key = updated.blocks[0].columns[0].image_key
        assert key is not None
        assert key in storage.uploaded

    async def test_finds_the_column_even_when_its_row_has_multiple_columns(self) -> None:
        tenant_id, user_id = uuid.uuid4(), uuid.uuid4()
        repo = FakeInterviewTopicRepository()
        text_column = ArticleColumn(id=uuid.uuid4(), type="rich_text", label="Text", html="<p>Hi</p>")
        image_column = ArticleColumn(id=uuid.uuid4(), type="image", label="Photo")
        row = ArticleBlock(id=uuid.uuid4(), columns=[text_column, image_column])
        topic = await repo.create(_make_topic(tenant_id, user_id, blocks=[row]))
        service = InterviewTopicService(repo, FakePrivateObjectStorage())

        updated = await service.upload_image(
            tenant_id=tenant_id,
            user_id=user_id,
            topic_id=topic.id,
            column_id=image_column.id,
            content=b"fake-bytes",
            content_type="image/png",
        )

        assert len(updated.blocks) == 1
        assert updated.blocks[0].columns[0].html == "<p>Hi</p>"  # untouched
        assert updated.blocks[0].columns[1].image_key is not None

    async def test_raises_not_found_for_an_unknown_column(self) -> None:
        tenant_id, user_id = uuid.uuid4(), uuid.uuid4()
        repo = FakeInterviewTopicRepository()
        topic = await repo.create(_make_topic(tenant_id, user_id))
        service = InterviewTopicService(repo, FakePrivateObjectStorage())

        with pytest.raises(NotFoundError):
            await service.upload_image(
                tenant_id=tenant_id,
                user_id=user_id,
                topic_id=topic.id,
                column_id=uuid.uuid4(),
                content=b"data",
                content_type="image/png",
            )

    async def test_replacing_an_image_deletes_the_old_one(self) -> None:
        tenant_id, user_id = uuid.uuid4(), uuid.uuid4()
        repo = FakeInterviewTopicRepository()
        image_block = _image_block(image_key="interview-topics/old.jpg")
        topic = await repo.create(_make_topic(tenant_id, user_id, blocks=[image_block]))
        storage = FakePrivateObjectStorage()
        service = InterviewTopicService(repo, storage)

        await service.upload_image(
            tenant_id=tenant_id,
            user_id=user_id,
            topic_id=topic.id,
            column_id=image_block.columns[0].id,
            content=b"new-bytes",
            content_type="image/png",
        )

        assert "interview-topics/old.jpg" in storage.deleted_keys

    async def test_rejects_unsupported_content_type(self) -> None:
        tenant_id, user_id = uuid.uuid4(), uuid.uuid4()
        repo = FakeInterviewTopicRepository()
        image_block = _image_block()
        topic = await repo.create(_make_topic(tenant_id, user_id, blocks=[image_block]))
        service = InterviewTopicService(repo, FakePrivateObjectStorage())

        with pytest.raises(ValidationError):
            await service.upload_image(
                tenant_id=tenant_id,
                user_id=user_id,
                topic_id=topic.id,
                column_id=image_block.columns[0].id,
                content=b"data",
                content_type="application/pdf",
            )

    async def test_rejects_oversized_image(self) -> None:
        tenant_id, user_id = uuid.uuid4(), uuid.uuid4()
        repo = FakeInterviewTopicRepository()
        image_block = _image_block()
        topic = await repo.create(_make_topic(tenant_id, user_id, blocks=[image_block]))
        service = InterviewTopicService(repo, FakePrivateObjectStorage())

        with pytest.raises(ValidationError):
            await service.upload_image(
                tenant_id=tenant_id,
                user_id=user_id,
                topic_id=topic.id,
                column_id=image_block.columns[0].id,
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


class TestPresignedImageUrls:
    async def test_returns_empty_when_no_image_columns(self) -> None:
        tenant_id, user_id = uuid.uuid4(), uuid.uuid4()
        service = InterviewTopicService(FakeInterviewTopicRepository(), FakePrivateObjectStorage())
        topic = _make_topic(tenant_id, user_id, blocks=[_rich_text_block("<p>hi</p>")])

        assert await service.get_presigned_image_urls(topic) == {}

    async def test_resolves_a_url_per_image_column(self) -> None:
        tenant_id, user_id = uuid.uuid4(), uuid.uuid4()
        service = InterviewTopicService(FakeInterviewTopicRepository(), FakePrivateObjectStorage())
        block = _image_block(image_key="interview-topics/x.jpg")
        topic = _make_topic(tenant_id, user_id, blocks=[block])

        urls = await service.get_presigned_image_urls(topic)

        column_id = block.columns[0].id
        assert column_id in urls
        assert "interview-topics/x.jpg" in urls[column_id]
