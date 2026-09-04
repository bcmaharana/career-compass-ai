"""The anonymous read path — the only place in this codebase (besides
login) that resolves a tenant from something other than an already
-authenticated request. No `Depends(get_current_identity)` anywhere
upstream of this service; see app/api/v1/public_sharing/router.py.

Lookup chain, same shape phone login's Personal-account path already
established (app/application/identity/authenticate_user.py's
execute_phone): look up the bare share_key in the RLS-exempt
public_share_links table (no tenant context needed for that one query),
learn tenant_id, bind it via TenantContextBinder, THEN query the real,
RLS-protected resource row in the same session/transaction. A resource
is served only if its *live* is_public flag is still true — the link
row itself is never deleted on toggle-off (see PublicShareLink's own
docstring), so this flag is what actually gates access.

Both methods return None — never a distinguishing error — for every one
of "key never existed", "key points at the wrong resource type", and
"resource exists but is now private". An anonymous caller must not be
able to tell any of these apart from one another.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID

from app.domain.career_profile.repositories import CareerProfileRepository, TargetRoleRepository
from app.domain.identity.repositories import TenantContextBinder, UserRepository
from app.domain.interview_prep.entities import InterviewTopic
from app.domain.interview_prep.repositories import InterviewTopicRepository
from app.application.showcase_page.showcase_page_service import (
    RESUME_DOWNLOAD_URL_TTL_SECONDS,
    resume_download_filename,
)
from app.domain.resume_intelligence.storage import PrivateObjectStorageRepository
from app.domain.showcase_page.entities import ShowcasePage
from app.domain.showcase_page.repositories import PublicShareLinkRepository, ShowcasePageRepository


async def _resolve_photo_url(
    career_profiles: CareerProfileRepository, *, tenant_id: UUID, user_id: UUID, target_role_id: UUID
) -> str | None:
    """Read-only counterpart to ShowcasePageService.get_photo_url — no
    get_or_create side effects here (an anonymous viewer should never be
    the one to lazily create a CareerProfile row; by the time a page is
    public, both the target role's own and Master's rows already exist
    from whatever earlier authenticated flow created them). Same
    Master-fallback rule: a Target Role Profile with no photo of its own
    falls back to Master's."""
    profile = await career_profiles.get_by_user_id(tenant_id, user_id, target_role_id)
    if profile is not None and profile.photo_url:
        return profile.photo_url
    master = await career_profiles.get_by_user_id(tenant_id, user_id, None)
    return master.photo_url if master is not None else None


@dataclass(frozen=True, slots=True)
class PublicShowcasePageView:
    page: ShowcasePage
    owner_display_name: str
    owner_handle: str
    role_name: str
    role_tag: str
    #: share_key for every `article_link` block whose target
    #: InterviewTopic is CURRENTLY public — omitted entirely (not even a
    #: None entry) for a block pointing at a topic that's private, was
    #: deleted, or belongs to a different tenant somehow. The block's own
    #: entity docstring already establishes the rule this enforces: "a
    #: page referencing a topic that's since gone private just renders
    #: as plain text on the public page rather than a broken/private
    #: link" — the raw article_topic_id alone is deliberately never
    #: enough to build a working public link (it isn't a share key, and
    #: exposing it as one would let a viewer probe for a topic's
    #: existence independent of its public/private state).
    article_share_keys: dict[UUID, str] = field(default_factory=dict)
    #: Resolved fresh from the real, current CareerProfile — never
    #: stored on ShowcasePage itself (see that entity's own docstring
    #: for why the profile picture is deliberately "fixed").
    photo_url: str | None = None
    #: Fresh presigned URLs for the owner's uploaded resume document
    #: (private bucket, unlike photo_url/background_image_url's public
    #: one) — both None whenever no resume has been uploaded.
    #: resume_view_url opens inline, resume_download_url saves the file
    #: — see ShowcasePageService.get_resume_urls's own docstring for why
    #: these are two separate URLs, resolved fresh on every read rather
    #: than stored.
    resume_view_url: str | None = None
    resume_download_url: str | None = None


@dataclass(frozen=True, slots=True)
class PublicArticleView:
    topic: InterviewTopic
    owner_display_name: str
    owner_handle: str
    #: Presigned URL per image-type column id — Article images are
    #: private-bucket, so unlike ShowcasePage's own image_url (a direct,
    #: non-expiring public-bucket URL persisted on the column itself)
    #: these are resolved fresh on every read and never persisted.
    image_urls: dict[UUID, str] = field(default_factory=dict)
    #: share_key for every `article_link` column (this Article can link
    #: to another one) whose target InterviewTopic is CURRENTLY public —
    #: same "omitted entirely, never a None entry, for anything that
    #: doesn't currently resolve" rule as
    #: PublicShowcasePageView.article_share_keys.
    article_share_keys: dict[UUID, str] = field(default_factory=dict)


