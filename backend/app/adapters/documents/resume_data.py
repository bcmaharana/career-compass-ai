"""Shared data shape for resume document generation.

Both resume_docx_builder.py and resume_pdf_builder.py take a ResumeData
instance — built once by ResumeExportService
(app/application/career_profile/resume_export_service.py) from a
CareerProfile plus its child entities and the owning User — so the two
renderers never duplicate "which fields feed a resume," only how to lay
them out in their own format.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from app.domain.career_profile.entities import (
    CareerGoal,
    CareerHighlight,
    CareerProfile,
    Certification,
    CoreCompetency,
    Education,
    Experience,
    KeyAchievement,
    PeerEndorsement,
)
from app.domain.identity.entities import User


@dataclass(slots=True)
class ResumeData:
    profile: CareerProfile
    user: User
    experiences: list[Experience]
    educations: list[Education]
    certifications: list[Certification]
    career_highlights: list[CareerHighlight]
    key_achievements: list[KeyAchievement]
    career_goals: list[CareerGoal]
    #: Named "recommendations" (not "peer_endorsements") to match the
    #: section key CareerProfilePage.tsx's SECTION_DEFS/section_order and
    #: the resume-inclusion toggle feature already use for this section.
    recommendations: list[PeerEndorsement]
    #: The target role's display name (e.g. "Senior Engineer") — None
    #: for the Master Profile. Shown as a subtitle so a downloaded file
    #: is identifiable at a glance when someone has generated several.
    role_label: str | None


def description_lines(
    description: str | None, *, exclude: tuple[str | None, ...] = ()
) -> list[str]:
    """Splits a stored description into display lines using the same
    "a line starting with '• ' is a real bullet, everything else is a
    plain paragraph line" rule the Career Profile page's own UI and the
    resume-extraction prompt (seed_platform_defaults.py) both already
    use — so a generated resume renders the same shape of content the
    person already sees on their profile, not a re-interpretation of it.

    `exclude` drops any line that's an exact (case/whitespace-insensitive,
    bullet marker stripped) duplicate of one of the given reference
    strings — e.g. Education's constructed "degree in field" line.
    Observed live: a real profile's description repeated its own
    degree/field_of_study as a bullet, so the generated resume printed
    "Institution — BE in Electronics and Communication Engineering"
    immediately followed by a bullet reading the exact same text. This
    only catches an *exact* repeat, deliberately — anything looser
    (e.g. a differently-worded paraphrase) risks dropping real, distinct
    content, which is worse than an occasional harmless duplicate line.
    """
    if not description:
        return []
    excluded = {ref.strip().casefold() for ref in exclude if ref}
    lines = []
    for line in description.split("\n"):
        if not line.strip():
            continue
        if strip_bullet_marker(line).strip().casefold() in excluded:
            continue
        lines.append(line)
    return lines


def strip_bullet_marker(line: str) -> str:
    return line[2:] if line.startswith("• ") else line


def group_competencies_by_category(
    competencies: list[CoreCompetency],
) -> list[tuple[str | None, list[CoreCompetency]]]:
    """Groups core_competencies by category, category order following
    each category's *first-encountered position* — not alphabetical —
    exactly matching groupCompetenciesByCategory
    (frontend/src/lib/group-by-category.ts), the function that decides
    how this same field is grouped on the Career Profile/Skill
    Intelligence pages. A resume should list competencies the same way
    the person already sees them there, not re-sort them. Items with no
    category (or a blank one) land in a trailing (None, [...]) group,
    always last, same as that function's "Uncategorized" group.
    """
    order: list[str] = []
    groups: dict[str, list[CoreCompetency]] = {}
    uncategorized: list[CoreCompetency] = []

    for item in competencies:
        category = (item.category or "").strip()
        if not category:
            uncategorized.append(item)
            continue
        if category in groups:
            groups[category].append(item)
        else:
            groups[category] = [item]
            order.append(category)

    result: list[tuple[str | None, list[CoreCompetency]]] = [
        (category, groups[category]) for category in order
    ]
    if uncategorized:
        result.append((None, uncategorized))
    return result


def education_degree_line(education: Education) -> str:
    """"BE in Electronics and Communication Engineering" — the exact
    text rendered next to the institution name, and what
    description_lines' `exclude` is checked against for that same
    education entry (see its docstring)."""
    degree = education.degree or ""
    if education.field_of_study:
        return f"{degree} in {education.field_of_study}" if degree else education.field_of_study
    return degree


# Every key CareerProfilePage.tsx's SECTION_DEFS/section_order uses —
# matches the resume-inclusion toggle feature's section key set exactly,
# so every section a person can toggle on/off is also a section this
# module can actually render. An unknown key in a profile's saved order
# (e.g. a future renamed section) is silently dropped rather than
# erroring — same "drop stale/unknown keys" handling resolveOrder in
# that file already does for a never-heard-of key.
DEFAULT_RESUME_SECTION_ORDER: tuple[str, ...] = (
    "core_competencies",
    "career_highlights",
    "experience",
    "education",
    "certifications",
    "key_achievements",
    "career_goals",
    "recommendations",
)


def resolve_resume_section_order(saved: list[str] | None) -> list[str]:
    """Mirrors resolveOrder (CareerProfilePage.tsx) exactly, scoped to
    the sections this module renders: keeps the saved relative order for
    keys that still exist, drops anything stale/unknown (a future
    renamed key), and appends any default keys the saved order doesn't
    have yet — so a resume always includes every renderable section
    exactly once, in the same order the person sees them on whichever
    profile (Master or a specific Target Role Profile) this document was
    generated from.
    """
    if not saved:
        return list(DEFAULT_RESUME_SECTION_ORDER)
    known = [key for key in saved if key in DEFAULT_RESUME_SECTION_ORDER]
    missing = [key for key in DEFAULT_RESUME_SECTION_ORDER if key not in known]
    return known + missing


_URL_PREFIXES_TO_STRIP = ("https://www.", "http://www.", "https://", "http://")


def _strip_url_scheme(url: str) -> str:
    """"https://www.linkedin.com/in/jordan" -> "linkedin.com/in/jordan" —
    a resume header reads cleaner as a bare host+path than a full URL,
    and the scheme is implied anyway. Checked longest-prefix-first so a
    "www." URL doesn't fall through to the shorter bare-scheme case and
    leave "www." in the result.
    """
    stripped = url.strip()
    lowered = stripped.lower()
    for prefix in _URL_PREFIXES_TO_STRIP:
        if lowered.startswith(prefix):
            return stripped[len(prefix) :]
    return stripped


def contact_line_parts(user: User) -> list[str]:
    """The pipe-separated contact line under the resume's name/subtitle:
    email, phone, location (city, state), Visa Status, then LinkedIn URL
    — whichever of these the user has actually filled in, in this fixed
    order, so the line reads the same shape resume to resume rather than
    reordering itself around whatever happens to be blank.
    """
    parts: list[str] = []
    if user.email:
        parts.append(user.email)
    if user.phone_number:
        parts.append(user.phone_number)
    location = ", ".join(part for part in (user.city, user.state) if part)
    if location:
        parts.append(location)
    if user.visa_status:
        parts.append(user.visa_status)
    if user.linkedin_url:
        parts.append(_strip_url_scheme(user.linkedin_url))
    return parts


def format_date_range(start: date | None, end: date | None) -> str:
    """"Month YYYY - Month YYYY" / "Month YYYY - Present" / "Present"."""

    def fmt(d: date | None) -> str:
        return d.strftime("%b %Y") if d else ""

    if end is None:
        return f"{fmt(start)} - Present" if start else "Present"
    return f"{fmt(start)} - {fmt(end)}" if start else fmt(end)
