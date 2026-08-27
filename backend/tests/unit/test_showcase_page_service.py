"""Unit tests for ShowcasePageService — fake repositories/storage, no
database. Wires the REAL TargetRoleService/CareerProfileService/
ResumeExportService against fake in-memory repositories (same pattern
tests/unit/test_resume_export_service.py already established for
ResumeExportService itself), since ShowcasePageService composes those
services directly rather than depending on their repositories.
"""

from __future__ import annotations

import uuid
from dataclasses import replace
from datetime import UTC, date, datetime
from typing import Any

import pytest

from app.application.career_profile.career_profile_service import CareerProfileService
from app.application.career_profile.resume_export_service import ResumeExportService
from app.application.career_profile.target_role_service import TargetRoleService
from app.application.showcase_page.showcase_page_service import (
    MAX_IMAGE_SIZE_BYTES,
    ShowcasePageService,
)
from app.core.exceptions import NotFoundError, ValidationError
from app.domain.career_profile.entities import CareerProfile, Experience, TargetRole
from app.domain.identity.entities import User
from app.domain.showcase_page.entities import ShowcaseBlock, ShowcaseColumn, ShowcasePage

pytestmark = pytest.mark.unit


class FakeCareerProfileRepository:
    def __init__(self) -> None:
        self.profiles: dict[uuid.UUID, CareerProfile] = {}

    async def create(self, profile: CareerProfile) -> CareerProfile:
        self.profiles[profile.id] = profile
        return replace(profile)

    async def get_by_user_id(
        self, tenant_id: uuid.UUID, user_id: uuid.UUID, target_role_id: uuid.UUID | None = None
    ) -> CareerProfile | None:
        for profile in self.profiles.values():
            if (
                profile.tenant_id == tenant_id
                and profile.user_id == user_id
                and profile.target_role_id == target_role_id
            ):
                return replace(profile)
        return None

    async def get_by_id(self, tenant_id: uuid.UUID, profile_id: uuid.UUID) -> CareerProfile | None:
        profile = self.profiles.get(profile_id)
        return replace(profile) if profile and profile.tenant_id == tenant_id else None

    async def update(self, profile: CareerProfile) -> CareerProfile:
        self.profiles[profile.id] = replace(profile)
        return replace(profile)


class FakeCareerProfileVersionRepository:
    async def create(self, version: Any) -> Any:
        return version


class FakeEmptyChildRepository:
    """Stands in for Experience/Education/Certification/CareerHighlight/
    KeyAchievement/CareerGoal/PeerEndorsement — see the identical fake in
    test_resume_export_service.py for the full rationale."""

    async def list_for_profile(
        self, tenant_id: uuid.UUID, career_profile_id: uuid.UUID
    ) -> list[Any]:
        return []

    async def list_for_user(self, tenant_id: uuid.UUID, user_id: uuid.UUID) -> list[Any]:
        return []


class FakeExperienceRepository:
    def __init__(self) -> None:
        self.by_profile: dict[uuid.UUID, list[Experience]] = {}

    async def list_for_profile(
        self, tenant_id: uuid.UUID, career_profile_id: uuid.UUID
    ) -> list[Experience]:
        return list(self.by_profile.get(career_profile_id, []))

    async def list_for_user(self, tenant_id: uuid.UUID, user_id: uuid.UUID) -> list[Any]:
        return []


class FakeTargetRoleRepository:
    def __init__(self) -> None:
        self.roles: dict[uuid.UUID, TargetRole] = {}

    async def get_by_id(self, tenant_id: uuid.UUID, target_role_id: uuid.UUID) -> TargetRole | None:
        role = self.roles.get(target_role_id)
        return replace(role) if role and role.tenant_id == tenant_id else None


class FakeUserRepository:
    def __init__(self) -> None:
        self.users: dict[uuid.UUID, User] = {}

    async def get_by_id(self, tenant_id: uuid.UUID, user_id: uuid.UUID) -> User | None:
        user = self.users.get(user_id)
        return replace(user) if user and user.tenant_id == tenant_id else None


class FakePublicObjectStorage:
    def __init__(self) -> None:
        self.uploaded: dict[str, bytes] = {}

    async def upload(self, *, key: str, content: bytes, content_type: str) -> str:
        self.uploaded[key] = content
        return f"https://example.test/{key}"

    async def delete(self, *, key: str) -> None:
        self.uploaded.pop(key, None)


