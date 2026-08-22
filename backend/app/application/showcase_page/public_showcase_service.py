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

from app.domain.career_profile.repositories import TargetRoleRepository
from app.domain.identity.repositories import TenantContextBinder, UserRepository
from app.domain.interview_prep.entities import InterviewTopic
from app.domain.interview_prep.repositories import InterviewTopicRepository
from app.domain.resume_intelligence.storage import PrivateObjectStorageRepository
from app.domain.showcase_page.entities import ShowcasePage
from app.domain.showcase_page.repositories import PublicShareLinkRepository, ShowcasePageRepository


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


@dataclass(frozen=True, slots=True)
class PublicArticleView:
    topic: InterviewTopic
    owner_display_name: str
    owner_handle: str
    image_url: str | None


class PublicShowcaseService:
    def __init__(
        self,
        share_links: PublicShareLinkRepository,
        tenant_context: TenantContextBinder,
        pages: ShowcasePageRepository,
        topics: InterviewTopicRepository,
        target_roles: TargetRoleRepository,
        users: UserRepository,
        storage: PrivateObjectStorageRepository,
    ) -> None:
        self._share_links = share_links
        self._tenant_context = tenant_context
        self._pages = pages
        self._topics = topics
        self._target_roles = target_roles
        self._users = users
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
            if block.type != "article_link" or block.article_topic_id is None:
                continue
            topic = await self._topics.get_by_id(link.tenant_id, block.article_topic_id)
            if topic is None or not topic.is_public:
                continue
            article_link = await self._share_links.get_by_resource(
                "interview_topic", topic.id
            )
            if article_link is not None:
                article_share_keys[topic.id] = article_link.share_key

        return PublicShowcasePageView(
            page=page,
            owner_display_name=owner.display_name,
            owner_handle=owner.handle or "",
            role_name=role.role_name,
            role_tag=role.tag,
            article_share_keys=article_share_keys,
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

        image_url = None
        if topic.image_key is not None:
            image_url = await self._storage.get_presigned_url(
                key=topic.image_key, expires_in_seconds=300
            )

        return PublicArticleView(
            topic=topic,
            owner_display_name=owner.display_name,
            owner_handle=owner.handle or "",
            image_url=image_url,
        )
