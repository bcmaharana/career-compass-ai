"""Read/write the generic platform_settings key/value store.

Permission gating (platform.settings.view/edit) happens at the API
layer (require_platform_permission) — this service has no opinion on
who's allowed to call it.
"""

from __future__ import annotations

from uuid import UUID

from app.domain.platform_admin.entities import PlatformSetting
from app.domain.platform_admin.repositories import PlatformSettingsRepository


class PlatformSettingsService:
    def __init__(self, settings: PlatformSettingsRepository) -> None:
        self._settings = settings

    async def list_all(self) -> list[PlatformSetting]:
        return await self._settings.list_all()

    async def get(self, key: str) -> str | None:
        setting = await self._settings.get(key)
        return setting.value if setting else None

    async def set(
        self, *, key: str, value: str, description: str, updated_by_user_id: UUID
    ) -> PlatformSetting:
        # Preserve the existing description on a value-only edit unless
        # the caller explicitly supplies a new one — the admin UI always
        # sends both, but this keeps the service usable from a future
        # value-only caller without silently blanking the description.
        existing = await self._settings.get(key)
        final_description = description or (existing.description if existing else "")
        return await self._settings.upsert(
            key=key,
            value=value,
            description=final_description,
            updated_by_user_id=updated_by_user_id,
        )
