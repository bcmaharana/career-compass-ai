"""Unit tests for ResumeMergeService.

Wires the *real* ExperienceService/EducationService/CertificationService/
CareerProfileService against fake in-memory repositories, the same way
app/api/dependencies.py wires them against real SQLAlchemy repositories
— so these tests exercise the real merge-into-profile logic, not a
second reimplementation of it.
"""

from __future__ import annotations

import uuid
from dataclasses import replace
from datetime import UTC, datetime

import pytest

from app.application.career_profile.career_highlight_service import CareerHighlightService
from app.application.career_profile.career_profile_service import CareerProfileService
from app.application.career_profile.certification_service import CertificationService
from app.application.career_profile.education_service import EducationService
from app.application.career_profile.experience_service import ExperienceService
from app.application.career_profile.key_achievement_service import KeyAchievementService
from app.application.resume_intelligence.resume_merge_service import ResumeMergeService
from app.core.exceptions import CareerCompassError
from app.domain.career_profile.entities import (
    CareerHighlight,
    CareerProfile,
    CareerProfileVersion,
    Certification,
    CoreCompetency,
    Education,
    Experience,
    KeyAchievement,
)
from app.domain.resume_intelligence.entities import Resume

EXTRACTED_DATA: dict[str, object] = {
    "headline": "Senior Backend Engineer",
    "summary": "Backend engineer with 8 years of experience.",
    "skills": [
        {"name": "Python", "category": None},
        {"name": "AWS", "category": "Cloud"},
    ],
    "experience": [
        {
            "title": "Senior Backend Engineer",
            "company": "Initech",
            "location": None,
            "start_date": "2021-01-01",
            "end_date": None,
            "description": "Led migrations.",
        },
        {
            "title": "Software Engineer",
            "company": "Globex",
            "location": None,
            "start_date": "2018-06-01",
            "end_date": "2020-12-31",
            "description": None,
        },
    ],
    "education": [
        {
            "institution": "State University",
            "degree": "B.S. CS",
            "field_of_study": None,
            "start_date": "2014-09-01",
            "end_date": "2018-05-31",
            "description": None,
        }
    ],
    "certifications": [
        {
            "name": "AWS Certified",
            "issuing_organization": "AWS",
            "issue_date": "2022-01-01",
            "expiration_date": None,
            "credential_id": None,
            "credential_url": None,
        }
    ],
    "career_highlights": [
        {
            "title": "Led migration of monolith to microservices, cutting deploy time 40%.",
            "company": "Initech",
            "description": None,
            "occurred_on": None,
        }
    ],
    "key_achievements": [
        {
            "title": "Employee of the Year",
            "company": "Initech",
            "description": "Recognized for the microservices migration.",
            "occurred_on": None,
        }
    ],
}


class FakeResumeRepository:
    def __init__(self) -> None:
        self.resumes: dict[uuid.UUID, Resume] = {}

    async def create(self, resume: Resume) -> Resume:
        self.resumes[resume.id] = resume
        return replace(resume)

    async def get_by_id(self, tenant_id: uuid.UUID, resume_id: uuid.UUID) -> Resume | None:
        resume = self.resumes.get(resume_id)
        return replace(resume) if resume and resume.tenant_id == tenant_id else None

    async def list_for_user(self, tenant_id: uuid.UUID, user_id: uuid.UUID) -> list[Resume]:
        raise NotImplementedError

    async def soft_delete(self, tenant_id: uuid.UUID, resume_id: uuid.UUID) -> None:
        raise NotImplementedError


