"""Orchestrates the "make this public" toggle across the two resource
types that can be shared (Showcase Pages, Interview Prep Topics) so the
API router stays thin despite each toggle needing to touch two services
— the owning entity's own service (to flip is_public) and
PublicShareLinkService (to ensure a reusable share key exists once
public). Same fan-out-from-one-orchestrator reasoning as
ClearCareerProfileService, just for a toggle instead of a delete.

Turning OFF never touches public_share_links at all — the link row is
deliberately never deleted (see PublicShareLink's own docstring), so a
later re-toggle-on reuses the exact same key/URL rather than minting a
new one.
"""

from __future__ import annotations

from uuid import UUID

from app.application.interview_prep.interview_topic_service import InterviewTopicService
from app.application.showcase_page.public_share_link_service import PublicShareLinkService
from app.application.showcase_page.showcase_page_service import ShowcasePageService
from app.domain.interview_prep.entities import InterviewTopic
from app.domain.showcase_page.entities import ShowcasePage


class PublicSharingService:
    def __init__(
        self,
        showcase_pages: ShowcasePageService,
        interview_topics: InterviewTopicService,
        share_links: PublicShareLinkService,
    ) -> None:
        self._showcase_pages = showcase_pages
        self._interview_topics = interview_topics
        self._share_links = share_links

    async def set_showcase_page_public(
        self, *, tenant_id: UUID, user_id: UUID, target_role_id: UUID, is_public: bool
    ) -> tuple[ShowcasePage, str | None]:
        page = await self._showcase_pages.set_public(
            tenant_id=tenant_id, user_id=user_id, target_role_id=target_role_id, is_public=is_public
        )
        share_key = None
        if is_public:
            share_key = await self._share_links.get_or_create_key(
                tenant_id=tenant_id,
                user_id=user_id,
                resource_type="showcase_page",
                resource_id=page.id,
            )
        return page, share_key

    async def set_interview_topic_public(
        self, *, tenant_id: UUID, user_id: UUID, topic_id: UUID, is_public: bool
    ) -> tuple[InterviewTopic, str | None]:
        topic = await self._interview_topics.set_public(
            tenant_id=tenant_id, user_id=user_id, topic_id=topic_id, is_public=is_public
        )
        share_key = None
        if is_public:
            share_key = await self._share_links.get_or_create_key(
                tenant_id=tenant_id,
                user_id=user_id,
                resource_type="interview_topic",
                resource_id=topic.id,
            )
        return topic, share_key
