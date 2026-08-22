"""Unit tests for PublicSharingService — fake stand-ins for the three
services it composes (no database). Focused purely on the orchestration
contract: turning ON always ensures a share key exists, turning OFF
never mints one.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest

from app.application.showcase_page.public_sharing_service import PublicSharingService
from app.domain.interview_prep.entities import InterviewTopic
from app.domain.showcase_page.entities import ShareableResourceType, ShowcasePage

pytestmark = pytest.mark.unit


class FakeShowcasePageService:
    def __init__(self, page: ShowcasePage) -> None:
        self._page = page
        self.set_public_calls: list[bool] = []

    async def set_public(
        self,
        *,
        tenant_id: uuid.UUID,
        user_id: uuid.UUID,
        target_role_id: uuid.UUID,
        is_public: bool,
    ) -> ShowcasePage:
        self.set_public_calls.append(is_public)
        self._page.is_public = is_public
        return self._page


class FakeInterviewTopicService:
    def __init__(self, topic: InterviewTopic) -> None:
        self._topic = topic
        self.set_public_calls: list[bool] = []

    async def set_public(
        self, *, tenant_id: uuid.UUID, user_id: uuid.UUID, topic_id: uuid.UUID, is_public: bool
    ) -> InterviewTopic:
        self.set_public_calls.append(is_public)
        self._topic.is_public = is_public
        return self._topic


class FakePublicShareLinkService:
    def __init__(self) -> None:
        self.get_or_create_calls: list[tuple[ShareableResourceType, uuid.UUID]] = []

    async def get_or_create_key(
        self,
        *,
        tenant_id: uuid.UUID,
        user_id: uuid.UUID,
        resource_type: ShareableResourceType,
        resource_id: uuid.UUID,
    ) -> str:
        self.get_or_create_calls.append((resource_type, resource_id))
        return "minted-key"


def _make_page(
    *, tenant_id: uuid.UUID, user_id: uuid.UUID, target_role_id: uuid.UUID
) -> ShowcasePage:
    now = datetime.now(UTC)
    return ShowcasePage(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        user_id=user_id,
        target_role_id=target_role_id,
        created_at=now,
        updated_at=now,
    )


def _make_topic(*, tenant_id: uuid.UUID, user_id: uuid.UUID) -> InterviewTopic:
    now = datetime.now(UTC)
    return InterviewTopic(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        user_id=user_id,
        name="System Design",
        scope_target_role_ids=[None],
        created_at=now,
        updated_at=now,
    )


class TestSetShowcasePagePublic:
    async def test_turning_on_mints_a_share_key(self) -> None:
        tenant_id, user_id, role_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
        page = _make_page(tenant_id=tenant_id, user_id=user_id, target_role_id=role_id)
        pages = FakeShowcasePageService(page)
        topics = FakeInterviewTopicService(_make_topic(tenant_id=tenant_id, user_id=user_id))
        links = FakePublicShareLinkService()
        service = PublicSharingService(pages, topics, links)  # type: ignore[arg-type]

        result_page, share_key = await service.set_showcase_page_public(
            tenant_id=tenant_id, user_id=user_id, target_role_id=role_id, is_public=True
        )

        assert result_page.is_public is True
        assert share_key == "minted-key"
        assert links.get_or_create_calls == [("showcase_page", page.id)]

    async def test_turning_off_never_mints_a_share_key(self) -> None:
        tenant_id, user_id, role_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
        page = _make_page(tenant_id=tenant_id, user_id=user_id, target_role_id=role_id)
        pages = FakeShowcasePageService(page)
        topics = FakeInterviewTopicService(_make_topic(tenant_id=tenant_id, user_id=user_id))
        links = FakePublicShareLinkService()
        service = PublicSharingService(pages, topics, links)  # type: ignore[arg-type]

        result_page, share_key = await service.set_showcase_page_public(
            tenant_id=tenant_id, user_id=user_id, target_role_id=role_id, is_public=False
        )

        assert result_page.is_public is False
        assert share_key is None
        assert links.get_or_create_calls == []


class TestSetInterviewTopicPublic:
    async def test_turning_on_mints_a_share_key(self) -> None:
        tenant_id, user_id = uuid.uuid4(), uuid.uuid4()
        topic = _make_topic(tenant_id=tenant_id, user_id=user_id)
        pages = FakeShowcasePageService(
            _make_page(tenant_id=tenant_id, user_id=user_id, target_role_id=uuid.uuid4())
        )
        topics = FakeInterviewTopicService(topic)
        links = FakePublicShareLinkService()
        service = PublicSharingService(pages, topics, links)  # type: ignore[arg-type]

        result_topic, share_key = await service.set_interview_topic_public(
            tenant_id=tenant_id, user_id=user_id, topic_id=topic.id, is_public=True
        )

        assert result_topic.is_public is True
        assert share_key == "minted-key"
        assert links.get_or_create_calls == [("interview_topic", topic.id)]

    async def test_turning_off_never_mints_a_share_key(self) -> None:
        tenant_id, user_id = uuid.uuid4(), uuid.uuid4()
        topic = _make_topic(tenant_id=tenant_id, user_id=user_id)
        pages = FakeShowcasePageService(
            _make_page(tenant_id=tenant_id, user_id=user_id, target_role_id=uuid.uuid4())
        )
        topics = FakeInterviewTopicService(topic)
        links = FakePublicShareLinkService()
        service = PublicSharingService(pages, topics, links)  # type: ignore[arg-type]

        result_topic, share_key = await service.set_interview_topic_public(
            tenant_id=tenant_id, user_id=user_id, topic_id=topic.id, is_public=False
        )

        assert result_topic.is_public is False
        assert share_key is None
        assert links.get_or_create_calls == []