class FakeCareerProfileRepository:
    def __init__(self) -> None:
        self.profiles: dict[uuid.UUID, CareerProfile] = {}

    async def create(self, profile: CareerProfile) -> CareerProfile:
        self.profiles[profile.id] = profile
        return replace(profile)

    async def get_by_user_id(
        self,
        tenant_id: uuid.UUID,
        user_id: uuid.UUID,
        target_role_id: uuid.UUID | None = None,
    ) -> CareerProfile | None:
        for profile in self.profiles.values():
            if (
                profile.tenant_id == tenant_id
                and profile.user_id == user_id
                and profile.target_role_id == target_role_id
            ):
                return replace(profile)
        return None

    async def get_by_id(self, tenant_id: uuid.UUID, profile_id: uuid.UUID) -> CareerProfile | None:
        profile = self.profiles.get(profile_id)
        return replace(profile) if profile and profile.tenant_id == tenant_id else None

    async def update(self, profile: CareerProfile) -> CareerProfile:
        self.profiles[profile.id] = replace(profile)
        return replace(profile)


class FakeCareerProfileVersionRepository:
    def __init__(self) -> None:
        self.versions: list[CareerProfileVersion] = []

    async def create(self, version: CareerProfileVersion) -> CareerProfileVersion:
        self.versions.append(version)
        return version

    async def list_for_profile(
        self, career_profile_id: uuid.UUID, *, limit: int = 50
    ) -> list[CareerProfileVersion]:
        return [v for v in self.versions if v.career_profile_id == career_profile_id][:limit]


class FakeExperienceRepository:
    def __init__(self) -> None:
        self.experiences: dict[uuid.UUID, Experience] = {}

    async def create(self, experience: Experience) -> Experience:
        experience = replace(experience, display_order=len(self.experiences) + 1)
        self.experiences[experience.id] = experience
        return replace(experience)

    async def get_by_id(self, tenant_id: uuid.UUID, experience_id: uuid.UUID) -> Experience | None:
        e = self.experiences.get(experience_id)
        return replace(e) if e and e.tenant_id == tenant_id else None

    async def list_for_profile(
        self, tenant_id: uuid.UUID, career_profile_id: uuid.UUID
    ) -> list[Experience]:
        return [
            replace(e)
            for e in self.experiences.values()
            if e.tenant_id == tenant_id and e.career_profile_id == career_profile_id
        ]

    async def update(self, experience: Experience) -> Experience:
        self.experiences[experience.id] = replace(experience)
        return replace(experience)

    async def soft_delete(self, tenant_id: uuid.UUID, experience_id: uuid.UUID) -> None:
        raise NotImplementedError

    async def move(self, tenant_id: uuid.UUID, experience_id: uuid.UUID, direction: str) -> None:
        raise NotImplementedError


class FakeEducationRepository:
    def __init__(self) -> None:
        self.educations: dict[uuid.UUID, Education] = {}

    async def create(self, education: Education) -> Education:
        education = replace(education, display_order=len(self.educations) + 1)
        self.educations[education.id] = education
        return replace(education)

    async def get_by_id(self, tenant_id: uuid.UUID, education_id: uuid.UUID) -> Education | None:
        e = self.educations.get(education_id)
        return replace(e) if e and e.tenant_id == tenant_id else None

    async def list_for_profile(
        self, tenant_id: uuid.UUID, career_profile_id: uuid.UUID
    ) -> list[Education]:
        return [
            replace(e)
            for e in self.educations.values()
            if e.tenant_id == tenant_id and e.career_profile_id == career_profile_id
        ]

    async def update(self, education: Education) -> Education:
        self.educations[education.id] = replace(education)
        return replace(education)

    async def soft_delete(self, tenant_id: uuid.UUID, education_id: uuid.UUID) -> None:
        raise NotImplementedError

    async def move(self, tenant_id: uuid.UUID, education_id: uuid.UUID, direction: str) -> None:
        raise NotImplementedError


