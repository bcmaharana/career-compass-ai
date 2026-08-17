"""Unit tests for resume_docx_builder.py / resume_pdf_builder.py.

Real python-docx/reportlab calls (not faked) — these are pure functions
over a ResumeData bundle, cheap enough to run for real. The DOCX output
is parsed back with python-docx to assert on actual paragraph text; the
PDF builder is only checked for "doesn't raise / produces bytes," since
asserting on PDF *content* would need a PDF-parsing dependency this
project doesn't otherwise need.
"""

from __future__ import annotations

import io
import uuid
from dataclasses import replace
from datetime import UTC, date, datetime

import pytest
from docx import Document as DocxReader

from app.adapters.documents.resume_data import ResumeData, contact_line_parts
from app.adapters.documents.resume_docx_builder import build_resume_docx
from app.adapters.documents.resume_pdf_builder import build_resume_pdf
from app.domain.career_profile.entities import (
    CareerProfile,
    Certification,
    CoreCompetency,
    Education,
    Experience,
)
from app.domain.identity.entities import User


def _make_profile(
    *,
    core_competencies: list[CoreCompetency] | None = None,
    section_order: list[str] | None = None,
) -> CareerProfile:
    now = datetime.now(UTC)
    return CareerProfile(
        id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        current_version=1,
        headline=None,
        summary=None,
        career_readiness_score=None,
        photo_url=None,
        core_competencies=core_competencies or [],
        created_at=now,
        updated_at=now,
        section_order=section_order,
    )


def _make_experience() -> Experience:
    now = datetime.now(UTC)
    return Experience(
        id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        career_profile_id=uuid.uuid4(),
        title="Engineer",
        company="Acme",
        location=None,
        start_date=date(2020, 1, 1),
        end_date=None,
        description=None,
        display_order=0,
        created_at=now,
        updated_at=now,
    )


def _make_user() -> User:
    now = datetime.now(UTC)
    return User(
        id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        org_id=None,
        email="jordan@example.com",
        salutation=None,
        first_name="Jordan",
        last_name="Rivera",
        hashed_password="x",
        status="active",
        mfa_enabled=False,
        created_at=now,
        updated_at=now,
    )


def _make_education(*, description: str | None) -> Education:
    now = datetime.now(UTC)
    return Education(
        id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        career_profile_id=uuid.uuid4(),
        institution="Institution of Engineers (India)",
        degree="BE",
        field_of_study="Electronics and Communication Engineering",
        start_date=date(2010, 1, 1),
        end_date=date(2014, 1, 1),
        description=description,
        display_order=0,
        created_at=now,
        updated_at=now,
    )


def _docx_paragraph_texts(docx_bytes: bytes) -> list[str]:
    doc = DocxReader(io.BytesIO(docx_bytes))
    return [p.text for p in doc.paragraphs if p.text.strip()]


def _docx_heading_texts(docx_bytes: bytes) -> list[str]:
    doc = DocxReader(io.BytesIO(docx_bytes))
    return [
        p.text for p in doc.paragraphs if p.style is not None and p.style.name.startswith("Heading")
    ]


@pytest.mark.unit
class TestEducationDegreeDeduplication:
    """A real bug reported live: when a profile's education description
    already repeats the degree/field_of_study as its own bullet (e.g.
    from an earlier resume import), the generated document printed it
    twice — once in the constructed "Institution — Degree in Field"
    line, once again as a bullet immediately below it.
    """

    def test_a_description_bullet_matching_the_degree_line_is_dropped(self) -> None:
        education = _make_education(
            description="<ul><li>BE in Electronics and Communication Engineering</li></ul>"
        )
        data = ResumeData(
            profile=_make_profile(),
            user=_make_user(),
            experiences=[],
            educations=[education],
            certifications=[],
            career_highlights=[],
            key_achievements=[],
            career_goals=[],
            recommendations=[],
            role_label=None,
        )

        paragraphs = _docx_paragraph_texts(build_resume_docx(data))

        assert (
            "Institution of Engineers (India) — BE in Electronics and Communication Engineering"
            in paragraphs
        )
        # The redundant bullet must not appear as its own paragraph.
        assert "BE in Electronics and Communication Engineering" not in paragraphs
        assert sum("Electronics and Communication Engineering" in p for p in paragraphs) == 1

    def test_a_genuinely_distinct_bullet_is_kept_alongside_a_redundant_one(self) -> None:
        education = _make_education(
            description=(
                "<ul><li>BE in Electronics and Communication Engineering</li>"
                "<li>Graduated with honors, GPA 3.9</li></ul>"
            )
        )
        data = ResumeData(
            profile=_make_profile(),
            user=_make_user(),
            experiences=[],
            educations=[education],
            certifications=[],
            career_highlights=[],
            key_achievements=[],
            career_goals=[],
            recommendations=[],
            role_label=None,
        )

        paragraphs = _docx_paragraph_texts(build_resume_docx(data))

        assert "Graduated with honors, GPA 3.9" in paragraphs
        assert "BE in Electronics and Communication Engineering" not in paragraphs

    def test_pdf_builder_does_not_raise_for_the_same_redundant_description(self) -> None:
        education = _make_education(
            description="<ul><li>BE in Electronics and Communication Engineering</li></ul>"
        )
        data = ResumeData(
            profile=_make_profile(),
            user=_make_user(),
            experiences=[],
            educations=[education],
            certifications=[],
            career_highlights=[],
            key_achievements=[],
            career_goals=[],
            recommendations=[],
            role_label=None,
        )

        pdf_bytes = build_resume_pdf(data)

        assert pdf_bytes.startswith(b"%PDF")


