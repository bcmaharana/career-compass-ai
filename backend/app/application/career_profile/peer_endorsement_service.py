"""Peer endorsement application service.

Self-managed for now (the profile owner enters a testimonial they
received) — see PeerEndorsementModel's docstring for the scope decision.
Follows the same ownership-check pattern as ExperienceService.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from uuid import UUID

from app.application.career_profile.career_profile_service import CareerProfileService
from app.core.exceptions import NotFoundError
from app.domain.career_profile.entities import PeerEndorsement
from app.domain.career_profile.repositories import Direction, PeerEndorsementRepository


class PeerEndorsementService:
    def __init__(
        self,
        endorsements: PeerEndorsementRepository,
        career_profiles: CareerProfileService,
    ) -> None:
        self._endorsements = endorsements
        self._career_profiles = career_profiles

    async def _get_owned_or_raise(
        self, *, tenant_id: UUID, user_id: UUID, endorsement_id: UUID
    ) -> PeerEndorsement:
        endorsement = await self._endorsements.get_by_id(tenant_id, endorsement_id)
        profile = await self._career_profiles.get_or_create(tenant_id=tenant_id, user_id=user_id)
        if endorsement is None or endorsement.career_profile_id != profile.id:
            raise NotFoundError("Peer endorsement not found.", code="PEER_ENDORSEMENT_NOT_FOUND")
        return endorsement

    async def add(
        self,
        *,
        tenant_id: UUID,
        user_id: UUID,
        recommender_name: str,
        recommender_title: str | None,
        relationship: str | None,
        content: str,
    ) -> PeerEndorsement:
        profile = await self._career_profiles.get_or_create(tenant_id=tenant_id, user_id=user_id)
        now = datetime.now(UTC)
        return await self._endorsements.create(
            PeerEndorsement(
                id=uuid.uuid4(),
                tenant_id=tenant_id,
                career_profile_id=profile.id,
                recommender_name=recommender_name,
                recommender_title=recommender_title,
                relationship=relationship,
                content=content,
                display_order=0,  # overwritten by the repository on create
                created_at=now,
                updated_at=now,
            )
        )

    async def list_for_current_user(
        self, *, tenant_id: UUID, user_id: UUID
    ) -> list[PeerEndorsement]:
        profile = await self._career_profiles.get_or_create(tenant_id=tenant_id, user_id=user_id)
        return await self._endorsements.list_for_profile(tenant_id, profile.id)

    async def update(
        self,
        *,
        tenant_id: UUID,
        user_id: UUID,
        endorsement_id: UUID,
        recommender_name: str,
        recommender_title: str | None,
        relationship: str | None,
        content: str,
    ) -> PeerEndorsement:
        endorsement = await self._get_owned_or_raise(
            tenant_id=tenant_id, user_id=user_id, endorsement_id=endorsement_id
        )
        endorsement.recommender_name = recommender_name
        endorsement.recommender_title = recommender_title
        endorsement.relationship = relationship
        endorsement.content = content
        return await self._endorsements.update(endorsement)

    async def delete(self, *, tenant_id: UUID, user_id: UUID, endorsement_id: UUID) -> None:
        await self._get_owned_or_raise(
            tenant_id=tenant_id, user_id=user_id, endorsement_id=endorsement_id
        )
        await self._endorsements.soft_delete(tenant_id, endorsement_id)

    async def move(
        self, *, tenant_id: UUID, user_id: UUID, endorsement_id: UUID, direction: Direction
    ) -> None:
        await self._get_owned_or_raise(
            tenant_id=tenant_id, user_id=user_id, endorsement_id=endorsement_id
        )
        await self._endorsements.move(tenant_id, endorsement_id, direction)