class FakeCertificationRepository:
    def __init__(self) -> None:
        self.certifications: dict[uuid.UUID, Certification] = {}

    async def create(self, certification: Certification) -> Certification:
        certification = replace(certification, display_order=len(self.certifications) + 1)
        self.certifications[certification.id] = certification
        return replace(certification)

    async def get_by_id(
        self, tenant_id: uuid.UUID, certification_id: uuid.UUID
    ) -> Certification | None:
        c = self.certifications.get(certification_id)
        return replace(c) if c and c.tenant_id == tenant_id else None

    async def list_for_profile(
        self, tenant_id: uuid.UUID, career_profile_id: uuid.UUID
    ) -> list[Certification]:
        return [
            replace(c)
            for c in self.certifications.values()
            if c.tenant_id == tenant_id and c.career_profile_id == career_profile_id
        ]

    async def update(self, certification: Certification) -> Certification:
        self.certifications[certification.id] = replace(certification)
        return replace(certification)

    async def soft_delete(self, tenant_id: uuid.UUID, certification_id: uuid.UUID) -> None:
        raise NotImplementedError

    async def move(
        self, tenant_id: uuid.UUID, certification_id: uuid.UUID, direction: str
    ) -> None:
        raise NotImplementedError


class FakeCareerHighlightRepository:
    def __init__(self) -> None:
        self.highlights: dict[uuid.UUID, CareerHighlight] = {}

    async def create(self, highlight: CareerHighlight) -> CareerHighlight:
        highlight = replace(highlight, display_order=len(self.highlights) + 1)
        self.highlights[highlight.id] = highlight
        return replace(highlight)

    async def get_by_id(
        self, tenant_id: uuid.UUID, highlight_id: uuid.UUID
    ) -> CareerHighlight | None:
        h = self.highlights.get(highlight_id)
        return replace(h) if h and h.tenant_id == tenant_id else None

    async def list_for_profile(
        self, tenant_id: uuid.UUID, career_profile_id: uuid.UUID
    ) -> list[CareerHighlight]:
        return [
            replace(h)
            for h in self.highlights.values()
            if h.tenant_id == tenant_id and h.career_profile_id == career_profile_id
        ]

    async def update(self, highlight: CareerHighlight) -> CareerHighlight:
        self.highlights[highlight.id] = replace(highlight)
        return replace(highlight)

    async def soft_delete(self, tenant_id: uuid.UUID, highlight_id: uuid.UUID) -> None:
        raise NotImplementedError

    async def move(self, tenant_id: uuid.UUID, highlight_id: uuid.UUID, direction: str) -> None:
        raise NotImplementedError


class FakeKeyAchievementRepository:
    def __init__(self) -> None:
        self.achievements: dict[uuid.UUID, KeyAchievement] = {}

    async def create(self, achievement: KeyAchievement) -> KeyAchievement:
        achievement = replace(achievement, display_order=len(self.achievements) + 1)
        self.achievements[achievement.id] = achievement
        return replace(achievement)

    async def get_by_id(
        self, tenant_id: uuid.UUID, achievement_id: uuid.UUID
    ) -> KeyAchievement | None:
        a = self.achievements.get(achievement_id)
        return replace(a) if a and a.tenant_id == tenant_id else None

    async def list_for_profile(
        self, tenant_id: uuid.UUID, career_profile_id: uuid.UUID
    ) -> list[KeyAchievement]:
        return [
            replace(a)
            for a in self.achievements.values()
            if a.tenant_id == tenant_id and a.career_profile_id == career_profile_id
        ]

    async def update(self, achievement: KeyAchievement) -> KeyAchievement:
        self.achievements[achievement.id] = replace(achievement)
        return replace(achievement)

    async def soft_delete(self, tenant_id: uuid.UUID, achievement_id: uuid.UUID) -> None:
        raise NotImplementedError

    async def move(self, tenant_id: uuid.UUID, achievement_id: uuid.UUID, direction: str) -> None:
        raise NotImplementedError


