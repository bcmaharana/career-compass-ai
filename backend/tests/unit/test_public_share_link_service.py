"""Unit tests for PublicShareLinkService — fake repository/handle
service, no database."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest

from app.application.showcase_page.public_share_link_service import PublicShareLinkService
from app.domain.showcase_page.entities import PublicShareLink, ShareableResourceType

pytestmark = pytest.mark.unit


class FakePublicShareLinkRepository:
    def __init__(self) -> None:
        self.by_key: dict[str, PublicShareLink] = {}

    async def get_by_key(self, share_key: str) -> PublicShareLink | None:
        return self.by_key.get(share_key)

    async def get_by_resource(
        self, resource_type: ShareableResourceType, resource_id: uuid.UUID
    ) -> PublicShareLink | None:
        for link in self.by_key.values():
            if link.resource_type == resource_type and link.resource_id == resource_id:
                return link
        return None

    async def create(self, link: PublicShareLink) -> PublicShareLink:
        self.by_key[link.share_key] = link
        return link


class FakeHandleService:
    def __init__(self) -> None:
        self.ensure_calls: list[tuple[uuid.UUID, uuid.UUID]] = []

    async def ensure_handle(self, *, tenant_id: uuid.UUID, user_id: uuid.UUID) -> str:
        self.ensure_calls.append((tenant_id, user_id))
        return "BCM"


class TestGetOrCreateKey:
    async def test_mints_a_new_key_and_ensures_a_handle(self) -> None:
        tenant_id, user_id, resource_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
        links = FakePublicShareLinkRepository()
        handles = FakeHandleService()
        service = PublicShareLinkService(links, handles)  # type: ignore[arg-type]

        key = await service.get_or_create_key(
            tenant_id=tenant_id,
            user_id=user_id,
            resource_type="showcase_page",
            resource_id=resource_id,
        )

        assert key in links.by_key
        assert links.by_key[key].resource_id == resource_id
        assert links.by_key[key].resource_type == "showcase_page"
        assert handles.ensure_calls == [(tenant_id, user_id)]

    async def test_reuses_an_existing_key_without_minting_a_new_one(self) -> None:
        tenant_id, user_id, resource_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
        links = FakePublicShareLinkRepository()
        existing = PublicShareLink(
            share_key="existing-key",
            tenant_id=tenant_id,
            resource_type="interview_topic",
            resource_id=resource_id,
            user_id=user_id,
            created_at=datetime.now(UTC),
        )
        links.by_key[existing.share_key] = existing
        handles = FakeHandleService()
        service = PublicShareLinkService(links, handles)  # type: ignore[arg-type]

        key = await service.get_or_create_key(
            tenant_id=tenant_id,
            user_id=user_id,
            resource_type="interview_topic",
            resource_id=resource_id,
        )

        assert key == "existing-key"
        assert len(links.by_key) == 1
        assert handles.ensure_calls == []

    async def test_re_toggling_public_reuses_the_same_key(self) -> None:
        tenant_id, user_id, resource_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
        links = FakePublicShareLinkRepository()
        handles = FakeHandleService()
        service = PublicShareLinkService(links, handles)  # type: ignore[arg-type]

        first = await service.get_or_create_key(
            tenant_id=tenant_id,
            user_id=user_id,
            resource_type="showcase_page",
            resource_id=resource_id,
        )
        second = await service.get_or_create_key(
            tenant_id=tenant_id,
            user_id=user_id,
            resource_type="showcase_page",
            resource_id=resource_id,
        )

        assert first == second
        assert len(links.by_key) == 1


class TestGetExistingKey:
    async def test_returns_none_when_never_made_public(self) -> None:
        service = PublicShareLinkService(
            FakePublicShareLinkRepository(), FakeHandleService()  # type: ignore[arg-type]
        )

        key = await service.get_existing_key(
            resource_type="showcase_page", resource_id=uuid.uuid4()
        )

        assert key is None

    async def test_returns_the_key_without_minting_a_new_one(self) -> None:
        tenant_id, user_id, resource_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
        links = FakePublicShareLinkRepository()
        existing = PublicShareLink(
            share_key="already-there",
            tenant_id=tenant_id,
            resource_type="showcase_page",
            resource_id=resource_id,
            user_id=user_id,
            created_at=datetime.now(UTC),
        )
        links.by_key[existing.share_key] = existing
        handles = FakeHandleService()
        service = PublicShareLinkService(links, handles)  # type: ignore[arg-type]

        key = await service.get_existing_key(
            resource_type="showcase_page", resource_id=resource_id
        )

        assert key == "already-there"
        assert handles.ensure_calls == []
