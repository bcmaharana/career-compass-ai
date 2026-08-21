"""Interview Preparation domain entities.

Plain dataclasses — no SQLAlchemy, no Pydantic, no FastAPI. Mirrors the
pattern established in app/domain/career_profile/entities.py.

Both InterviewTopic and InterviewQuestion carry `scope_target_role_ids:
list[UUID | None]` — the set of scopes this item is tagged into and
visible under (None entries mean the Master/generic scope, a real id
means a specific Target Role). This is a genuine many-to-many tagging
model, not the single-exclusive-scope split most of this app's other
entities use (see CareerProfile) — requested directly by the user:
"Each question or topic can be tagged with one or more roles...
Correcting in one place will update in others automatically." A tagged
item is the SAME row surfaced under every scope in this list, not a
copy — editing or deleting it affects every scope it's tagged to at
once (deletion has an explicit "everywhere" vs "just this scope" choice
at the service layer, see InterviewTopicService.delete). There is no
longer a single "home"/original scope distinguished from "additional"
tags — the full set is always freely editable, matching the user's
explicit choice over pinning the creation-time scope.

Ordering (display_order) deliberately does NOT live on these entities —
the same item can sit at a different position in each scope's own list
(confirmed with the user: reordering is independent per scope, not
shared), so display_order is a property of the (item, scope) pairing,
tracked only in the InterviewTopicScopeTag/InterviewQuestionScopeTag
join-table rows the repository layer manages — never exposed on the
domain entity itself.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID


@dataclass(slots=True)
class ReferenceLink:
    """A labeled external URL attached to an InterviewQuestion — a label
    reads far better in the UI than a bare link, so this is a small
    value type rather than a plain list[str] (contrast
    TargetRole.required_skills, which has no per-item metadata and so
    stays a plain string list)."""

    url: str
    label: str


# Scheme allowlist rather than a denylist — a denylist only ever catches
# the schemes someone thought to name. Applied at every ReferenceLink
# write site (both InterviewQuestion and InterviewTopic), not just
# rendered defensively on the frontend: an `<a href>` with no scheme
# validation is a stored-XSS vector for a crafted `javascript:`/`data:`
# URL, and this app's own convention elsewhere (sanitize on write, never
# trust render time alone) says the check belongs here.
_SAFE_URL_SCHEMES = frozenset({"http", "https", "mailto"})
# RFC 3986's scheme grammar: a leading ALPHA, then any mix of
# letters/digits/+/-/.  A dangerous scheme like "javascript:" or
# "data:" matches this just as validly as "http:" does — critically,
# neither requires a "//" after the colon, so a naive check for "://"
# would let "javascript:alert(1)" straight through unblocked.
_SCHEME_RE = re.compile(r"^([a-zA-Z][a-zA-Z0-9+.-]*):")


def is_safe_reference_url(url: str) -> bool:
    match = _SCHEME_RE.match(url.strip())
    if match is None:
        # A scheme-less value (e.g. "linkedin.com/in/x", matching this
        # app's existing deliberately-permissive LinkedIn/credential-URL
        # fields) is safe — a bare host/path string carries no scheme for
        # a browser to execute, it can only ever be rendered as a literal
        # <a href> attribute value.
        return True
    return match.group(1).lower() in _SAFE_URL_SCHEMES


@dataclass(slots=True)
class InterviewTopic:
    """A study-notes card: a name, optional free-text discussion, and an
    optional image (stored in the private object storage bucket — see
    app/domain/resume_intelligence/storage.py's PrivateObjectStorageRepository,
    reused here rather than introducing a third bucket). `section` is a
    plain free-text grouping label with no separate entity of its own —
    same "just a string on each item" pattern CoreCompetency.category
    already uses for Core Competencies/My Skills.
    """

    id: UUID
    tenant_id: UUID
    user_id: UUID
    name: str
    created_at: datetime
    updated_at: datetime
    #: Every scope this topic is tagged into and visible under — see
    #: this module's own docstring. Always non-empty for a persisted
    #: topic (enforced by InterviewTopicService, not here).
    scope_target_role_ids: list[UUID | None] = field(default_factory=list)
    section: str | None = None
    discussion: str | None = None
    image_key: str | None = None  # private-bucket storage key, not a URL
    reference_links: list[ReferenceLink] = field(default_factory=list)
    deleted_at: datetime | None = None


@dataclass(slots=True)
class InterviewQuestion:
    """An interview question with a place for the user's own answer, an
    AI-generated one (read-only, regenerate-only — see
    InterviewAnswerService), a list of labeled reference links, and an
    optional link to one of this scope's InterviewTopics. `category` is
    a plain free-text grouping label with no separate entity of its
    own — same "just a string on each item" pattern
    InterviewTopic.section already established for grouping Topics.

    A follow-up question (`parent_question_id` set) is the SAME entity
    shape, deliberately reused rather than a separate type — it gets a
    manual answer, AI-suggested answer, and reference links exactly like
    a top-level question, for free. Single level only (enforced by
    InterviewQuestionService: a question that already has a
    parent_question_id can't itself be given one) — a follow-up has no
    `category`/`topic_id` of its own (always None, no UI for either) and
    is NOT independently scope-tagged (`scope_target_role_ids` is always
    empty for it): it's visible wherever its parent is, inheriting the
    parent's scopes entirely rather than tracking its own tag rows. Its
    `display_order` (unlike a top-level question's, which lives in
    InterviewQuestionScopeTagModel since ordering is per-scope) is a
    plain column on the row itself, scoped among siblings sharing the
    same parent_question_id — a follow-up has exactly one list to sit
    in, not one per scope, so per-scope ordering doesn't apply to it.
    """

    id: UUID
    tenant_id: UUID
    user_id: UUID
    question: str
    created_at: datetime
    updated_at: datetime
    #: Every scope this question is tagged into and visible under — see
    #: this module's own docstring. Always non-empty for a persisted
    #: top-level question (enforced by InterviewQuestionService); always
    #: empty for a follow-up (parent_question_id is not None).
    scope_target_role_ids: list[UUID | None] = field(default_factory=list)
    topic_id: UUID | None = None
    category: str | None = None
    manual_answer: str | None = None
    ai_answer: str | None = None
    #: None = never generated. "generated" | "failed".
    ai_answer_status: str | None = None
    ai_answer_error: str | None = None
    ai_answer_generated_at: datetime | None = None
    reference_links: list[ReferenceLink] = field(default_factory=list)
    #: None for a top-level question. Set to the parent's id for a
    #: follow-up — see this class's own docstring.
    parent_question_id: UUID | None = None
    #: Populated by InterviewQuestionRepository.list_for_scope() (and by
    #: create()/update() for a top-level question) — never persisted
    #: itself, and always empty on a follow-up's own InterviewQuestion
    #: (single level only, so a follow-up never has follow_ups of its
    #: own).
    follow_ups: list[InterviewQuestion] = field(default_factory=list)
    deleted_at: datetime | None = None
