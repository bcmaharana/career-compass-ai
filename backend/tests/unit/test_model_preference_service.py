"""Unit tests for ModelPreferenceService — listing selectable models and
setting/clearing a user's own model override."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest

from app.ai_platform.models.registry import ModelVersion
from app.application.ai_platform.model_preference_service import ModelPreferenceService
from app.core.exceptions import NotFoundError, ValidationError
from app.domain.identity.entities import User


def _model(*, model_name: str, is_default: bool = False, status: str = "active") -> ModelVersion:
    return ModelVersion(
        id=str(uuid.uuid4()),
        provider="anthropic",
        model_name=model_name,
        version="1",
        status=status,
        cost_per_1k_tokens=0.006,
        is_default=is_default,
    )


def _user(
    *, tenant_id: uuid.UUID, user_id: uuid.UUID, preferred_model_version_id: uuid.UUID | None = None
) -> User:
    now = datetime.now(UTC)
    return User(
        id=user_id,
        tenant_id=tenant_id,
        org_id=None,
        email="user@example.com",
        salutation=None,
        first_name="Ada",
        last_name="Lovelace",
        hashed_password="hashed",
        status="active",
        mfa_enabled=False,
        created_at=now,
        updated_at=now,
        preferred_model_version_id=preferred_model_version_id,
    )


class FakeModelCatalog:
    """Fakes must return copies on fetch — a fake returning the same
    ModelVersion instance every call would mask a real bug the same way
    FakeCareerProfileRepository's docstring warns about; ModelVersion is
    frozen, so mutation isn't possible, but the list itself is copied
    per call for the same reason."""

    def __init__(self, models: list[ModelVersion], *, users: FakeUserRepository) -> None:
        self._models = models
        # Reads the preference straight off the same fake user store the
        # service writes to — mirrors production, where
        # SqlAlchemyModelRegistry and the user's own repository query the
        # same `users` table, not two independent stores.
        self._users = users

    async def list_active(self) -> list[ModelVersion]:
        return [m for m in self._models if m.status == "active"]

    async def get_by_id(self, model_version_id: str) -> ModelVersion | None:
        return next((m for m in self._models if m.id == model_version_id), None)

    async def get_active_model(
        self, *, tenant_id: str | None = None, user_id: str | None = None
    ) -> ModelVersion:
        preferred_id = self._users.preferred_model_version_id(user_id) if user_id else None
        if preferred_id is not None:
            preferred = await self.get_by_id(preferred_id)
            if preferred is not None and preferred.status == "active":
                return preferred
        default = next((m for m in self._models if m.is_default and m.status == "active"), None)
        if default is None:
            raise NotFoundError("No active model configured", code="MODEL_NOT_CONFIGURED")
        return default


class FakeUserRepository:
    def __init__(self, users: list[User]) -> None:
        self._users = {(u.tenant_id, u.id): u for u in users}

    async def create(self, user: User) -> User:
        self._users[(user.tenant_id, user.id)] = user
        return user

    async def get_by_id(self, tenant_id: uuid.UUID, user_id: uuid.UUID) -> User | None:
        return self._users.get((tenant_id, user_id))

    async def get_by_email(self, tenant_id: uuid.UUID, email: str) -> User | None:
        return next(
            (u for u in self._users.values() if u.tenant_id == tenant_id and u.email == email),
            None,
        )

    async def update(self, user: User) -> User:
        self._users[(user.tenant_id, user.id)] = user
        return user

    def preferred_model_version_id(self, user_id: str) -> str | None:
        for (_, uid), user in self._users.items():
            if str(uid) == user_id:
                return (
                    str(user.preferred_model_version_id)
                    if user.preferred_model_version_id
                    else None
                )
        return None


@pytest.mark.unit
class TestGetSelection:
    async def test_falls_back_to_the_default_model_with_no_preference_set(self) -> None:
        tenant_id, user_id = uuid.uuid4(), uuid.uuid4()
        sonnet = _model(model_name="claude-sonnet-5", is_default=True)
        opus = _model(model_name="claude-opus-5")
        users = FakeUserRepository([_user(tenant_id=tenant_id, user_id=user_id)])
        models = FakeModelCatalog([sonnet, opus], users=users)
        service = ModelPreferenceService(models, users)

        selection = await service.get_selection(tenant_id, user_id)

        assert selection.selected_id == sonnet.id
        assert {m.id for m in selection.available} == {sonnet.id, opus.id}


@pytest.mark.unit
class TestSetPreference:
    async def test_setting_a_valid_active_model_persists_and_is_reflected_in_selection(
        self,
    ) -> None:
        tenant_id, user_id = uuid.uuid4(), uuid.uuid4()
        sonnet = _model(model_name="claude-sonnet-5", is_default=True)
        opus = _model(model_name="claude-opus-5")
        users = FakeUserRepository([_user(tenant_id=tenant_id, user_id=user_id)])
        models = FakeModelCatalog([sonnet, opus], users=users)
        service = ModelPreferenceService(models, users)

        selection = await service.set_preference(tenant_id, user_id, uuid.UUID(opus.id))

        assert selection.selected_id == opus.id
        stored = await users.get_by_id(tenant_id, user_id)
        assert stored is not None
        assert str(stored.preferred_model_version_id) == opus.id

    async def test_clearing_the_preference_reverts_to_the_platform_default(self) -> None:
        tenant_id, user_id = uuid.uuid4(), uuid.uuid4()
        sonnet = _model(model_name="claude-sonnet-5", is_default=True)
        opus = _model(model_name="claude-opus-5")
        users = FakeUserRepository(
            [
                _user(
                    tenant_id=tenant_id,
                    user_id=user_id,
                    preferred_model_version_id=uuid.UUID(opus.id),
                )
            ]
        )
        models = FakeModelCatalog([sonnet, opus], users=users)
        service = ModelPreferenceService(models, users)

        selection = await service.set_preference(tenant_id, user_id, None)

        assert selection.selected_id == sonnet.id
        stored = await users.get_by_id(tenant_id, user_id)
        assert stored is not None
        assert stored.preferred_model_version_id is None

    async def test_rejects_a_model_that_is_not_active(self) -> None:
        tenant_id, user_id = uuid.uuid4(), uuid.uuid4()
        sonnet = _model(model_name="claude-sonnet-5", is_default=True)
        sunset = _model(model_name="claude-opus-4-6", status="sunset")
        users = FakeUserRepository([_user(tenant_id=tenant_id, user_id=user_id)])
        models = FakeModelCatalog([sonnet, sunset], users=users)
        service = ModelPreferenceService(models, users)

        with pytest.raises(ValidationError) as exc_info:
            await service.set_preference(tenant_id, user_id, uuid.UUID(sunset.id))

        assert exc_info.value.code == "MODEL_NOT_SELECTABLE"

    async def test_rejects_a_model_id_that_does_not_exist(self) -> None:
        tenant_id, user_id = uuid.uuid4(), uuid.uuid4()
        sonnet = _model(model_name="claude-sonnet-5", is_default=True)
        users = FakeUserRepository([_user(tenant_id=tenant_id, user_id=user_id)])
        models = FakeModelCatalog([sonnet], users=users)
        service = ModelPreferenceService(models, users)

        with pytest.raises(ValidationError):
            await service.set_preference(tenant_id, user_id, uuid.uuid4())

    async def test_raises_not_found_for_an_unknown_user(self) -> None:
        tenant_id, user_id = uuid.uuid4(), uuid.uuid4()
        sonnet = _model(model_name="claude-sonnet-5", is_default=True)
        users = FakeUserRepository([])
        models = FakeModelCatalog([sonnet], users=users)
        service = ModelPreferenceService(models, users)

        with pytest.raises(NotFoundError):
            await service.set_preference(tenant_id, user_id, None)
