"""Request/response schemas for the Interview Preparation API."""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel


class ReferenceLinkPayload(BaseModel):
    url: str
    label: str


ArticleColumnTypePayload = Literal[
    "rich_text", "image", "video_embed", "article_link", "external_link"
]


class ArticleColumnPayload(BaseModel):
    """Same generic content-column shape as
    app/api/v1/showcase_page/schemas.py's ShowcaseColumnPayload (both
    wrap app/domain/content_blocks/entities.py's ContentColumn) — kept as
    its own, separately-named class rather than imported/reused directly,
    so each domain's OpenAPI schema names its own payload rather than one
    leaking the other's ("Showcase") name; see that module for the
    field-by-field rationale, identical here except image_key (Article
    images are private-bucket, unlike ShowcasePage's public-bucket ones —
    image_key is never sent by the client, only ever set server-side by
    the image-upload endpoint, and image_url in a response is always a
    fresh short-TTL presigned URL, never persisted)."""

    id: UUID
    type: ArticleColumnTypePayload
    label: str
    html: str | None = None
    image_url: str | None = None
    video_embed_url: str | None = None
    article_topic_id: UUID | None = None
    external_url: str | None = None


class ArticleBlockPayload(BaseModel):
    id: UUID
    #: 1 or more columns rendered side by side (equal width) on desktop,
    #: stacked vertically on mobile — see ContentBlock's own domain
    #: docstring. No cap on column count.
    columns: list[ArticleColumnPayload]


class InterviewTopicRequest(BaseModel):
    name: str
    section: str | None = None
    #: Every scope (Master and/or one or more Target Roles — None
    #: entries mean Master) this topic should be tagged into and
    #: visible under. Must contain at least one entry (enforced by
    #: InterviewTopicService, not here, for the same consistent
    #: domain-exception-over-Pydantic-validator convention this app's
    #: other services already follow).
    scope_target_role_ids: list[UUID | None]


class InterviewTopicUpdateRequest(BaseModel):
    name: str
    section: str | None = None
    blocks: list[ArticleBlockPayload] = []
    scope_target_role_ids: list[UUID | None]


class InterviewTopicResponse(BaseModel):
    id: UUID
    name: str
    section: str | None
    blocks: list[ArticleBlockPayload]
    scope_target_role_ids: list[UUID | None]
    is_public: bool
    #: The public URL's last path segment ("Article" when framed
    #: externally), present whenever this topic has ever been made
    #: public — see app/api/v1/showcase_page/schemas.py's
    #: ShowcasePageResponse.share_key for the full "why persists across
    #: toggle cycles, why the API doesn't return a full URL" rationale;
    #: identical here, just shared through the same public_share_links
    #: table with resource_type="interview_topic".
    share_key: str | None = None
    created_at: datetime


class ToggleTopicPublicRequest(BaseModel):
    is_public: bool


class InterviewQuestionRequest(BaseModel):
    topic_id: UUID | None = None
    question: str
    category: str | None = None
    scope_target_role_ids: list[UUID | None]


class InterviewQuestionUpdateRequest(BaseModel):
    topic_id: UUID | None = None
    question: str
    category: str | None = None
    manual_answer: str | None = None
    reference_links: list[ReferenceLinkPayload] = []
    scope_target_role_ids: list[UUID | None]


class InterviewQuestionResponse(BaseModel):
    id: UUID
    topic_id: UUID | None
    question: str
    category: str | None
    manual_answer: str | None
    ai_answer: str | None
    ai_answer_status: str | None
    ai_answer_error: str | None
    ai_answer_generated_at: datetime | None
    reference_links: list[ReferenceLinkPayload]
    scope_target_role_ids: list[UUID | None]
    #: None for a top-level question. Set for a follow-up — see
    #: app/domain/interview_prep/entities.py's InterviewQuestion
    #: docstring for the full "why" (single level only, no scope tags
    #: or topic/category of its own).
    parent_question_id: UUID | None
    #: Always empty on a follow-up's own response (single level only).
    #: Populated on a top-level question's response by
    #: InterviewQuestionRepository.list_for_scope()/update().
    follow_ups: list["InterviewQuestionResponse"] = []
    created_at: datetime


#: Required for Pydantic v2 to resolve the self-reference in follow_ups
#: above — a self-referencing model isn't safely usable in a FastAPI
#: response_model without this explicit rebuild.
InterviewQuestionResponse.model_rebuild()


class AddFollowUpQuestionRequest(BaseModel):
    question: str


class UpdateFollowUpQuestionRequest(BaseModel):
    question: str
    manual_answer: str | None = None
    reference_links: list[ReferenceLinkPayload] = []


class InterviewPrepMoveRequest(BaseModel):
    """Move endpoints need the scope currently being viewed, not just a
    direction — reordering is independent per scope (the same item can
    sit at a different position in each scope's own list), so there's
    no longer a single implicit scope to derive from the item itself.
    Not the shared career_profile.schemas.MoveRequest, since that extra
    field is specific to this domain's multi-scope model."""

    direction: Literal["up", "down"]
    target_role_id: UUID | None = None


class InterviewPrepScopeSummaryResponse(BaseModel):
    target_role_id: UUID | None
    role_name: str
    topic_count: int
    question_count: int


class InterviewPrepSummaryResponse(BaseModel):
    scopes: list[InterviewPrepScopeSummaryResponse]
    #: Distinct articles/questions across every scope — see
    #: InterviewPrepSummary's own docstring for why this isn't just a
    #: sum of each scope's own topic_count/question_count.
    total_topic_count: int
    total_question_count: int