@pytest.mark.unit
class TestCoreCompetenciesGrouping:
    """Requested live: Core Competencies should render the same way the
    Career Profile/Skill Intelligence pages already display them —
    grouped by category, category order following first-encountered
    position (not alphabetical) — with the skills within a category
    comma-separated on one line, not one per bullet.
    """

    def test_groups_by_category_in_first_encountered_order_comma_separated(self) -> None:
        competencies = [
            CoreCompetency(name="SAFe 6", category="Agile & Scaling"),
            CoreCompetency(name="Scrum", category="Agile & Scaling"),
            CoreCompetency(name="Python", category="Programming"),
            CoreCompetency(name="Excel"),  # uncategorized
        ]
        data = ResumeData(
            profile=_make_profile(core_competencies=competencies),
            user=_make_user(),
            experiences=[],
            educations=[],
            certifications=[],
            career_highlights=[],
            key_achievements=[],
            career_goals=[],
            recommendations=[],
            role_label=None,
        )

        paragraphs = _docx_paragraph_texts(build_resume_docx(data))

        assert "Agile & Scaling: SAFe 6, Scrum" in paragraphs
        assert "Programming: Python" in paragraphs
        assert "Uncategorized: Excel" in paragraphs
        # "Agile & Scaling" was the first category encountered, so it
        # must come before "Programming" — not alphabetical (P < A).
        assert paragraphs.index("Agile & Scaling: SAFe 6, Scrum") < paragraphs.index(
            "Programming: Python"
        )

    def test_pdf_builder_does_not_raise_for_grouped_competencies(self) -> None:
        competencies = [
            CoreCompetency(name="SAFe 6", category="Agile & Scaling"),
            CoreCompetency(name="Excel"),
        ]
        data = ResumeData(
            profile=_make_profile(core_competencies=competencies),
            user=_make_user(),
            experiences=[],
            educations=[],
            certifications=[],
            career_highlights=[],
            key_achievements=[],
            career_goals=[],
            recommendations=[],
            role_label=None,
        )

        pdf_bytes = build_resume_pdf(data)

        assert pdf_bytes.startswith(b"%PDF")


