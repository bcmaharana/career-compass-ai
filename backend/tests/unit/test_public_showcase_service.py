"""Unit tests for PublicShowcaseService — the anonymous read path. Fake
repositories/binder, no database. Focused on the contract that matters
most for this service: a share key resolves ONLY when it exists, points
at the right resource type, AND the live resource is still public — and
every failure mode returns None (never a distinguishing error).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest

from app.application.showcase_page.public_showcase_service import PublicShowcaseService
from app.domain.career_profile.entities import TargetRole
from app.domain.identity.entities import User
from app.domain.interview_prep.entities import ArticleBlock, ArticleColumn, InterviewTopic
from app.domain.showcase_page.entities import (
    PublicShareLink,
    ShowcaseBlock,
    ShowcaseColumn,
    ShowcasePage,
)

pytestmark = pytest.mark.unit


class FakePublicShareLinkRepository:
    def __init__(self) -> None:
        self.by_key: dict[str, PublicShareLink] = {}

    async def get_by_key(self, share_key: str) -> PublicShareLink | None:
        return self.by_key.get(share_key)

    async def get_by_resource(
        self, resource_type: str, resource_id: uuid.UUID
    ) -> PublicShareLink | None:
        for link in self.by_key.values():
            if link.resource_type == resource_type and link.resource_id == resource_id:
                return link
        return None

    async def create(self, link: PublicShareLink) -> PublicShareLink:
        raise NotImplementedError("not used by PublicShowcaseService")


class FakeTenantContextBinder:
    def __init__(self) -> None:
        self.bound: list[uuid.UUID] = []

    async def bind(self, tenant_id: uuid.UUID) -> None:
        self.bound.append(tenant_id)


class FakeShowcasePageRepository:
    def __init__(self) -> None:
        self.pages: dict[uuid.UUID, ShowcasePage] = {}

    async def create(self, page: ShowcasePage) -> ShowcasePage:
        raise NotImplementedError

    async def get_by_target_role(
        self, tenant_id: uuid.UUID, target_role_id: uuid.UUID
    ) -> ShowcasePage | None:
        raise NotImplementedError

    async def get_by_id(self, tenant_id: uuid.UUID, page_id: uuid.UUID) -> ShowcasePage | None:
        page = self.pages.get(page_id)
        return page if page and page.tenant_id == tenant_id else None

    async def update(self, page: ShowcasePage) -> ShowcasePage:
        raise NotImplementedError


class FakeInterviewTopicRepository:
    def __init__(self) -> None:
        self.topics: dict[uuid.UUID, InterviewTopic] = {}

    async def get_by_id(self, tenant_id: uuid.UUID, topic_id: uuid.UUID) -> InterviewTopic | None:
        topic = self.topics.get(topic_id)
        return topic if topic and topic.tenant_id == tenant_id else None


class FakeTargetRoleRepository:
    def __init__(self) -> None:
        self.roles: dict[uuid.UUID, TargetRole] = {}

    async def get_by_id(self, tenant_id: uuid.UUID, target_role_id: uuid.UUID) -> TargetRole | None:
        role = self.roles.get(target_role_id)
        return role if role and role.tenant_id == tenant_id else None


class FakeUserRepository:
    def __init__(self) -> None:
        self.users: dict[uuid.UUID, User] = {}

    async def get_by_id(self, tenant_id: uuid.UUID, user_id: uuid.UUID) -> User | None:
        user = self.users.get(user_id)
        return user if user and user.tenant_id == tenant_id else None


class FakeStorage:
    async def get_presigned_url(
        self, *, key: str, expires_in_seconds: int = 300, download_filename: str | None = None
    ) -> str:
        return f"https://example.test/{key}"


def _make_user(*, tenant_id: uuid.UUID) -> User:
    now = datetime.now(UTC)
    return User(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        org_id=None,
        email="jordan@example.com",
        salutation=None,
        first_name="Jordan",
        last_name="Rivera",
        hashed_password="x",
        status="active",
        mfa_enabled=False,
        created_at=now,
        updated_at=now,
        handle="JR",
    )


class _Fixture:
    def __init__(self) -> None:
        self.share_links = FakePublicShareLinkRepository()
        self.tenant_context = FakeTenantContextBinder()
        self.pages = FakeShowcasePageRepository()
        self.topics = FakeInterviewTopicRepository()
        self.target_roles = FakeTargetRoleRepository()
        self.users = FakeUserRepository()
        self.storage = FakeStorage()
        self.service = PublicShowcaseService(
            self.share_links,
            self.tenant_context,
            self.pages,
            self.topics,  # type: ignore[arg-type]
            self.target_roles,  # type: ignore[arg-type]
            self.users,  # type: ignore[arg-type]
            self.storage,  # type: ignore[arg-type]
        )


class TestGetShowcasePage:
    async def test_returns_none_for_an_unknown_key(self) -> None:
        fx = _Fixture()

        assert await fx.service.get_showcase_page("nope") is None
        assert fx.tenant_context.bound == []

    async def test_returns_none_when_the_key_points_at_a_different_resource_type(self) -> None:
        fx = _Fixture()
        tenant_id, user_id, resource_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
        fx.share_links.by_key["k"] = PublicShareLink(
            share_key="k",
            tenant_id=tenant_id,
            resource_type="interview_topic",
            resource_id=resource_id,
            user_id=user_id,
            created_at=datetime.now(UTC),
        )

        assert await fx.service.get_showcase_page("k") is None

    async def test_returns_none_when_the_page_is_now_private(self) -> None:
        fx = _Fixture()
        tenant_id, user_id, role_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
        page = ShowcasePage(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            user_id=user_id,
            target_role_id=role_id,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
            is_public=False,
        )
        fx.pages.pages[page.id] = page
        fx.share_links.by_key["k"] = PublicShareLink(
            share_key="k",
            tenant_id=tenant_id,
            resource_type="showcase_page",
            resource_id=page.id,
            user_id=user_id,
            created_at=datetime.now(UTC),
        )

        assert await fx.service.get_showcase_page("k") is None
        # The lookup binds tenant context before checking is_public.
        assert fx.tenant_context.bound == [tenant_id]

    async def test_returns_the_page_view_when_public(self) -> None:
        fx = _Fixture()
        tenant_id, user_id, role_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
        page = ShowcasePage(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            user_id=user_id,
            target_role_id=role_id,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
            is_public=True,
        )
        fx.pages.pages[page.id] = page
        fx.target_roles.roles[role_id] = TargetRole(
            id=role_id,
            tenant_id=tenant_id,
            user_id=user_id,
            role_name="Senior Engineer",
            tag="SE",
            created_at=datetime.now(UTC),
        )
        fx.users.users[user_id] = _make_user(tenant_id=tenant_id)
        fx.share_links.by_key["k"] = PublicShareLink(
            share_key="k",
            tenant_id=tenant_id,
            resource_type="showcase_page",
            resource_id=page.id,
            user_id=user_id,
            created_at=datetime.now(UTC),
        )

        view = await fx.service.get_showcase_page("k")

        assert view is not None
        assert view.page.id == page.id
        assert view.role_name == "Senior Engineer"
        assert view.role_tag == "SE"
        assert view.owner_handle == "JR"

    async def test_resolves_a_share_key_for_a_public_linked_article(self) -> None:
        fx = _Fixture()
        tenant_id, user_id, role_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
        topic = InterviewTopic(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            user_id=user_id,
            name="System Design",
            scope_target_role_ids=[None],
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
            is_public=True,
        )
        fx.topics.topics[topic.id] = topic
        fx.share_links.by_key["article-key"] = PublicShareLink(
            share_key="article-key",
            tenant_id=tenant_id,
            resource_type="interview_topic",
            resource_id=topic.id,
            user_id=user_id,
            created_at=datetime.now(UTC),
        )
        page = ShowcasePage(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            user_id=user_id,
            target_role_id=role_id,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
            is_public=True,
            blocks=[
                ShowcaseBlock(
                    id=uuid.uuid4(),
                    columns=[
                        ShowcaseColumn(
                            id=uuid.uuid4(),
                            type="article_link",
                            label="Read more",
                            article_topic_id=topic.id,
                        )
                    ],
                )
            ],
        )
        fx.pages.pages[page.id] = page
        fx.target_roles.roles[role_id] = TargetRole(
            id=role_id,
            tenant_id=tenant_id,
            user_id=user_id,
            role_name="Senior Engineer",
            tag="SE",
            created_at=datetime.now(UTC),
        )
        fx.users.users[user_id] = _make_user(tenant_id=tenant_id)
        fx.share_links.by_key["k"] = PublicShareLink(
            share_key="k",
            tenant_id=tenant_id,
            resource_type="showcase_page",
            resource_id=page.id,
            user_id=user_id,
            created_at=datetime.now(UTC),
        )

        view = await fx.service.get_showcase_page("k")

        assert view is not None
        assert view.article_share_keys == {topic.id: "article-key"}

    async def test_omits_the_entry_for_a_now_private_linked_article(self) -> None:
        fx = _Fixture()
        tenant_id, user_id, role_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
        topic = InterviewTopic(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            user_id=user_id,
            name="System Design",
            scope_target_role_ids=[None],
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
            is_public=False,
        )
        fx.topics.topics[topic.id] = topic
        page = ShowcasePage(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            user_id=user_id,
            target_role_id=role_id,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
            is_public=True,
            blocks=[
                ShowcaseBlock(
                    id=uuid.uuid4(),
                    columns=[
                        ShowcaseColumn(
                            id=uuid.uuid4(),
                            type="article_link",
                            label="Read more",
                            article_topic_id=topic.id,
                        )
                    ],
                )
            ],
        )
        fx.pages.pages[page.id] = page
        fx.target_roles.roles[role_id] = TargetRole(
            id=role_id,
            tenant_id=tenant_id,
            user_id=user_id,
            role_name="Senior Engineer",
            tag="SE",
            created_at=datetime.now(UTC),
        )
        fx.users.users[user_id] = _make_user(tenant_id=tenant_id)
        fx.share_links.by_key["k"] = PublicShareLink(
            share_key="k",
            tenant_id=tenant_id,
            resource_type="showcase_page",
            resource_id=page.id,
            user_id=user_id,
            created_at=datetime.now(UTC),
        )

        view = await fx.service.get_showcase_page("k")

        assert view is not None
        assert view.article_share_keys == {}

    async def test_returns_none_when_the_owning_target_role_is_gone(self) -> None:
        fx = _Fixture()
        tenant_id, user_id, role_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
        page = ShowcasePage(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            user_id=user_id,
            target_role_id=role_id,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
            is_public=True,
        )
        fx.pages.pages[page.id] = page
        fx.users.users[user_id] = _make_user(tenant_id=tenant_id)
        # Deliberately no target role registered.
        fx.share_links.by_key["k"] = PublicShareLink(
            share_key="k",
            tenant_id=tenant_id,
            resource_type="showcase_page",
            resource_id=page.id,
            user_id=user_id,
            created_at=datetime.now(UTC),
        )

        assert await fx.service.get_showcase_page("k") is None


class TestGetArticle:
    async def test_returns_none_for_an_unknown_key(self) -> None:
        fx = _Fixture()

        assert await fx.service.get_article("nope") is None

    async def test_returns_none_when_the_topic_is_now_private(self) -> None:
        fx = _Fixture()
        tenant_id, user_id = uuid.uuid4(), uuid.uuid4()
        topic = InterviewTopic(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            user_id=user_id,
            name="System Design",
            scope_target_role_ids=[None],
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
            is_public=False,
        )
        fx.topics.topics[topic.id] = topic
        fx.share_links.by_key["k"] = PublicShareLink(
            share_key="k",
            tenant_id=tenant_id,
            resource_type="interview_topic",
            resource_id=topic.id,
            user_id=user_id,
            created_at=datetime.now(UTC),
        )

        assert await fx.service.get_article("k") is None

    async def test_returns_the_article_view_when_public(self) -> None:
        fx = _Fixture()
        tenant_id, user_id = uuid.uuid4(), uuid.uuid4()
        image_column = ArticleColumn(
            id=uuid.uuid4(), type="image", label="Photo", image_key="interview-topics/x.jpg"
        )
        topic = InterviewTopic(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            user_id=user_id,
            name="System Design",
            blocks=[
                ArticleBlock(
                    id=uuid.uuid4(),
                    columns=[
                        ArticleColumn(id=uuid.uuid4(), type="rich_text", label="Notes", html="<p>Notes</p>")
                    ],
                ),
                ArticleBlock(id=uuid.uuid4(), columns=[image_column]),
            ],
            scope_target_role_ids=[None],
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
            is_public=True,
        )
        fx.topics.topics[topic.id] = topic
        fx.users.users[user_id] = _make_user(tenant_id=tenant_id)
        fx.share_links.by_key["k"] = PublicShareLink(
            share_key="k",
            tenant_id=tenant_id,
            resource_type="interview_topic",
            resource_id=topic.id,
            user_id=user_id,
            created_at=datetime.now(UTC),
        )

        view = await fx.service.get_article("k")

        assert view is not None
        assert view.topic.name == "System Design"
        assert view.owner_handle == "JR"
        assert view.image_urls[image_column.id] == "https://example.test/interview-topics/x.jpg"