class FakeShowcasePageRepository:
    def __init__(self) -> None:
        self.pages: dict[uuid.UUID, ShowcasePage] = {}

    async def create(self, page: ShowcasePage) -> ShowcasePage:
        self.pages[page.id] = page
        return replace(page)

    async def get_by_target_role(
        self, tenant_id: uuid.UUID, target_role_id: uuid.UUID
    ) -> ShowcasePage | None:
        for page in self.pages.values():
            if page.tenant_id == tenant_id and page.target_role_id == target_role_id:
                return replace(page)
        return None

    async def get_by_id(self, tenant_id: uuid.UUID, page_id: uuid.UUID) -> ShowcasePage | None:
        page = self.pages.get(page_id)
        return replace(page) if page and page.tenant_id == tenant_id else None

    async def update(self, page: ShowcasePage) -> ShowcasePage:
        self.pages[page.id] = replace(page)
        return replace(page)


def _make_target_role(*, tenant_id: uuid.UUID, user_id: uuid.UUID) -> TargetRole:
    return TargetRole(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        user_id=user_id,
        role_name="Senior Engineer",
        tag="SE",
        created_at=datetime.now(UTC),
    )


def _make_profile(
    *,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
    target_role_id: uuid.UUID | None,
    headline: str | None = "Senior Engineer",
    summary: str | None = "Builds reliable systems.",
    photo_url: str | None = None,
) -> CareerProfile:
    now = datetime.now(UTC)
    return CareerProfile(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        user_id=user_id,
        current_version=1,
        headline=headline,
        summary=summary,
        career_readiness_score=None,
        photo_url=photo_url,
        core_competencies=[],
        created_at=now,
        updated_at=now,
        target_role_id=target_role_id,
    )


def _make_user(*, tenant_id: uuid.UUID, user_id: uuid.UUID | None = None) -> User:
    now = datetime.now(UTC)
    return User(
        id=user_id or uuid.uuid4(),
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
    )


class _Fixture:
    def __init__(self) -> None:
        self.tenant_id = uuid.uuid4()
        self.user_id = uuid.uuid4()
        self.pages = FakeShowcasePageRepository()
        self.target_role_repo = FakeTargetRoleRepository()
        self.career_profile_repo = FakeCareerProfileRepository()
        self.experience_repo = FakeExperienceRepository()
        self.user_repo = FakeUserRepository()
        self.storage = FakePublicObjectStorage()

        self.target_roles = TargetRoleService(self.target_role_repo)  # type: ignore[arg-type]
        self.career_profiles = CareerProfileService(
            self.career_profile_repo,
            FakeCareerProfileVersionRepository(),  # type: ignore[arg-type]
        )
        self.resume_export = ResumeExportService(
            profiles=self.career_profile_repo,
            experiences=self.experience_repo,
            educations=FakeEmptyChildRepository(),
            certifications=FakeEmptyChildRepository(),
            career_highlights=FakeEmptyChildRepository(),
            key_achievements=FakeEmptyChildRepository(),
            career_goals=FakeEmptyChildRepository(),
            peer_endorsements=FakeEmptyChildRepository(),
            target_roles=self.target_role_repo,
            users=self.user_repo,
            storage=self.storage,  # type: ignore[arg-type]
        )
        self.service = ShowcasePageService(
            self.pages,
            self.target_roles,
            self.career_profiles,
            self.resume_export,
            self.storage,
            self.user_repo,  # type: ignore[arg-type]
        )

    def register_role_with_profile(self) -> TargetRole:
        role = _make_target_role(tenant_id=self.tenant_id, user_id=self.user_id)
        self.target_role_repo.roles[role.id] = role
        self.user_repo.users[self.user_id] = _make_user(
            tenant_id=self.tenant_id, user_id=self.user_id
        )
        profile = _make_profile(
            tenant_id=self.tenant_id, user_id=self.user_id, target_role_id=role.id
        )
        self.career_profile_repo.profiles[profile.id] = profile
        return role

    async def update(
        self,
        *,
        target_role_id: uuid.UUID,
        blocks: list[ShowcaseBlock],
        name: str | None = None,
        headline: str | None = None,
        summary: str | None = None,
    ) -> ShowcasePage:
        return await self.service.update(
            tenant_id=self.tenant_id,
            user_id=self.user_id,
            target_role_id=target_role_id,
            blocks=blocks,
            name=name,
            headline=headline,
            summary=summary,
        )