@pytest.fixture
def setup():
    resumes = FakeResumeRepository()
    career_profiles = CareerProfileService(
        FakeCareerProfileRepository(), FakeCareerProfileVersionRepository()
    )
    experiences = ExperienceService(FakeExperienceRepository(), career_profiles)
    educations = EducationService(FakeEducationRepository(), career_profiles)
    certifications = CertificationService(FakeCertificationRepository(), career_profiles)
    career_highlights = CareerHighlightService(FakeCareerHighlightRepository(), career_profiles)
    key_achievements = KeyAchievementService(FakeKeyAchievementRepository(), career_profiles)
    merge_service = ResumeMergeService(
        resumes,
        experiences,
        educations,
        certifications,
        career_highlights,
        key_achievements,
        career_profiles,
    )
    return (
        merge_service,
        resumes,
        experiences,
        educations,
        certifications,
        career_highlights,
        key_achievements,
        career_profiles,
    )


def _make_resume(tenant_id: uuid.UUID, user_id: uuid.UUID, *, status: str = "parsed") -> Resume:
    now = datetime.now(UTC)
    return Resume(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        user_id=user_id,
        original_filename="resume.pdf",
        file_key="resumes/x/y/z.pdf",
        content_type="application/pdf",
        file_size_bytes=100,
        status=status,
        raw_text="raw text",
        extracted_data=EXTRACTED_DATA if status == "parsed" else None,
        error_message=None,
        created_at=now,
        updated_at=now,
    )