class PublicShowcaseService:
    def __init__(
        self,
        share_links: PublicShareLinkRepository,
        tenant_context: TenantContextBinder,
        pages: ShowcasePageRepository,
        topics: InterviewTopicRepository,
        target_roles: TargetRoleRepository,
        users: UserRepository,
        career_profiles: CareerProfileRepository,
        storage: PrivateObjectStorageRepository,
    ) -> None:
        self._share_links = share_links
        self._tenant_context = tenant_context
        self._pages = pages
        self._topics = topics
        self._target_roles = target_roles
        self._users = users
        self._career_profiles = career_profiles
        self._storage = storage

    async def get_showcase_page(self, share_key: str) -> PublicShowcasePageView | None:
        link = await self._share_links.get_by_key(share_key)
        if link is None or link.resource_type != "showcase_page":
            return None

        await self._tenant_context.bind(link.tenant_id)

        page = await self._pages.get_by_id(link.tenant_id, link.resource_id)
        if page is None or not page.is_public:
            return None

        role = await self._target_roles.get_by_id(link.tenant_id, page.target_role_id)
        owner = await self._users.get_by_id(link.tenant_id, link.user_id)
        if role is None or owner is None:
            # A dangling link (target role or user deleted out from under
            # a still-public page) — treat as not-found, same as every
            # other unreachable case here.
            return None

        article_share_keys: dict[UUID, str] = {}
        for block in page.blocks:
            for column in block.columns:
                if column.type != "article_link" or column.article_topic_id is None:
                    continue
                topic = await self._topics.get_by_id(link.tenant_id, column.article_topic_id)
                if topic is None or not topic.is_public:
                    continue
                article_link = await self._share_links.get_by_resource(
                    "interview_topic", topic.id
                )
                if article_link is not None:
                    article_share_keys[topic.id] = article_link.share_key

        photo_url = await _resolve_photo_url(
            self._career_profiles,
            tenant_id=link.tenant_id,
            user_id=link.user_id,
            target_role_id=page.target_role_id,
        )

        resume_view_url: str | None = None
        resume_download_url: str | None = None
        if page.resume_file_key is not None:
            extension = page.resume_file_key.rsplit(".", 1)[-1]
            filename = resume_download_filename(
                display_name=owner.display_name, extension=extension
            )
            resume_view_url = await self._storage.get_presigned_url(
                key=page.resume_file_key,
                expires_in_seconds=RESUME_DOWNLOAD_URL_TTL_SECONDS,
                download_filename=filename,
                disposition="inline",
            )
            resume_download_url = await self._storage.get_presigned_url(
                key=page.resume_file_key,
                expires_in_seconds=RESUME_DOWNLOAD_URL_TTL_SECONDS,
                download_filename=filename,
                disposition="attachment",
            )

        return PublicShowcasePageView(
            page=page,
            owner_display_name=owner.display_name,
            owner_handle=owner.handle or "",
            role_name=role.role_name,
            role_tag=role.tag,
            article_share_keys=article_share_keys,
            photo_url=photo_url,
            resume_view_url=resume_view_url,
            resume_download_url=resume_download_url,
        )

    async def get_article(self, share_key: str) -> PublicArticleView | None:
        link = await self._share_links.get_by_key(share_key)
        if link is None or link.resource_type != "interview_topic":
            return None

        await self._tenant_context.bind(link.tenant_id)

        topic = await self._topics.get_by_id(link.tenant_id, link.resource_id)
        if topic is None or not topic.is_public:
            return None

        owner = await self._users.get_by_id(link.tenant_id, link.user_id)
        if owner is None:
            return None

        image_urls: dict[UUID, str] = {}
        article_share_keys: dict[UUID, str] = {}
        for block in topic.blocks:
            for column in block.columns:
                if column.type == "image" and column.image_key:
                    image_urls[column.id] = await self._storage.get_presigned_url(
                        key=column.image_key, expires_in_seconds=300
                    )
                elif column.type == "article_link" and column.article_topic_id is not None:
                    linked_topic = await self._topics.get_by_id(
                        link.tenant_id, column.article_topic_id
                    )
                    if linked_topic is None or not linked_topic.is_public:
                        continue
                    article_link = await self._share_links.get_by_resource(
                        "interview_topic", linked_topic.id
                    )
                    if article_link is not None:
                        article_share_keys[linked_topic.id] = article_link.share_key

        return PublicArticleView(
            topic=topic,
            owner_display_name=owner.display_name,
            owner_handle=owner.handle or "",
            image_urls=image_urls,
            article_share_keys=article_share_keys,
        )
