"""Career Profile domain entities.

Plain dataclasses — no SQLAlchemy, no Pydantic, no FastAPI. Mirrors the
pattern established in app/domain/identity/entities.py.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from uuid import UUID


@dataclass(slots=True)
class CoreCompetency:
    """A single Core Competencies / My Skills entry — the same field
    (CareerProfile.core_competencies) is edited from both the Career
    Profile page and the Skill Intelligence page. `category` is a plain
    per-item attribute, not a link into a shared catalog (ADR-005
    removed the old global SkillCategory model entirely) — two users'
    "Agile & Scaling" categories are unrelated strings, not the same row.
    """

    name: str
    category: str | None = None
    #: Per-item resume-inclusion toggle — default True (on). See
    #: CareerProfile.resume_section_toggles for the section-level
    #: (whole Core Competencies section) counterpart.
    include_in_resume: bool = True


@dataclass(slots=True)
class CareerProfile:
    id: UUID
    tenant_id: UUID
    user_id: UUID
    current_version: int
    headline: str | None
    summary: str | None
    career_readiness_score: int | None
    photo_url: str | None
    core_competencies: list[CoreCompetency]
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None = None
    # None = use the page's default section order. Only ever set via an
    # explicit reorder action (UI enhancement brief follow-up) — not a
    # "tracked" profile field, so it's deliberately excluded from
    # CareerProfileVersion snapshots (see career_profile_service.py).
    section_order: list[str] | None = None
    # None = the Master Profile. A real id = one of this user's Target
    # Role Profiles — a fully independent row, not a filter/view over
    # Master. See career_profile_service.py's get_or_create for how this
    # is resolved.
    target_role_id: UUID | None = None
    # Storage keys (in the private resumes bucket) for the most recently
    # generated resume document, one per format — same "regenerating
    # overwrites, doesn't accumulate a history" model as photo_url.
    # None if that format has never been generated for this profile. See
    # ResumeExportService.
    resume_docx_key: str | None = None
    resume_pdf_key: str | None = None
    resume_generated_at: datetime | None = None
    # Whole-section resume-inclusion toggles, keyed by the same section
    # keys CareerProfilePage.tsx's SECTION_DEFS/section_order already
    # use (core_competencies, career_highlights, experience, education,
    # certifications, key_achievements, career_goals, recommendations).
    # A missing key (including None entirely, the default for a profile
    # that's never touched this) means "on" — see
    # ResumeExportService._section_enabled. Independent per profile
    # (Master and each Target Role Profile has its own row), even
    # though career_goals' underlying data is itself shared across all
    # of a user's profiles.
    resume_section_toggles: dict[str, bool] | None = None


@dataclass(slots=True)
class CareerProfileSummary:
    """Cheap existence/counts snapshot of one profile (Master or a Target
    Role Profile) — powers the Override-vs-Merge prompt during resume
    merge, so the user sees "this profile already has 3 experience
    entries and a summary" instead of a content-free yes/no.
    """

    experience_count: int
    education_count: int
    certification_count: int
    career_highlight_count: int
    key_achievement_count: int
    competency_count: int
    has_headline: bool
    has_summary: bool

    @property
    def has_any_data(self) -> bool:
        return (
            self.experience_count > 0
            or self.education_count > 0
            or self.certification_count > 0
            or self.career_highlight_count > 0
            or self.key_achievement_count > 0
            or self.competency_count > 0
            or self.has_headline
            or self.has_summary
        )


@dataclass(slots=True)
class CareerProfileVersion:
    id: UUID
    career_profile_id: UUID
    version_number: int
    snapshot: dict[str, object]
    change_reason: str | None
    created_at: datetime


@dataclass(slots=True)
class Experience:
    id: UUID
    tenant_id: UUID
    career_profile_id: UUID
    title: str
    company: str
    location: str | None
    start_date: date
    end_date: date | None  # None = current role
    description: str | None
    display_order: int
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None = None
    #: Per-item resume-inclusion toggle — default True (on).
    include_in_resume: bool = True


@dataclass(slots=True)
class Education:
    id: UUID
    tenant_id: UUID
    career_profile_id: UUID
    institution: str
    degree: str | None
    field_of_study: str | None
    start_date: date | None
    end_date: date | None
    description: str | None
    display_order: int
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None = None
    #: Per-item resume-inclusion toggle — default True (on).
    include_in_resume: bool = True


@dataclass(slots=True)
class Certification:
    id: UUID
    tenant_id: UUID
    career_profile_id: UUID
    name: str
    issuing_organization: str
    issue_date: date | None
    expiration_date: date | None
    credential_id: str | None
    credential_url: str | None
    display_order: int
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None = None
    #: Per-item resume-inclusion toggle — default True (on).
    include_in_resume: bool = True


@dataclass(slots=True)
class CareerGoal:
    id: UUID
    tenant_id: UUID
    user_id: UUID
    target_role: str
    target_date: date | None
    status: str
    description: str | None
    display_order: int
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None = None
    #: Per-item resume-inclusion toggle — default True (on).
    include_in_resume: bool = True


@dataclass(slots=True)
class CareerHighlight:
    id: UUID
    tenant_id: UUID
    career_profile_id: UUID
    title: str
    company: str | None
    description: str | None
    occurred_on: date | None
    display_order: int
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None = None
    #: Per-item resume-inclusion toggle — default True (on).
    include_in_resume: bool = True


@dataclass(slots=True)
class KeyAchievement:
    id: UUID
    tenant_id: UUID
    career_profile_id: UUID
    title: str
    company: str | None
    description: str | None
    occurred_on: date | None
    display_order: int
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None = None
    #: Per-item resume-inclusion toggle — default True (on).
    include_in_resume: bool = True


@dataclass(slots=True)
class PeerEndorsement:
    id: UUID
    tenant_id: UUID
    career_profile_id: UUID
    recommender_name: str
    recommender_title: str | None
    relationship: str | None
    content: str
    display_order: int
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None = None
    #: Per-item resume-inclusion toggle — default True (on).
    include_in_resume: bool = True


@dataclass(slots=True)
class TargetRole:
    """Up to 5 per user (UI enhancement brief Part 2.5) — a Right Nav
    widget on the Career Profile page, not a page section. A standalone
    entity with its own id, not a list[str] field on CareerProfile: the
    brief's explicit future scope is tagging other profile items against
    these roles, which needs a stable id to reference — a flat string
    list would make that fragile (renaming or retyping a role would
    silently break any reference pointing at the old text). That
    cross-entity tagging feature is out of scope for this round.

    `tag` here is a different, simpler thing: a short (<=3 char) label
    the user picks for the role itself, e.g. "EAC" for "Enterprise
    Agile Coach" — not to be confused with the tagging feature above.

    `required_skills` is a plain free-text list (same shape as
    CareerProfile.core_competencies) — the skill_intelligence domain's
    catalog/proficiency/category model was removed by explicit user
    decision (see ADR-005); this replaced TargetRoleSkill's catalog-linked
    rows.
    """

    id: UUID
    tenant_id: UUID
    user_id: UUID
    role_name: str
    tag: str
    created_at: datetime
    deleted_at: datetime | None = None
    required_skills: list[str] = field(default_factory=list)