@pytest.mark.unit
class TestMerge:
    async def test_only_accepted_items_are_written_to_the_profile(self, setup) -> None:
        (
            merge_service,
            resumes,
            experiences,
            educations,
            certifications,
            _career_highlights,
            _key_achievements,
            career_profiles,
        ) = setup
        tenant_id, user_id = uuid.uuid4(), uuid.uuid4()
        resume = await resumes.create(_make_resume(tenant_id, user_id))

        result = await merge_service.merge(
            tenant_id=tenant_id,
            user_id=user_id,
            resume_id=resume.id,
            target_role_id=None,
            accept_headline=False,
            accept_summary=True,
            accepted_skill_indices=[0],
            accepted_experience_indices=[0],
            accepted_education_indices=[],
            accepted_certification_indices=[],
            accepted_career_highlight_indices=[],
            accepted_key_achievement_indices=[],
        )

        assert result.added_experience_count == 1
        assert result.added_education_count == 0
        assert result.added_certification_count == 0
        assert result.added_skills_count == 1
        assert result.updated_headline is False
        assert result.updated_summary is True

        profile = await career_profiles.get_or_create(tenant_id=tenant_id, user_id=user_id)
        assert profile.headline is None
        assert profile.summary == "Backend engineer with 8 years of experience."
        assert profile.core_competencies == [CoreCompetency(name="Python", category=None)]

        added_experiences = await experiences.list_for_current_user(
            tenant_id=tenant_id, user_id=user_id
        )
        assert len(added_experiences) == 1
        assert added_experiences[0].company == "Initech"

        assert await educations.list_for_current_user(tenant_id=tenant_id, user_id=user_id) == []
        assert (
            await certifications.list_for_current_user(tenant_id=tenant_id, user_id=user_id) == []
        )

    async def test_accepting_everything_adds_everything(self, setup) -> None:
        merge_service, resumes, experiences, educations, certifications, *_ = setup
        tenant_id, user_id = uuid.uuid4(), uuid.uuid4()
        resume = await resumes.create(_make_resume(tenant_id, user_id))

        result = await merge_service.merge(
            tenant_id=tenant_id,
            user_id=user_id,
            resume_id=resume.id,
            target_role_id=None,
            accept_headline=True,
            accept_summary=True,
            accepted_skill_indices=[0, 1],
            accepted_experience_indices=[0, 1],
            accepted_education_indices=[0],
            accepted_certification_indices=[0],
            accepted_career_highlight_indices=[0],
            accepted_key_achievement_indices=[0],
        )

        assert result.added_experience_count == 2
        assert result.added_education_count == 1
        assert result.added_certification_count == 1
        assert result.added_skills_count == 2
        assert result.added_career_highlight_count == 1
        assert result.added_key_achievement_count == 1

    async def test_skills_already_on_the_profile_are_not_duplicated(self, setup) -> None:
        merge_service, resumes, _, _, _, _, _, career_profiles = setup
        tenant_id, user_id = uuid.uuid4(), uuid.uuid4()
        await career_profiles.update(
            tenant_id=tenant_id, user_id=user_id, headline=None, summary=None,
            core_competencies=[CoreCompetency(name="python")],  # already present, different case
        )
        resume = await resumes.create(_make_resume(tenant_id, user_id))

        result = await merge_service.merge(
            tenant_id=tenant_id,
            user_id=user_id,
            resume_id=resume.id,
            target_role_id=None,
            accept_headline=False,
            accept_summary=False,
            accepted_skill_indices=[0, 1],
            accepted_experience_indices=[],
            accepted_education_indices=[],
            accepted_certification_indices=[],
            accepted_career_highlight_indices=[],
            accepted_key_achievement_indices=[],
        )

        assert result.added_skills_count == 1  # only AWS is new
        profile = await career_profiles.get_or_create(tenant_id=tenant_id, user_id=user_id)
        assert profile.core_competencies == [
            CoreCompetency(name="python"),
            CoreCompetency(name="AWS", category="Cloud"),
        ]

    async def test_merging_a_foreign_users_resume_raises_not_found(self, setup) -> None:
        merge_service, resumes, *_ = setup
        tenant_id = uuid.uuid4()
        owner, intruder = uuid.uuid4(), uuid.uuid4()
        resume = await resumes.create(_make_resume(tenant_id, owner))

        with pytest.raises(CareerCompassError) as exc_info:
            await merge_service.merge(
                tenant_id=tenant_id,
                user_id=intruder,
                resume_id=resume.id,
                target_role_id=None,
                accept_headline=False,
                accept_summary=False,
                accepted_skill_indices=[],
                accepted_experience_indices=[],
                accepted_education_indices=[],
                accepted_certification_indices=[],
                accepted_career_highlight_indices=[],
                accepted_key_achievement_indices=[],
            )
        assert exc_info.value.code == "RESUME_NOT_FOUND"

    async def test_merging_a_failed_resume_raises_validation_error(self, setup) -> None:
        merge_service, resumes, *_ = setup
        tenant_id, user_id = uuid.uuid4(), uuid.uuid4()
        resume = await resumes.create(_make_resume(tenant_id, user_id, status="failed"))

        with pytest.raises(CareerCompassError) as exc_info:
            await merge_service.merge(
                tenant_id=tenant_id,
                user_id=user_id,
                resume_id=resume.id,
                target_role_id=None,
                accept_headline=False,
                accept_summary=False,
                accepted_skill_indices=[],
                accepted_experience_indices=[],
                accepted_education_indices=[],
                accepted_certification_indices=[],
                accepted_career_highlight_indices=[],
                accepted_key_achievement_indices=[],
            )
        assert exc_info.value.code == "RESUME_NOT_PARSED"

    async def test_out_of_range_indices_are_silently_ignored(self, setup) -> None:
        merge_service, resumes, experiences, *_ = setup
        tenant_id, user_id = uuid.uuid4(), uuid.uuid4()
        resume = await resumes.create(_make_resume(tenant_id, user_id))

        result = await merge_service.merge(
            tenant_id=tenant_id,
            user_id=user_id,
            resume_id=resume.id,
            target_role_id=None,
            accept_headline=False,
            accept_summary=False,
            accepted_skill_indices=[],
            accepted_experience_indices=[99],
            accepted_education_indices=[],
            accepted_certification_indices=[],
            accepted_career_highlight_indices=[],
            accepted_key_achievement_indices=[],
        )

        assert result.added_experience_count == 0
        assert await experiences.list_for_current_user(tenant_id=tenant_id, user_id=user_id) == []

    async def test_an_experience_item_missing_a_start_date_is_skipped_not_fatal(
        self, setup
    ) -> None:
        """Real bug caught live: one accepted experience entry lacking a
        usable start date used to raise and abort the *entire* merge,
        silently dropping skills/education/certifications the user also
        selected in the same request. It should only skip that one item.
        """
        (
            merge_service,
            resumes,
            experiences,
            educations,
            certifications,
            _career_highlights,
            _key_achievements,
            career_profiles,
        ) = setup
        tenant_id, user_id = uuid.uuid4(), uuid.uuid4()
        data_with_missing_date: dict[str, object] = {
            **EXTRACTED_DATA,
            "experience": [
                EXTRACTED_DATA["experience"][0],
                {**EXTRACTED_DATA["experience"][1], "start_date": None},
            ],
        }
        base_resume = _make_resume(tenant_id, user_id)
        resume = await resumes.create(replace(base_resume, extracted_data=data_with_missing_date))

        result = await merge_service.merge(
            tenant_id=tenant_id,
            user_id=user_id,
            resume_id=resume.id,
            target_role_id=None,
            accept_headline=True,
            accept_summary=True,
            accepted_skill_indices=[0],
            accepted_experience_indices=[0, 1],
            accepted_education_indices=[0],
            accepted_certification_indices=[0],
            accepted_career_highlight_indices=[0],
            accepted_key_achievement_indices=[0],
        )

        assert result.added_experience_count == 1  # only the Initech entry
        assert result.skipped_experience_titles == ["Software Engineer"]
        # Everything else in the same request still went through.
        assert result.added_education_count == 1
        assert result.added_certification_count == 1
        assert result.added_skills_count == 1
        assert result.updated_headline is True

        added_experiences = await experiences.list_for_current_user(
            tenant_id=tenant_id, user_id=user_id
        )
        assert [e.company for e in added_experiences] == ["Initech"]

    async def test_accepted_career_highlights_are_added(self, setup) -> None:
        merge_service, resumes, _, _, _, career_highlights, _, _ = setup
        tenant_id, user_id = uuid.uuid4(), uuid.uuid4()
        resume = await resumes.create(_make_resume(tenant_id, user_id))

        result = await merge_service.merge(
            tenant_id=tenant_id,
            user_id=user_id,
            resume_id=resume.id,
            target_role_id=None,
            accept_headline=False,
            accept_summary=False,
            accepted_skill_indices=[],
            accepted_experience_indices=[],
            accepted_education_indices=[],
            accepted_certification_indices=[],
            accepted_career_highlight_indices=[0],
            accepted_key_achievement_indices=[],
        )

        assert result.added_career_highlight_count == 1
        added = await career_highlights.list_for_current_user(tenant_id=tenant_id, user_id=user_id)
        assert len(added) == 1
        assert added[0].company == "Initech"

    async def test_accepted_key_achievements_are_added(self, setup) -> None:
        merge_service, resumes, _, _, _, _, key_achievements, _ = setup
        tenant_id, user_id = uuid.uuid4(), uuid.uuid4()
        resume = await resumes.create(_make_resume(tenant_id, user_id))

        result = await merge_service.merge(
            tenant_id=tenant_id,
            user_id=user_id,
            resume_id=resume.id,
            target_role_id=None,
            accept_headline=False,
            accept_summary=False,
            accepted_skill_indices=[],
            accepted_experience_indices=[],
            accepted_education_indices=[],
            accepted_certification_indices=[],
            accepted_career_highlight_indices=[],
            accepted_key_achievement_indices=[0],
        )

        assert result.added_key_achievement_count == 1
        added = await key_achievements.list_for_current_user(tenant_id=tenant_id, user_id=user_id)
        assert len(added) == 1
        assert added[0].company == "Initech"