class TestGetOrCreate:
    async def test_raises_not_found_for_an_unowned_target_role(self) -> None:
        fx = _Fixture()

        with pytest.raises(NotFoundError):
            await fx.service.get_or_create(
                tenant_id=fx.tenant_id, user_id=fx.user_id, target_role_id=uuid.uuid4()
            )

    async def test_seeds_an_about_block_from_headline_and_summary(self) -> None:
        fx = _Fixture()
        role = fx.register_role_with_profile()

        page = await fx.service.get_or_create(
            tenant_id=fx.tenant_id, user_id=fx.user_id, target_role_id=role.id
        )

        assert page.is_public is False
        about_block = next(b for b in page.blocks if b.columns[0].label == "About")
        assert len(about_block.columns) == 1
        about = about_block.columns[0]
        assert "Senior Engineer" in (about.html or "")
        assert "Builds reliable systems." in (about.html or "")

    async def test_seeds_name_headline_and_summary_top_bar_fields(self) -> None:
        fx = _Fixture()
        role = fx.register_role_with_profile()

        page = await fx.service.get_or_create(
            tenant_id=fx.tenant_id, user_id=fx.user_id, target_role_id=role.id
        )

        assert page.name == "Jordan Rivera"
        assert page.headline == "Senior Engineer"
        assert page.summary == "Builds reliable systems."

    async def test_seeds_an_experience_block_when_experiences_exist(self) -> None:
        fx = _Fixture()
        role = fx.register_role_with_profile()
        profile = next(iter(fx.career_profile_repo.profiles.values()))
        exp = Experience(
            id=uuid.uuid4(),
            tenant_id=fx.tenant_id,
            career_profile_id=profile.id,
            title="Staff Engineer",
            company="Acme Corp",
            location="Remote",
            start_date=date(2020, 1, 1),
            end_date=None,
            description="<p>Shipped things.</p>",
            display_order=1,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        fx.experience_repo.by_profile[profile.id] = [exp]

        page = await fx.service.get_or_create(
            tenant_id=fx.tenant_id, user_id=fx.user_id, target_role_id=role.id
        )

        experience_block = next(b for b in page.blocks if b.columns[0].label == "Experience")
        experience_html = experience_block.columns[0].html or ""
        assert "Staff Engineer" in experience_html
        assert "Acme Corp" in experience_html
        assert "Shipped things." in experience_html

    async def test_second_call_reuses_the_existing_page_without_reseeding(self) -> None:
        fx = _Fixture()
        role = fx.register_role_with_profile()

        first = await fx.service.get_or_create(
            tenant_id=fx.tenant_id, user_id=fx.user_id, target_role_id=role.id
        )
        # Mutate the seeded page directly in storage to prove a second
        # get_or_create returns THIS row, not a freshly re-seeded one.
        fx.pages.pages[first.id].blocks = []
        second = await fx.service.get_or_create(
            tenant_id=fx.tenant_id, user_id=fx.user_id, target_role_id=role.id
        )

        assert second.id == first.id
        assert second.blocks == []


class TestUpdate:
    async def test_sanitizes_rich_text_block_html(self) -> None:
        fx = _Fixture()
        role = fx.register_role_with_profile()
        await fx.service.get_or_create(
            tenant_id=fx.tenant_id, user_id=fx.user_id, target_role_id=role.id
        )
        column = ShowcaseColumn(
            id=uuid.uuid4(),
            type="rich_text",
            label="Custom",
            html="<p>Hello</p><script>alert(1)</script>",
        )
        block = ShowcaseBlock(id=uuid.uuid4(), columns=[column])

        updated = await fx.update(target_role_id=role.id, blocks=[block])

        assert updated.blocks[0].columns[0].html == "<p>Hello</p>alert(1)"

    async def test_leaves_non_rich_text_blocks_untouched(self) -> None:
        fx = _Fixture()
        role = fx.register_role_with_profile()
        await fx.service.get_or_create(
            tenant_id=fx.tenant_id, user_id=fx.user_id, target_role_id=role.id
        )
        column = ShowcaseColumn(
            id=uuid.uuid4(),
            type="external_link",
            label="My site",
            external_url="https://example.com",
        )
        block = ShowcaseBlock(id=uuid.uuid4(), columns=[column])

        updated = await fx.update(target_role_id=role.id, blocks=[block])

        assert updated.blocks[0].columns[0].external_url == "https://example.com"

    async def test_replaces_the_whole_block_list(self) -> None:
        fx = _Fixture()
        role = fx.register_role_with_profile()
        seeded = await fx.service.get_or_create(
            tenant_id=fx.tenant_id, user_id=fx.user_id, target_role_id=role.id
        )
        assert len(seeded.blocks) > 0

        updated = await fx.update(target_role_id=role.id, blocks=[])

        assert updated.blocks == []

    async def test_updates_name_headline_and_summary_independently_of_the_real_profile(
        self,
    ) -> None:
        fx = _Fixture()
        role = fx.register_role_with_profile()
        await fx.service.get_or_create(
            tenant_id=fx.tenant_id, user_id=fx.user_id, target_role_id=role.id
        )

        updated = await fx.update(
            target_role_id=role.id,
            blocks=[],
            name="Custom Name",
            headline="<p>Custom headline</p>",
            summary="<p>Custom summary</p>",
        )

        assert updated.name == "Custom Name"
        assert updated.headline == "<p>Custom headline</p>"
        assert updated.summary == "<p>Custom summary</p>"
        # The real CareerProfile is untouched — this is the page's own
        # independent copy (direct 2026-08-24 decision), not a sync.
        real_profile = next(iter(fx.career_profile_repo.profiles.values()))
        assert real_profile.headline == "Senior Engineer"
        assert real_profile.summary == "Builds reliable systems."

    async def test_sanitizes_headline_and_summary_on_update(self) -> None:
        fx = _Fixture()
        role = fx.register_role_with_profile()
        await fx.service.get_or_create(
            tenant_id=fx.tenant_id, user_id=fx.user_id, target_role_id=role.id
        )

        updated = await fx.update(
            target_role_id=role.id,
            blocks=[],
            headline="<p>Hi</p><script>alert(1)</script>",
            summary="<p>Bye</p><script>alert(2)</script>",
        )

        assert updated.headline == "<p>Hi</p>alert(1)"
        assert updated.summary == "<p>Bye</p>alert(2)"

    async def test_name_is_trimmed_and_blank_becomes_none(self) -> None:
        fx = _Fixture()
        role = fx.register_role_with_profile()
        await fx.service.get_or_create(
            tenant_id=fx.tenant_id, user_id=fx.user_id, target_role_id=role.id
        )

        updated = await fx.update(target_role_id=role.id, blocks=[], name="  Padded Name  ")
        assert updated.name == "Padded Name"

        cleared = await fx.update(target_role_id=role.id, blocks=[], name="   ")
        assert cleared.name is None


class TestSetPublic:
    async def test_flips_the_flag(self) -> None:
        fx = _Fixture()
        role = fx.register_role_with_profile()
        await fx.service.get_or_create(
            tenant_id=fx.tenant_id, user_id=fx.user_id, target_role_id=role.id
        )

        page = await fx.service.set_public(
            tenant_id=fx.tenant_id, user_id=fx.user_id, target_role_id=role.id, is_public=True
        )

        assert page.is_public is True

        page = await fx.service.set_public(
            tenant_id=fx.tenant_id, user_id=fx.user_id, target_role_id=role.id, is_public=False
        )

        assert page.is_public is False


class TestGetPhotoUrl:
    async def test_returns_the_target_role_profiles_own_photo(self) -> None:
        fx = _Fixture()
        role = fx.register_role_with_profile()
        target_profile = next(iter(fx.career_profile_repo.profiles.values()))
        target_profile.photo_url = "https://example.test/target-role-photo.jpg"
        # Master's own profile has a DIFFERENT photo — the target role's
        # own must win, no fallback needed here.
        master_profile = _make_profile(
            tenant_id=fx.tenant_id, user_id=fx.user_id, target_role_id=None
        )
        master_profile.photo_url = "https://example.test/master-photo.jpg"
        fx.career_profile_repo.profiles[master_profile.id] = master_profile

        url = await fx.service.get_photo_url(
            tenant_id=fx.tenant_id, user_id=fx.user_id, target_role_id=role.id
        )

        assert url == "https://example.test/target-role-photo.jpg"

    async def test_falls_back_to_masters_photo_when_target_role_has_none(self) -> None:
        fx = _Fixture()
        role = fx.register_role_with_profile()
        # register_role_with_profile's own target-role CareerProfile has
        # photo_url=None (see _make_profile's default) — no separate
        # override needed to exercise the fallback here.
        master_profile = _make_profile(
            tenant_id=fx.tenant_id, user_id=fx.user_id, target_role_id=None
        )
        master_profile.photo_url = "https://example.test/master-photo.jpg"
        fx.career_profile_repo.profiles[master_profile.id] = master_profile

        url = await fx.service.get_photo_url(
            tenant_id=fx.tenant_id, user_id=fx.user_id, target_role_id=role.id
        )

        assert url == "https://example.test/master-photo.jpg"

    async def test_returns_none_when_neither_profile_has_a_photo(self) -> None:
        fx = _Fixture()
        role = fx.register_role_with_profile()

        url = await fx.service.get_photo_url(
            tenant_id=fx.tenant_id, user_id=fx.user_id, target_role_id=role.id
        )

        assert url is None


def _image_block() -> ShowcaseBlock:
    return ShowcaseBlock(
        id=uuid.uuid4(),
        columns=[ShowcaseColumn(id=uuid.uuid4(), type="image", label="Photo")],
    )


class TestUploadImage:
    async def test_sets_the_column_image_url(self) -> None:
        fx = _Fixture()
        role = fx.register_role_with_profile()
        page = await fx.update(target_role_id=role.id, blocks=[_image_block()])
        column_id = page.blocks[0].columns[0].id

        updated = await fx.service.upload_image(
            tenant_id=fx.tenant_id,
            user_id=fx.user_id,
            target_role_id=role.id,
            column_id=column_id,
            content=b"fake-bytes",
            content_type="image/png",
        )

        image_url = updated.blocks[0].columns[0].image_url
        assert image_url is not None
        assert image_url.startswith("https://example.test/showcase-pages/")

    async def test_finds_the_column_even_when_its_row_has_multiple_columns(self) -> None:
        fx = _Fixture()
        role = fx.register_role_with_profile()
        text_column = ShowcaseColumn(id=uuid.uuid4(), type="rich_text", label="Text", html="<p>Hi</p>")
        image_column = ShowcaseColumn(id=uuid.uuid4(), type="image", label="Photo")
        row = ShowcaseBlock(id=uuid.uuid4(), columns=[text_column, image_column])
        await fx.update(target_role_id=role.id, blocks=[row])

        updated = await fx.service.upload_image(
            tenant_id=fx.tenant_id,
            user_id=fx.user_id,
            target_role_id=role.id,
            column_id=image_column.id,
            content=b"fake-bytes",
            content_type="image/png",
        )

        assert len(updated.blocks) == 1
        assert len(updated.blocks[0].columns) == 2
        assert updated.blocks[0].columns[0].html == "<p>Hi</p>"  # untouched
        assert updated.blocks[0].columns[1].image_url is not None

    async def test_raises_not_found_for_an_unknown_column(self) -> None:
        fx = _Fixture()
        role = fx.register_role_with_profile()
        await fx.service.get_or_create(
            tenant_id=fx.tenant_id, user_id=fx.user_id, target_role_id=role.id
        )

        with pytest.raises(NotFoundError):
            await fx.service.upload_image(
                tenant_id=fx.tenant_id,
                user_id=fx.user_id,
                target_role_id=role.id,
                column_id=uuid.uuid4(),
                content=b"data",
                content_type="image/png",
            )

    async def test_rejects_unsupported_content_type(self) -> None:
        fx = _Fixture()
        role = fx.register_role_with_profile()
        page = await fx.update(target_role_id=role.id, blocks=[_image_block()])

        with pytest.raises(ValidationError):
            await fx.service.upload_image(
                tenant_id=fx.tenant_id,
                user_id=fx.user_id,
                target_role_id=role.id,
                column_id=page.blocks[0].columns[0].id,
                content=b"data",
                content_type="application/pdf",
            )

    async def test_rejects_oversized_image(self) -> None:
        fx = _Fixture()
        role = fx.register_role_with_profile()
        page = await fx.update(target_role_id=role.id, blocks=[_image_block()])

        with pytest.raises(ValidationError):
            await fx.service.upload_image(
                tenant_id=fx.tenant_id,
                user_id=fx.user_id,
                target_role_id=role.id,
                column_id=page.blocks[0].columns[0].id,
                content=b"x" * (MAX_IMAGE_SIZE_BYTES + 1),
                content_type="image/png",
            )


class TestUploadBackgroundImage:
    async def test_sets_the_pages_background_image_url(self) -> None:
        fx = _Fixture()
        role = fx.register_role_with_profile()

        updated = await fx.service.upload_background_image(
            tenant_id=fx.tenant_id,
            user_id=fx.user_id,
            target_role_id=role.id,
            content=b"fake-bytes",
            content_type="image/png",
        )

        assert updated.background_image_url is not None
        assert updated.background_image_url.startswith(
            "https://example.test/showcase-pages/"
        )

    async def test_rejects_unsupported_content_type(self) -> None:
        fx = _Fixture()
        role = fx.register_role_with_profile()

        with pytest.raises(ValidationError):
            await fx.service.upload_background_image(
                tenant_id=fx.tenant_id,
                user_id=fx.user_id,
                target_role_id=role.id,
                content=b"data",
                content_type="application/pdf",
            )

    async def test_rejects_oversized_image(self) -> None:
        fx = _Fixture()
        role = fx.register_role_with_profile()

        with pytest.raises(ValidationError):
            await fx.service.upload_background_image(
                tenant_id=fx.tenant_id,
                user_id=fx.user_id,
                target_role_id=role.id,
                content=b"x" * (MAX_IMAGE_SIZE_BYTES + 1),
                content_type="image/png",
            )


class TestRemoveBackgroundImage:
    async def test_clears_the_field_and_deletes_from_storage(self) -> None:
        fx = _Fixture()
        role = fx.register_role_with_profile()
        await fx.service.upload_background_image(
            tenant_id=fx.tenant_id,
            user_id=fx.user_id,
            target_role_id=role.id,
            content=b"fake-bytes",
            content_type="image/png",
        )
        assert len(fx.storage.uploaded) == 1

        updated = await fx.service.remove_background_image(
            tenant_id=fx.tenant_id, user_id=fx.user_id, target_role_id=role.id
        )

        assert updated.background_image_url is None
        assert fx.storage.uploaded == {}

    async def test_is_a_no_op_when_no_background_image_is_set(self) -> None:
        fx = _Fixture()
        role = fx.register_role_with_profile()

        updated = await fx.service.remove_background_image(
            tenant_id=fx.tenant_id, user_id=fx.user_id, target_role_id=role.id
        )

        assert updated.background_image_url is None


class TestMultiColumnRows:
    async def test_a_row_can_hold_several_columns_of_different_types(self) -> None:
        fx = _Fixture()
        role = fx.register_role_with_profile()
        row = ShowcaseBlock(
            id=uuid.uuid4(),
            columns=[
                ShowcaseColumn(id=uuid.uuid4(), type="image", label="Photo"),
                ShowcaseColumn(id=uuid.uuid4(), type="rich_text", label="Bio", html="<p>Hi</p>"),
                ShowcaseColumn(
                    id=uuid.uuid4(),
                    type="video_embed",
                    label="Demo",
                    video_embed_url="https://www.youtube.com/embed/xyz",
                ),
            ],
        )

        updated = await fx.update(target_role_id=role.id, blocks=[row])

        assert len(updated.blocks) == 1
        assert [c.type for c in updated.blocks[0].columns] == ["image", "rich_text", "video_embed"]

    async def test_an_existing_single_column_row_can_be_extended_to_multiple_columns(self) -> None:
        fx = _Fixture()
        role = fx.register_role_with_profile()
        original_column = ShowcaseColumn(
            id=uuid.uuid4(), type="rich_text", label="Text", html="<p>Original</p>"
        )
        row = ShowcaseBlock(id=uuid.uuid4(), columns=[original_column])
        page = await fx.update(target_role_id=role.id, blocks=[row])
        assert len(page.blocks[0].columns) == 1

        # Same row id, now with a second column appended — mirrors what
        # the frontend's "+ Add column" control sends: the whole blocks
        # array, replaced atomically (same convention every other
        # structural change to this page already uses).
        new_column = ShowcaseColumn(id=uuid.uuid4(), type="image", label="Photo")
        extended_row = ShowcaseBlock(id=row.id, columns=[original_column, new_column])

        updated = await fx.update(target_role_id=role.id, blocks=[extended_row])

        assert len(updated.blocks) == 1
        assert updated.blocks[0].id == row.id
        assert len(updated.blocks[0].columns) == 2
        assert updated.blocks[0].columns[0].html == "<p>Original</p>"
        assert updated.blocks[0].columns[1].type == "image"
