"""Resume merge application service.

Takes the per-item accept/reject decisions the user made on the review
screen and writes only the accepted items into the existing Career
Profile — reusing ExperienceService.add()/EducationService.add()/
CertificationService.add()/CareerProfileService.update() exactly as
every other caller of those services does, rather than duplicating any
profile-mutation logic here. Nothing is written to the profile until
this call succeeds; uploading/parsing a resume never touches the
profile on its own.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from uuid import UUID

from app.application.career_profile.career_highlight_service import CareerHighlightService
from app.application.career_profile.career_profile_service import CareerProfileService
from app.application.career_profile.certification_service import CertificationService
from app.application.career_profile.education_service import EducationService
from app.application.career_profile.experience_service import ExperienceService
from app.application.career_profile.key_achievement_service import KeyAchievementService
from app.core.exceptions import NotFoundError, ValidationError
from app.domain.career_profile.entities import CoreCompetency
from app.domain.resume_intelligence.repositories import ResumeRepository


@dataclass(slots=True)
class ResumeMergeResult:
    added_experience_count: int
    added_education_count: int
    added_certification_count: int
    added_skills_count: int
    added_career_highlight_count: int
    added_key_achievement_count: int
    updated_headline: bool
    updated_summary: bool
    # Titles of accepted experience entries that couldn't be added because
    # no usable start date was extracted for them (Experience.start_date
    # is a required field) — everything else in the same merge request
    # still goes through. See merge()'s experience loop.
    skipped_experience_titles: list[str]


def _parse_date(value: object) -> date | None:
    """Never raises — an unparseable or missing date is treated the same
    as "no date given" rather than aborting the caller. By the time this
    runs, ResumeExtractionService has already normalized every date
    string to strict ISO or None (see _clean_date there), so a genuinely
    malformed string here would only come from data extracted before
    that fix shipped; treating it as missing rather than fatal is the
    safer default either way — a single item's bad data has no business
    blocking every other accepted item in the same merge.
    """
    if not isinstance(value, str):
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


class ResumeMergeService:
    def __init__(
        self,
        resumes: ResumeRepository,
        experiences: ExperienceService,
        educations: EducationService,
        certifications: CertificationService,
        career_highlights: CareerHighlightService,
        key_achievements: KeyAchievementService,
        career_profiles: CareerProfileService,
    ) -> None:
        self._resumes = resumes
        self._experiences = experiences
        self._educations = educations
        self._certifications = certifications
        self._career_highlights = career_highlights
        self._key_achievements = key_achievements
        self._career_profiles = career_profiles

    async def merge(
        self,
        *,
        tenant_id: UUID,
        user_id: UUID,
        resume_id: UUID,
        accept_headline: bool,
        accept_summary: bool,
        accepted_skill_indices: list[int],
        accepted_experience_indices: list[int],
        accepted_education_indices: list[int],
        accepted_certification_indices: list[int],
        accepted_career_highlight_indices: list[int],
        accepted_key_achievement_indices: list[int],
    ) -> ResumeMergeResult:
        resume = await self._resumes.get_by_id(tenant_id, resume_id)
        if resume is None or resume.user_id != user_id:
            raise NotFoundError("Resume not found.", code="RESUME_NOT_FOUND")
        if resume.status != "parsed" or resume.extracted_data is None:
            raise ValidationError(
                "This resume has no extracted data to merge.", code="RESUME_NOT_PARSED"
            )

        # The resume's own tag (set once, at upload time) determines the
        # destination profile — None merges into Master, a real id merges
        # into that Target Role Profile. Not a client-supplied field:
        # the whole point is that a resume tagged to a role at upload
        # can't be redirected to a different profile at merge time.
        target_role_id = resume.target_role_id

        data = resume.extracted_data
        skill_items = data.get("skills") or []
        experience_items = data.get("experience") or []
        education_items = data.get("education") or []
        certification_items = data.get("certifications") or []
        career_highlight_items = data.get("career_highlights") or []
        key_achievement_items = data.get("key_achievements") or []
        assert isinstance(skill_items, list)
        assert isinstance(experience_items, list)
        assert isinstance(education_items, list)
        assert isinstance(certification_items, list)
        assert isinstance(career_highlight_items, list)
        assert isinstance(key_achievement_items, list)

        # Every section below is deduped against what's already on the
        # profile before adding anything — the same rule the skills merge
        # further down already applied. Without this, re-merging a resume
        # that was already (fully or partially) merged before (a
        # realistic scenario: the same resume re-uploaded after a quality
        # fix, or two resume versions sharing content) silently appends
        # the exact same entry again as a brand new row rather than
        # recognizing it's already there — a real bug found live across
        # Career Highlights and Education, and fixed the same way in
        # Experience/Certifications too rather than waiting for it to
        # surface separately in each.
        existing_experiences = await self._experiences.list_for_current_user(
            tenant_id=tenant_id, user_id=user_id, target_role_id=target_role_id
        )
        existing_experience_keys = {
            (e.title.strip().lower(), e.company.strip().lower(), e.start_date)
            for e in existing_experiences
        }
        existing_educations = await self._educations.list_for_current_user(
            tenant_id=tenant_id, user_id=user_id, target_role_id=target_role_id
        )
        existing_education_keys = {
            (e.institution.strip().lower(), (e.degree or "").strip().lower())
            for e in existing_educations
        }
        existing_certifications = await self._certifications.list_for_current_user(
            tenant_id=tenant_id, user_id=user_id, target_role_id=target_role_id
        )
        existing_certification_names = {c.name.strip().lower() for c in existing_certifications}
        existing_highlights = await self._career_highlights.list_for_current_user(
            tenant_id=tenant_id, user_id=user_id, target_role_id=target_role_id
        )
        existing_highlight_titles = {h.title.strip().lower() for h in existing_highlights}
        existing_achievements = await self._key_achievements.list_for_current_user(
            tenant_id=tenant_id, user_id=user_id, target_role_id=target_role_id
        )
        existing_achievement_titles = {a.title.strip().lower() for a in existing_achievements}

        added_experience = 0
        skipped_experience_titles: list[str] = []
        for idx in accepted_experience_indices:
            if idx < 0 or idx >= len(experience_items):
                continue
            item = experience_items[idx]
            start_date = _parse_date(item.get("start_date"))
            if start_date is None:
                # Experience.start_date is a required domain field — this
                # one item can't be added, but that's no reason to also
                # drop every other accepted item in the same request (the
                # original all-or-nothing behavior here was a real bug:
                # one item missing a date silently blocked skills,
                # education, and certifications the user also selected).
                skipped_experience_titles.append(str(item.get("title") or f"Item {idx + 1}"))
                continue
            title = str(item.get("title", ""))
            company = str(item.get("company", ""))
            experience_key = (title.strip().lower(), company.strip().lower(), start_date)
            if experience_key in existing_experience_keys:
                continue
            await self._experiences.add(
                tenant_id=tenant_id,
                user_id=user_id,
                title=title,
                company=company,
                location=item.get("location"),
                start_date=start_date,
                end_date=_parse_date(item.get("end_date")),
                description=item.get("description"),
                target_role_id=target_role_id,
            )
            existing_experience_keys.add(experience_key)
            added_experience += 1

        added_education = 0
        for idx in accepted_education_indices:
            if idx < 0 or idx >= len(education_items):
                continue
            item = education_items[idx]
            institution = str(item.get("institution", ""))
            degree = item.get("degree")
            education_key = (institution.strip().lower(), str(degree or "").strip().lower())
            if education_key in existing_education_keys:
                continue
            await self._educations.add(
                tenant_id=tenant_id,
                user_id=user_id,
                institution=institution,
                degree=degree,
                field_of_study=item.get("field_of_study"),
                start_date=_parse_date(item.get("start_date")),
                end_date=_parse_date(item.get("end_date")),
                description=item.get("description"),
                target_role_id=target_role_id,
            )
            existing_education_keys.add(education_key)
            added_education += 1

        added_certifications = 0
        for idx in accepted_certification_indices:
            if idx < 0 or idx >= len(certification_items):
                continue
            item = certification_items[idx]
            name = str(item.get("name", ""))
            if name.strip().lower() in existing_certification_names:
                continue
            await self._certifications.add(
                tenant_id=tenant_id,
                user_id=user_id,
                name=name,
                issuing_organization=item.get("issuing_organization", ""),
                issue_date=_parse_date(item.get("issue_date")),
                expiration_date=_parse_date(item.get("expiration_date")),
                credential_id=item.get("credential_id"),
                credential_url=item.get("credential_url"),
                target_role_id=target_role_id,
            )
            existing_certification_names.add(name.strip().lower())
            added_certifications += 1

        added_career_highlights = 0
        for idx in accepted_career_highlight_indices:
            if idx < 0 or idx >= len(career_highlight_items):
                continue
            item = career_highlight_items[idx]
            title = str(item.get("title", ""))
            if title.strip().lower() in existing_highlight_titles:
                continue
            await self._career_highlights.add(
                tenant_id=tenant_id,
                user_id=user_id,
                title=title,
                company=item.get("company"),
                description=item.get("description"),
                occurred_on=_parse_date(item.get("occurred_on")),
                target_role_id=target_role_id,
            )
            existing_highlight_titles.add(title.strip().lower())
            added_career_highlights += 1

        added_key_achievements = 0
        for idx in accepted_key_achievement_indices:
            if idx < 0 or idx >= len(key_achievement_items):
                continue
            item = key_achievement_items[idx]
            title = str(item.get("title", ""))
            if title.strip().lower() in existing_achievement_titles:
                continue
            await self._key_achievements.add(
                tenant_id=tenant_id,
                user_id=user_id,
                title=title,
                company=item.get("company"),
                description=item.get("description"),
                occurred_on=_parse_date(item.get("occurred_on")),
                target_role_id=target_role_id,
            )
            existing_achievement_titles.add(title.strip().lower())
            added_key_achievements += 1

        profile = await self._career_profiles.get_or_create(
            tenant_id=tenant_id, user_id=user_id, target_role_id=target_role_id
        )
        existing_lower = {c.name.lower() for c in profile.core_competencies}
        seen: set[str] = set()
        new_skills: list[CoreCompetency] = []
        for idx in accepted_skill_indices:
            if idx < 0 or idx >= len(skill_items):
                continue
            item = skill_items[idx]
            trimmed = str(item.get("name", "")).strip()
            key = trimmed.lower()
            if trimmed and key not in existing_lower and key not in seen:
                seen.add(key)
                category = item.get("category")
                new_skills.append(
                    CoreCompetency(
                        name=trimmed,
                        category=category.strip() if isinstance(category, str) and category.strip() else None,
                    )
                )

        headline_raw = data.get("headline")
        summary_raw = data.get("summary")
        extracted_headline = headline_raw if isinstance(headline_raw, str) else None
        extracted_summary = summary_raw if isinstance(summary_raw, str) else None
        updated_headline = accept_headline and bool(extracted_headline)
        updated_summary = accept_summary and bool(extracted_summary)

        if updated_headline or updated_summary or new_skills:
            await self._career_profiles.update(
                tenant_id=tenant_id,
                user_id=user_id,
                headline=extracted_headline if updated_headline else profile.headline,
                summary=extracted_summary if updated_summary else profile.summary,
                core_competencies=(
                    [*profile.core_competencies, *new_skills] if new_skills else None
                ),
                section_order=profile.section_order,
                target_role_id=target_role_id,
            )

        return ResumeMergeResult(
            added_experience_count=added_experience,
            added_education_count=added_education,
            added_certification_count=added_certifications,
            added_skills_count=len(new_skills),
            added_career_highlight_count=added_career_highlights,
            added_key_achievement_count=added_key_achievements,
            updated_headline=updated_headline,
            updated_summary=updated_summary,
            skipped_experience_titles=skipped_experience_titles,
        )