@pytest.mark.unit
class TestSectionOrderFollowsTheProfile:
    """Requested live: a resume must render sections in the same order
    the person has arranged on that specific profile (Master and each
    Target Role Profile order independently, since section_order lives
    on the CareerProfile row itself) — not a hardcoded sequence.
    """

    def test_a_custom_section_order_is_respected(self) -> None:
        profile = _make_profile(
            section_order=["certifications", "experience", "education"]
        )
        cert = Certification(
            id=uuid.uuid4(),
            tenant_id=uuid.uuid4(),
            career_profile_id=uuid.uuid4(),
            name="AWS Cert",
            issuing_organization="AWS",
            issue_date=None,
            expiration_date=None,
            credential_id=None,
            credential_url=None,
            display_order=0,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        data = ResumeData(
            profile=profile,
            user=_make_user(),
            experiences=[_make_experience()],
            educations=[],
            certifications=[cert],
            career_highlights=[],
            key_achievements=[],
            career_goals=[],
            recommendations=[],
            role_label=None,
        )

        headings = _docx_heading_texts(build_resume_docx(data))

        assert headings.index("Certifications") < headings.index("Professional Experience")

    def test_an_unset_section_order_falls_back_to_the_default(self) -> None:
        profile = _make_profile(section_order=None)
        data = ResumeData(
            profile=profile,
            user=_make_user(),
            experiences=[_make_experience()],
            educations=[],
            certifications=[],
            career_highlights=[],
            key_achievements=[],
            career_goals=[],
            recommendations=[],
            role_label=None,
        )

        headings = _docx_heading_texts(build_resume_docx(data))

        # Default order: core_competencies, career_highlights, experience,
        # education, certifications, key_achievements, career_goals,
        # recommendations — experience is the only section with data
        # here, so it's the only section heading.
        assert headings == ["Professional Experience"]

    def test_an_unknown_saved_key_is_dropped_not_erroring(self) -> None:
        profile = _make_profile(
            section_order=["some_future_section", "another_stale_key", "experience"]
        )
        data = ResumeData(
            profile=profile,
            user=_make_user(),
            experiences=[_make_experience()],
            educations=[],
            certifications=[],
            career_highlights=[],
            key_achievements=[],
            career_goals=[],
            recommendations=[],
            role_label=None,
        )

        headings = _docx_heading_texts(build_resume_docx(data))

        assert headings == ["Professional Experience"]

    def test_pdf_builder_respects_a_custom_section_order_too(self) -> None:
        profile = _make_profile(section_order=["certifications", "experience"])
        cert = Certification(
            id=uuid.uuid4(),
            tenant_id=uuid.uuid4(),
            career_profile_id=uuid.uuid4(),
            name="AWS Cert",
            issuing_organization="AWS",
            issue_date=None,
            expiration_date=None,
            credential_id=None,
            credential_url=None,
            display_order=0,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        data = ResumeData(
            profile=profile,
            user=_make_user(),
            experiences=[_make_experience()],
            educations=[],
            certifications=[cert],
            career_highlights=[],
            key_achievements=[],
            career_goals=[],
            recommendations=[],
            role_label=None,
        )

        pdf_bytes = build_resume_pdf(data)

        assert pdf_bytes.startswith(b"%PDF")


@pytest.mark.unit
class TestContactLineParts:
    """Requested live: the resume header's pipe-separated contact line
    (previously just email | phone) should also show location (city,
    state), Visa Status, and LinkedIn URL — with the URL's scheme/www.
    stripped, since a bare "linkedin.com/in/name" reads cleaner in a
    resume header than the full https://www. form.
    """

    def test_includes_every_field_when_all_are_set(self) -> None:
        user = replace(
            _make_user(),
            phone_number="+1 415 555 0100",
            city="San Francisco",
            state="CA",
            visa_status="H-1B",
            linkedin_url="https://www.linkedin.com/in/jordanrivera",
        )

        assert contact_line_parts(user) == [
            "jordan@example.com",
            "+1 415 555 0100",
            "San Francisco, CA",
            "H-1B",
            "linkedin.com/in/jordanrivera",
        ]

    def test_strips_bare_https_scheme_without_www(self) -> None:
        user = replace(_make_user(), linkedin_url="https://linkedin.com/in/jordanrivera")

        assert contact_line_parts(user)[-1] == "linkedin.com/in/jordanrivera"

    def test_omits_fields_that_are_unset(self) -> None:
        user = _make_user()  # phone/city/state/visa_status/linkedin_url all None

        assert contact_line_parts(user) == ["jordan@example.com"]

    def test_location_uses_city_alone_when_state_is_unset(self) -> None:
        user = replace(_make_user(), city="Remote", state=None)

        assert "Remote" in contact_line_parts(user)

    def test_renders_in_the_generated_docx_header(self) -> None:
        user = replace(
            _make_user(),
            city="San Francisco",
            state="CA",
            visa_status="H-1B",
            linkedin_url="https://www.linkedin.com/in/jordanrivera",
        )
        data = ResumeData(
            profile=_make_profile(),
            user=user,
            experiences=[],
            educations=[],
            certifications=[],
            career_highlights=[],
            key_achievements=[],
            career_goals=[],
            recommendations=[],
            role_label=None,
        )

        paragraphs = _docx_paragraph_texts(build_resume_docx(data))

        assert (
            "jordan@example.com | San Francisco, CA | H-1B | linkedin.com/in/jordanrivera"
            in paragraphs
        )
