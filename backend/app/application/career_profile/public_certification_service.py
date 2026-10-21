"""Read-only public projection for individually shared certificates."""

from __future__ import annotations

from dataclasses import dataclass

from app.domain.career_profile.entities import Certification
from app.domain.career_profile.repositories import CareerProfileRepository, CertificationRepository
from app.domain.identity.repositories import TenantContextBinder, UserRepository
from app.domain.resume_intelligence.storage import PrivateObjectStorageRepository
from app.domain.showcase_page.repositories import PublicShareLinkRepository


@dataclass(frozen=True, slots=True)
class PublicCertificationView:
    certification: Certification
    owner_display_name: str
    certificate_file_url: str | None
    badge_image_url: str | None


class PublicCertificationService:
    def __init__(
        self,
        share_links: PublicShareLinkRepository,
        tenant_context: TenantContextBinder,
        certifications: CertificationRepository,
        career_profiles: CareerProfileRepository,
        users: UserRepository,
        storage: PrivateObjectStorageRepository,
    ) -> None:
        self._share_links = share_links
        self._tenant_context = tenant_context
        self._certifications = certifications
        self._career_profiles = career_profiles
        self._users = users
        self._storage = storage

    async def get_certificate(self, share_key: str) -> PublicCertificationView | None:
        link = await self._share_links.get_by_key(share_key)
        if link is None or link.resource_type != "certification":
            return None

        await self._tenant_context.bind(link.tenant_id)
        certification = await self._certifications.get_by_id(link.tenant_id, link.resource_id)
        if certification is None:
            return None
        profile = await self._career_profiles.get_by_id(
            link.tenant_id, certification.career_profile_id
        )
        if profile is None or profile.user_id != link.user_id:
            return None
        owner = await self._users.get_by_id(link.tenant_id, link.user_id)
        if owner is None:
            return None

        certificate_file_url = None
        if certification.certificate_file_key:
            certificate_file_url = await self._storage.get_presigned_url(
                key=certification.certificate_file_key,
                expires_in_seconds=300,
                disposition="inline",
            )

        badge_image_url = None
        if certification.badge_image_key:
            badge_image_url = await self._storage.get_presigned_url(
                key=certification.badge_image_key,
                expires_in_seconds=300,
                disposition="inline",
            )

        return PublicCertificationView(
            certification=certification,
            owner_display_name=owner.display_name,
            certificate_file_url=certificate_file_url,
            badge_image_url=badge_image_url,
        )
