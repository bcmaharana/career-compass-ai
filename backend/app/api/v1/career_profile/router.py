"""Career Profile API routes.

Thin per backend-architecture.md: parse input, call one application
service, map the result to a response schema. Every route depends on
get_current_identity (or, per convention, get_tenant_scoped_session
transitively via the service dependencies) — self-service data, no extra
RBAC permission required, since a user always manages their own profile.

Every reorderable entity gets a POST .../{id}/move endpoint accepting
{"direction": "up"|"down"} — see app/adapters/db/reorder.py for the
shared swap logic and MoveRequest in schemas.py for the request shape.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query, UploadFile, status

from app.api.dependencies import (
    get_career_goal_service,
    get_career_highlight_service,
    get_career_profile_service,
    get_career_profile_summary_service,
    get_certification_service,
    get_clear_career_profile_service,
    get_current_identity,
    get_education_service,
    get_experience_service,
    get_key_achievement_service,
    get_peer_endorsement_service,
    get_resume_export_service,
    get_target_role_service,
)
from app.api.v1.career_profile.schemas import (
    AddRequiredSkillRequest,
    CareerGoalRequest,
    CareerGoalResponse,
    CareerGoalUpdateRequest,
    CareerHighlightRequest,
    CareerHighlightResponse,
    CareerProfileResponse,
    CareerProfileSummaryResponse,
    CertificationRequest,
    CertificationResponse,
    CoreCompetencyPayload,
    EducationRequest,
    EducationResponse,
    ExperienceRequest,
    ExperienceResponse,
    GenerateResumeRequest,
    KeyAchievementRequest,
    KeyAchievementResponse,
    MoveRequest,
    PeerEndorsementRequest,
    PeerEndorsementResponse,
    PhotoUploadResponse,
    TargetRoleRequest,
    TargetRoleResponse,
    UpdateCareerProfileRequest,
)
from app.application.career_profile.career_goal_service import CareerGoalService
from app.application.career_profile.career_highlight_service import CareerHighlightService
from app.application.career_profile.career_profile_service import CareerProfileService
from app.application.career_profile.career_profile_summary_service import (
    CareerProfileSummaryService,
)
from app.application.career_profile.certification_service import CertificationService
from app.application.career_profile.clear_profile_service import ClearCareerProfileService
from app.application.career_profile.education_service import EducationService
from app.application.career_profile.experience_service import ExperienceService
from app.application.career_profile.key_achievement_service import KeyAchievementService
from app.application.career_profile.peer_endorsement_service import PeerEndorsementService
from app.application.career_profile.resume_export_service import (
    ResumeDownloadUrls,
    ResumeExportService,
)
from app.application.career_profile.target_role_service import TargetRoleService
from app.core.identity_provider_interface import IdentityClaims
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
    TargetRole,
)


def _core_competency_response(competency: CoreCompetency) -> CoreCompetencyPayload:
    return CoreCompetencyPayload(
        name=competency.name,
        category=competency.category,
        include_in_resume=competency.include_in_resume,
    )


def _profile_response(
    profile: CareerProfile, download_urls: ResumeDownloadUrls
) -> CareerProfileResponse:
    return CareerProfileResponse(
        id=profile.id,
        current_version=profile.current_version,
        headline=profile.headline,
        summary=profile.summary,
        career_readiness_score=profile.career_readiness_score,
        photo_url=profile.photo_url,
        core_competencies=[_core_competency_response(c) for c in profile.core_competencies],
        section_order=profile.section_order,
        resume_docx_url=download_urls.docx_url,
        resume_pdf_url=download_urls.pdf_url,
        resume_generated_at=profile.resume_generated_at,
        resume_section_toggles=profile.resume_section_toggles,
    )

router = APIRouter(tags=["career-profile"])


@router.get("/career-profile", response_model=CareerProfileResponse)
async def get_career_profile(
    target_role_id: UUID | None = Query(default=None),
    identity: IdentityClaims = Depends(get_current_identity),
    service: CareerProfileService = Depends(get_career_profile_service),
    resume_export: ResumeExportService = Depends(get_resume_export_service),
) -> CareerProfileResponse:
    profile = await service.get_or_create(
        tenant_id=UUID(identity.tenant_id),
        user_id=UUID(identity.user_id),
        target_role_id=target_role_id,
    )
    download_urls = await resume_export.get_download_urls(
        tenant_id=UUID(identity.tenant_id), profile=profile
    )
    return _profile_response(profile, download_urls)


@router.patch("/career-profile", response_model=CareerProfileResponse)
async def update_career_profile(
    request: UpdateCareerProfileRequest,
    target_role_id: UUID | None = Query(default=None),
    identity: IdentityClaims = Depends(get_current_identity),
    service: CareerProfileService = Depends(get_career_profile_service),
    resume_export: ResumeExportService = Depends(get_resume_export_service),
) -> CareerProfileResponse:
    profile = await service.update(
        tenant_id=UUID(identity.tenant_id),
        user_id=UUID(identity.user_id),
        headline=request.headline,
        summary=request.summary,
        core_competencies=(
            [
                CoreCompetency(
                    name=c.name, category=c.category, include_in_resume=c.include_in_resume
                )
                for c in request.core_competencies
            ]
            if request.core_competencies is not None
            else None
        ),
        section_order=request.section_order,
        resume_section_toggles=request.resume_section_toggles,
        target_role_id=target_role_id,
    )
    download_urls = await resume_export.get_download_urls(
        tenant_id=UUID(identity.tenant_id), profile=profile
    )
    return _profile_response(profile, download_urls)


@router.post("/career-profile/resume-export", response_model=CareerProfileResponse)
async def generate_resume(
    request: GenerateResumeRequest,
    target_role_id: UUID | None = Query(default=None),
    identity: IdentityClaims = Depends(get_current_identity),
    resume_export: ResumeExportService = Depends(get_resume_export_service),
) -> CareerProfileResponse:
    profile, _immediate_url = await resume_export.generate(
        tenant_id=UUID(identity.tenant_id),
        user_id=UUID(identity.user_id),
        target_role_id=target_role_id,
        format=request.format,
    )
    # A second presigned-URL round trip (get_download_urls, right after
    # generate() already returned one) rather than reusing
    # _immediate_url directly — keeps this response identical in shape
    # to GET/PATCH's (both resume_docx_url and resume_pdf_url populated
    # together, not just the one just-generated format), so the
    # frontend has one response shape to reason about everywhere,
    # not a special case for this endpoint.
    download_urls = await resume_export.get_download_urls(
        tenant_id=UUID(identity.tenant_id), profile=profile
    )
    return _profile_response(profile, download_urls)


@router.delete("/career-profile", status_code=status.HTTP_204_NO_CONTENT)
async def clear_career_profile(
    target_role_id: UUID | None = Query(default=None),
    identity: IdentityClaims = Depends(get_current_identity),
    service: ClearCareerProfileService = Depends(get_clear_career_profile_service),
) -> None:
    await service.clear_all(
        tenant_id=UUID(identity.tenant_id),
        user_id=UUID(identity.user_id),
        target_role_id=target_role_id,
    )


@router.get("/career-profile/summary", response_model=CareerProfileSummaryResponse)
async def get_career_profile_summary(
    target_role_id: UUID | None = Query(default=None),
    identity: IdentityClaims = Depends(get_current_identity),
    service: CareerProfileSummaryService = Depends(get_career_profile_summary_service),
) -> CareerProfileSummaryResponse:
    summary = await service.get_summary(
        tenant_id=UUID(identity.tenant_id),
        user_id=UUID(identity.user_id),
        target_role_id=target_role_id,
    )
    return CareerProfileSummaryResponse(
        experience_count=summary.experience_count,
        education_count=summary.education_count,
        certification_count=summary.certification_count,
        career_highlight_count=summary.career_highlight_count,
        key_achievement_count=summary.key_achievement_count,
        competency_count=summary.competency_count,
        has_headline=summary.has_headline,
        has_summary=summary.has_summary,
        has_any_data=summary.has_any_data,
    )


@router.post("/career-profile/photo", response_model=PhotoUploadResponse)
async def upload_profile_photo(
    file: UploadFile,
    identity: IdentityClaims = Depends(get_current_identity),
    service: CareerProfileService = Depends(get_career_profile_service),
) -> PhotoUploadResponse:
    content = await file.read()
    profile = await service.upload_photo(
        tenant_id=UUID(identity.tenant_id),
        user_id=UUID(identity.user_id),
        content=content,
        content_type=file.content_type or "application/octet-stream",
    )
    assert profile.photo_url is not None  # set by upload_photo on success
    return PhotoUploadResponse(photo_url=profile.photo_url)


@router.delete("/career-profile/photo", status_code=status.HTTP_204_NO_CONTENT)
async def delete_profile_photo(
    identity: IdentityClaims = Depends(get_current_identity),
    service: CareerProfileService = Depends(get_career_profile_service),
) -> None:
    await service.delete_photo(tenant_id=UUID(identity.tenant_id), user_id=UUID(identity.user_id))


def _experience_response(experience: Experience) -> ExperienceResponse:
    return ExperienceResponse(
        id=experience.id,
        title=experience.title,
        company=experience.company,
        location=experience.location,
        start_date=experience.start_date,
        end_date=experience.end_date,
        description=experience.description,
        display_order=experience.display_order,
        include_in_resume=experience.include_in_resume,
    )


@router.get("/career-profile/experiences", response_model=list[ExperienceResponse])
async def list_experiences(
    target_role_id: UUID | None = Query(default=None),
    identity: IdentityClaims = Depends(get_current_identity),
    service: ExperienceService = Depends(get_experience_service),
) -> list[ExperienceResponse]:
    experiences = await service.list_for_current_user(
        tenant_id=UUID(identity.tenant_id),
        user_id=UUID(identity.user_id),
        target_role_id=target_role_id,
    )
    return [_experience_response(e) for e in experiences]


@router.post(
    "/career-profile/experiences",
    response_model=ExperienceResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_experience(
    request: ExperienceRequest,
    target_role_id: UUID | None = Query(default=None),
    identity: IdentityClaims = Depends(get_current_identity),
    service: ExperienceService = Depends(get_experience_service),
) -> ExperienceResponse:
    experience = await service.add(
        tenant_id=UUID(identity.tenant_id),
        user_id=UUID(identity.user_id),
        title=request.title,
        company=request.company,
        location=request.location,
        start_date=request.start_date,
        end_date=request.end_date,
        description=request.description,
        target_role_id=target_role_id,
    )
    return _experience_response(experience)


@router.patch("/career-profile/experiences/{experience_id}", response_model=ExperienceResponse)
async def update_experience(
    experience_id: UUID,
    request: ExperienceRequest,
    identity: IdentityClaims = Depends(get_current_identity),
    service: ExperienceService = Depends(get_experience_service),
) -> ExperienceResponse:
    experience = await service.update(
        tenant_id=UUID(identity.tenant_id),
        user_id=UUID(identity.user_id),
        experience_id=experience_id,
        title=request.title,
        company=request.company,
        location=request.location,
        start_date=request.start_date,
        end_date=request.end_date,
        description=request.description,
        include_in_resume=request.include_in_resume,
    )
    return _experience_response(experience)


@router.delete(
    "/career-profile/experiences/{experience_id}", status_code=status.HTTP_204_NO_CONTENT
)
async def delete_experience(
    experience_id: UUID,
    identity: IdentityClaims = Depends(get_current_identity),
    service: ExperienceService = Depends(get_experience_service),
) -> None:
    await service.delete(
        tenant_id=UUID(identity.tenant_id),
        user_id=UUID(identity.user_id),
        experience_id=experience_id,
    )


@router.delete("/career-profile/experiences", status_code=status.HTTP_204_NO_CONTENT)
async def clear_experiences(
    target_role_id: UUID | None = Query(default=None),
    identity: IdentityClaims = Depends(get_current_identity),
    service: ExperienceService = Depends(get_experience_service),
) -> None:
    await service.clear_all(
        tenant_id=UUID(identity.tenant_id),
        user_id=UUID(identity.user_id),
        target_role_id=target_role_id,
    )


@router.post(
    "/career-profile/experiences/{experience_id}/move", response_model=list[ExperienceResponse]
)
async def move_experience(
    experience_id: UUID,
    request: MoveRequest,
    target_role_id: UUID | None = Query(default=None),
    identity: IdentityClaims = Depends(get_current_identity),
    service: ExperienceService = Depends(get_experience_service),
) -> list[ExperienceResponse]:
    await service.move(
        tenant_id=UUID(identity.tenant_id),
        user_id=UUID(identity.user_id),
        experience_id=experience_id,
        direction=request.direction,
    )
    # target_role_id here is only for re-fetching the right list to
    # return — move() itself resolved ownership from the item's own
    # career_profile_id, not from this param.
    experiences = await service.list_for_current_user(
        tenant_id=UUID(identity.tenant_id),
        user_id=UUID(identity.user_id),
        target_role_id=target_role_id,
    )
    return [_experience_response(e) for e in experiences]


def _education_response(education: Education) -> EducationResponse:
    return EducationResponse(
        id=education.id,
        institution=education.institution,
        degree=education.degree,
        field_of_study=education.field_of_study,
        start_date=education.start_date,
        end_date=education.end_date,
        description=education.description,
        display_order=education.display_order,
        include_in_resume=education.include_in_resume,
    )


@router.get("/career-profile/educations", response_model=list[EducationResponse])
async def list_educations(
    target_role_id: UUID | None = Query(default=None),
    identity: IdentityClaims = Depends(get_current_identity),
    service: EducationService = Depends(get_education_service),
) -> list[EducationResponse]:
    educations = await service.list_for_current_user(
        tenant_id=UUID(identity.tenant_id),
        user_id=UUID(identity.user_id),
        target_role_id=target_role_id,
    )
    return [_education_response(e) for e in educations]


@router.post(
    "/career-profile/educations",
    response_model=EducationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_education(
    request: EducationRequest,
    target_role_id: UUID | None = Query(default=None),
    identity: IdentityClaims = Depends(get_current_identity),
    service: EducationService = Depends(get_education_service),
) -> EducationResponse:
    education = await service.add(
        tenant_id=UUID(identity.tenant_id),
        user_id=UUID(identity.user_id),
        institution=request.institution,
        degree=request.degree,
        field_of_study=request.field_of_study,
        start_date=request.start_date,
        end_date=request.end_date,
        description=request.description,
        target_role_id=target_role_id,
    )
    return _education_response(education)


@router.patch("/career-profile/educations/{education_id}", response_model=EducationResponse)
async def update_education(
    education_id: UUID,
    request: EducationRequest,
    identity: IdentityClaims = Depends(get_current_identity),
    service: EducationService = Depends(get_education_service),
) -> EducationResponse:
    education = await service.update(
        tenant_id=UUID(identity.tenant_id),
        user_id=UUID(identity.user_id),
        education_id=education_id,
        institution=request.institution,
        degree=request.degree,
        field_of_study=request.field_of_study,
        start_date=request.start_date,
        end_date=request.end_date,
        description=request.description,
        include_in_resume=request.include_in_resume,
    )
    return _education_response(education)


@router.delete("/career-profile/educations/{education_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_education(
    education_id: UUID,
    identity: IdentityClaims = Depends(get_current_identity),
    service: EducationService = Depends(get_education_service),
) -> None:
    await service.delete(
        tenant_id=UUID(identity.tenant_id),
        user_id=UUID(identity.user_id),
        education_id=education_id,
    )


@router.delete("/career-profile/educations", status_code=status.HTTP_204_NO_CONTENT)
async def clear_educations(
    target_role_id: UUID | None = Query(default=None),
    identity: IdentityClaims = Depends(get_current_identity),
    service: EducationService = Depends(get_education_service),
) -> None:
    await service.clear_all(
        tenant_id=UUID(identity.tenant_id),
        user_id=UUID(identity.user_id),
        target_role_id=target_role_id,
    )


@router.post(
    "/career-profile/educations/{education_id}/move", response_model=list[EducationResponse]
)
async def move_education(
    education_id: UUID,
    request: MoveRequest,
    target_role_id: UUID | None = Query(default=None),
    identity: IdentityClaims = Depends(get_current_identity),
    service: EducationService = Depends(get_education_service),
) -> list[EducationResponse]:
    await service.move(
        tenant_id=UUID(identity.tenant_id),
        user_id=UUID(identity.user_id),
        education_id=education_id,
        direction=request.direction,
    )
    educations = await service.list_for_current_user(
        tenant_id=UUID(identity.tenant_id),
        user_id=UUID(identity.user_id),
        target_role_id=target_role_id,
    )
    return [_education_response(e) for e in educations]


def _certification_response(certification: Certification) -> CertificationResponse:
    return CertificationResponse(
        id=certification.id,
        name=certification.name,
        issuing_organization=certification.issuing_organization,
        issue_date=certification.issue_date,
        expiration_date=certification.expiration_date,
        credential_id=certification.credential_id,
        credential_url=certification.credential_url,
        display_order=certification.display_order,
        include_in_resume=certification.include_in_resume,
    )


@router.get("/career-profile/certifications", response_model=list[CertificationResponse])
async def list_certifications(
    target_role_id: UUID | None = Query(default=None),
    identity: IdentityClaims = Depends(get_current_identity),
    service: CertificationService = Depends(get_certification_service),
) -> list[CertificationResponse]:
    certifications = await service.list_for_current_user(
        tenant_id=UUID(identity.tenant_id),
        user_id=UUID(identity.user_id),
        target_role_id=target_role_id,
    )
    return [_certification_response(c) for c in certifications]


@router.post(
    "/career-profile/certifications",
    response_model=CertificationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_certification(
    request: CertificationRequest,
    target_role_id: UUID | None = Query(default=None),
    identity: IdentityClaims = Depends(get_current_identity),
    service: CertificationService = Depends(get_certification_service),
) -> CertificationResponse:
    certification = await service.add(
        tenant_id=UUID(identity.tenant_id),
        user_id=UUID(identity.user_id),
        name=request.name,
        issuing_organization=request.issuing_organization,
        issue_date=request.issue_date,
        expiration_date=request.expiration_date,
        credential_id=request.credential_id,
        credential_url=request.credential_url,
        target_role_id=target_role_id,
    )
    return _certification_response(certification)


@router.patch(
    "/career-profile/certifications/{certification_id}", response_model=CertificationResponse
)
async def update_certification(
    certification_id: UUID,
    request: CertificationRequest,
    identity: IdentityClaims = Depends(get_current_identity),
    service: CertificationService = Depends(get_certification_service),
) -> CertificationResponse:
    certification = await service.update(
        tenant_id=UUID(identity.tenant_id),
        user_id=UUID(identity.user_id),
        certification_id=certification_id,
        name=request.name,
        issuing_organization=request.issuing_organization,
        issue_date=request.issue_date,
        expiration_date=request.expiration_date,
        credential_id=request.credential_id,
        credential_url=request.credential_url,
        include_in_resume=request.include_in_resume,
    )
    return _certification_response(certification)


@router.delete(
    "/career-profile/certifications/{certification_id}", status_code=status.HTTP_204_NO_CONTENT
)
async def delete_certification(
    certification_id: UUID,
    identity: IdentityClaims = Depends(get_current_identity),
    service: CertificationService = Depends(get_certification_service),
) -> None:
    await service.delete(
        tenant_id=UUID(identity.tenant_id),
        user_id=UUID(identity.user_id),
        certification_id=certification_id,
    )


@router.delete("/career-profile/certifications", status_code=status.HTTP_204_NO_CONTENT)
async def clear_certifications(
    target_role_id: UUID | None = Query(default=None),
    identity: IdentityClaims = Depends(get_current_identity),
    service: CertificationService = Depends(get_certification_service),
) -> None:
    await service.clear_all(
        tenant_id=UUID(identity.tenant_id),
        user_id=UUID(identity.user_id),
        target_role_id=target_role_id,
    )


@router.post(
    "/career-profile/certifications/{certification_id}/move",
    response_model=list[CertificationResponse],
)
async def move_certification(
    certification_id: UUID,
    request: MoveRequest,
    target_role_id: UUID | None = Query(default=None),
    identity: IdentityClaims = Depends(get_current_identity),
    service: CertificationService = Depends(get_certification_service),
) -> list[CertificationResponse]:
    await service.move(
        tenant_id=UUID(identity.tenant_id),
        user_id=UUID(identity.user_id),
        certification_id=certification_id,
        direction=request.direction,
    )
    certifications = await service.list_for_current_user(
        tenant_id=UUID(identity.tenant_id),
        user_id=UUID(identity.user_id),
        target_role_id=target_role_id,
    )
    return [_certification_response(c) for c in certifications]


def _highlight_response(highlight: CareerHighlight) -> CareerHighlightResponse:
    return CareerHighlightResponse(
        id=highlight.id,
        title=highlight.title,
        company=highlight.company,
        description=highlight.description,
        occurred_on=highlight.occurred_on,
        display_order=highlight.display_order,
        include_in_resume=highlight.include_in_resume,
    )


@router.get("/career-profile/highlights", response_model=list[CareerHighlightResponse])
async def list_career_highlights(
    target_role_id: UUID | None = Query(default=None),
    identity: IdentityClaims = Depends(get_current_identity),
    service: CareerHighlightService = Depends(get_career_highlight_service),
) -> list[CareerHighlightResponse]:
    highlights = await service.list_for_current_user(
        tenant_id=UUID(identity.tenant_id),
        user_id=UUID(identity.user_id),
        target_role_id=target_role_id,
    )
    return [_highlight_response(h) for h in highlights]


@router.post(
    "/career-profile/highlights",
    response_model=CareerHighlightResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_career_highlight(
    request: CareerHighlightRequest,
    target_role_id: UUID | None = Query(default=None),
    identity: IdentityClaims = Depends(get_current_identity),
    service: CareerHighlightService = Depends(get_career_highlight_service),
) -> CareerHighlightResponse:
    highlight = await service.add(
        tenant_id=UUID(identity.tenant_id),
        user_id=UUID(identity.user_id),
        title=request.title,
        company=request.company,
        description=request.description,
        occurred_on=request.occurred_on,
        target_role_id=target_role_id,
    )
    return _highlight_response(highlight)


@router.patch("/career-profile/highlights/{highlight_id}", response_model=CareerHighlightResponse)
async def update_career_highlight(
    highlight_id: UUID,
    request: CareerHighlightRequest,
    identity: IdentityClaims = Depends(get_current_identity),
    service: CareerHighlightService = Depends(get_career_highlight_service),
) -> CareerHighlightResponse:
    highlight = await service.update(
        tenant_id=UUID(identity.tenant_id),
        user_id=UUID(identity.user_id),
        highlight_id=highlight_id,
        title=request.title,
        company=request.company,
        description=request.description,
        occurred_on=request.occurred_on,
        include_in_resume=request.include_in_resume,
    )
    return _highlight_response(highlight)


@router.delete(
    "/career-profile/highlights/{highlight_id}", status_code=status.HTTP_204_NO_CONTENT
)
async def delete_career_highlight(
    highlight_id: UUID,
    identity: IdentityClaims = Depends(get_current_identity),
    service: CareerHighlightService = Depends(get_career_highlight_service),
) -> None:
    await service.delete(
        tenant_id=UUID(identity.tenant_id),
        user_id=UUID(identity.user_id),
        highlight_id=highlight_id,
    )


@router.delete("/career-profile/highlights", status_code=status.HTTP_204_NO_CONTENT)
async def clear_career_highlights(
    target_role_id: UUID | None = Query(default=None),
    identity: IdentityClaims = Depends(get_current_identity),
    service: CareerHighlightService = Depends(get_career_highlight_service),
) -> None:
    await service.clear_all(
        tenant_id=UUID(identity.tenant_id),
        user_id=UUID(identity.user_id),
        target_role_id=target_role_id,
    )


@router.post(
    "/career-profile/highlights/{highlight_id}/move", response_model=list[CareerHighlightResponse]
)
async def move_career_highlight(
    highlight_id: UUID,
    request: MoveRequest,
    target_role_id: UUID | None = Query(default=None),
    identity: IdentityClaims = Depends(get_current_identity),
    service: CareerHighlightService = Depends(get_career_highlight_service),
) -> list[CareerHighlightResponse]:
    await service.move(
        tenant_id=UUID(identity.tenant_id),
        user_id=UUID(identity.user_id),
        highlight_id=highlight_id,
        direction=request.direction,
    )
    highlights = await service.list_for_current_user(
        tenant_id=UUID(identity.tenant_id),
        user_id=UUID(identity.user_id),
        target_role_id=target_role_id,
    )
    return [_highlight_response(h) for h in highlights]


def _achievement_response(achievement: KeyAchievement) -> KeyAchievementResponse:
    return KeyAchievementResponse(
        id=achievement.id,
        title=achievement.title,
        company=achievement.company,
        description=achievement.description,
        occurred_on=achievement.occurred_on,
        display_order=achievement.display_order,
        include_in_resume=achievement.include_in_resume,
    )


@router.get("/career-profile/achievements", response_model=list[KeyAchievementResponse])
async def list_key_achievements(
    target_role_id: UUID | None = Query(default=None),
    identity: IdentityClaims = Depends(get_current_identity),
    service: KeyAchievementService = Depends(get_key_achievement_service),
) -> list[KeyAchievementResponse]:
    achievements = await service.list_for_current_user(
        tenant_id=UUID(identity.tenant_id),
        user_id=UUID(identity.user_id),
        target_role_id=target_role_id,
    )
    return [_achievement_response(a) for a in achievements]


@router.post(
    "/career-profile/achievements",
    response_model=KeyAchievementResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_key_achievement(
    request: KeyAchievementRequest,
    target_role_id: UUID | None = Query(default=None),
    identity: IdentityClaims = Depends(get_current_identity),
    service: KeyAchievementService = Depends(get_key_achievement_service),
) -> KeyAchievementResponse:
    achievement = await service.add(
        tenant_id=UUID(identity.tenant_id),
        user_id=UUID(identity.user_id),
        title=request.title,
        company=request.company,
        description=request.description,
        occurred_on=request.occurred_on,
        target_role_id=target_role_id,
    )
    return _achievement_response(achievement)


@router.patch(
    "/career-profile/achievements/{achievement_id}", response_model=KeyAchievementResponse
)
async def update_key_achievement(
    achievement_id: UUID,
    request: KeyAchievementRequest,
    identity: IdentityClaims = Depends(get_current_identity),
    service: KeyAchievementService = Depends(get_key_achievement_service),
) -> KeyAchievementResponse:
    achievement = await service.update(
        tenant_id=UUID(identity.tenant_id),
        user_id=UUID(identity.user_id),
        achievement_id=achievement_id,
        title=request.title,
        company=request.company,
        description=request.description,
        occurred_on=request.occurred_on,
        include_in_resume=request.include_in_resume,
    )
    return _achievement_response(achievement)


@router.delete(
    "/career-profile/achievements/{achievement_id}", status_code=status.HTTP_204_NO_CONTENT
)
async def delete_key_achievement(
    achievement_id: UUID,
    identity: IdentityClaims = Depends(get_current_identity),
    service: KeyAchievementService = Depends(get_key_achievement_service),
) -> None:
    await service.delete(
        tenant_id=UUID(identity.tenant_id),
        user_id=UUID(identity.user_id),
        achievement_id=achievement_id,
    )


@router.delete("/career-profile/achievements", status_code=status.HTTP_204_NO_CONTENT)
async def clear_key_achievements(
    target_role_id: UUID | None = Query(default=None),
    identity: IdentityClaims = Depends(get_current_identity),
    service: KeyAchievementService = Depends(get_key_achievement_service),
) -> None:
    await service.clear_all(
        tenant_id=UUID(identity.tenant_id),
        user_id=UUID(identity.user_id),
        target_role_id=target_role_id,
    )


@router.post(
    "/career-profile/achievements/{achievement_id}/move",
    response_model=list[KeyAchievementResponse],
)
async def move_key_achievement(
    achievement_id: UUID,
    request: MoveRequest,
    target_role_id: UUID | None = Query(default=None),
    identity: IdentityClaims = Depends(get_current_identity),
    service: KeyAchievementService = Depends(get_key_achievement_service),
) -> list[KeyAchievementResponse]:
    await service.move(
        tenant_id=UUID(identity.tenant_id),
        user_id=UUID(identity.user_id),
        achievement_id=achievement_id,
        direction=request.direction,
    )
    achievements = await service.list_for_current_user(
        tenant_id=UUID(identity.tenant_id),
        user_id=UUID(identity.user_id),
        target_role_id=target_role_id,
    )
    return [_achievement_response(a) for a in achievements]


def _endorsement_response(endorsement: PeerEndorsement) -> PeerEndorsementResponse:
    return PeerEndorsementResponse(
        id=endorsement.id,
        recommender_name=endorsement.recommender_name,
        recommender_title=endorsement.recommender_title,
        relationship=endorsement.relationship,
        content=endorsement.content,
        display_order=endorsement.display_order,
        include_in_resume=endorsement.include_in_resume,
    )


@router.get("/career-profile/endorsements", response_model=list[PeerEndorsementResponse])
async def list_peer_endorsements(
    identity: IdentityClaims = Depends(get_current_identity),
    service: PeerEndorsementService = Depends(get_peer_endorsement_service),
) -> list[PeerEndorsementResponse]:
    endorsements = await service.list_for_current_user(
        tenant_id=UUID(identity.tenant_id), user_id=UUID(identity.user_id)
    )
    return [_endorsement_response(e) for e in endorsements]


@router.post(
    "/career-profile/endorsements",
    response_model=PeerEndorsementResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_peer_endorsement(
    request: PeerEndorsementRequest,
    identity: IdentityClaims = Depends(get_current_identity),
    service: PeerEndorsementService = Depends(get_peer_endorsement_service),
) -> PeerEndorsementResponse:
    endorsement = await service.add(
        tenant_id=UUID(identity.tenant_id),
        user_id=UUID(identity.user_id),
        recommender_name=request.recommender_name,
        recommender_title=request.recommender_title,
        relationship=request.relationship,
        content=request.content,
    )
    return _endorsement_response(endorsement)


@router.patch(
    "/career-profile/endorsements/{endorsement_id}", response_model=PeerEndorsementResponse
)
async def update_peer_endorsement(
    endorsement_id: UUID,
    request: PeerEndorsementRequest,
    identity: IdentityClaims = Depends(get_current_identity),
    service: PeerEndorsementService = Depends(get_peer_endorsement_service),
) -> PeerEndorsementResponse:
    endorsement = await service.update(
        tenant_id=UUID(identity.tenant_id),
        user_id=UUID(identity.user_id),
        endorsement_id=endorsement_id,
        recommender_name=request.recommender_name,
        recommender_title=request.recommender_title,
        relationship=request.relationship,
        content=request.content,
        include_in_resume=request.include_in_resume,
    )
    return _endorsement_response(endorsement)


@router.delete(
    "/career-profile/endorsements/{endorsement_id}", status_code=status.HTTP_204_NO_CONTENT
)
async def delete_peer_endorsement(
    endorsement_id: UUID,
    identity: IdentityClaims = Depends(get_current_identity),
    service: PeerEndorsementService = Depends(get_peer_endorsement_service),
) -> None:
    await service.delete(
        tenant_id=UUID(identity.tenant_id),
        user_id=UUID(identity.user_id),
        endorsement_id=endorsement_id,
    )


@router.delete("/career-profile/endorsements", status_code=status.HTTP_204_NO_CONTENT)
async def clear_peer_endorsements(
    identity: IdentityClaims = Depends(get_current_identity),
    service: PeerEndorsementService = Depends(get_peer_endorsement_service),
) -> None:
    await service.clear_all(tenant_id=UUID(identity.tenant_id), user_id=UUID(identity.user_id))


@router.post(
    "/career-profile/endorsements/{endorsement_id}/move",
    response_model=list[PeerEndorsementResponse],
)
async def move_peer_endorsement(
    endorsement_id: UUID,
    request: MoveRequest,
    identity: IdentityClaims = Depends(get_current_identity),
    service: PeerEndorsementService = Depends(get_peer_endorsement_service),
) -> list[PeerEndorsementResponse]:
    await service.move(
        tenant_id=UUID(identity.tenant_id),
        user_id=UUID(identity.user_id),
        endorsement_id=endorsement_id,
        direction=request.direction,
    )
    endorsements = await service.list_for_current_user(
        tenant_id=UUID(identity.tenant_id), user_id=UUID(identity.user_id)
    )
    return [_endorsement_response(e) for e in endorsements]


def _goal_response(goal: CareerGoal) -> CareerGoalResponse:
    return CareerGoalResponse(
        id=goal.id,
        target_role=goal.target_role,
        target_date=goal.target_date,
        status=goal.status,
        description=goal.description,
        display_order=goal.display_order,
        include_in_resume=goal.include_in_resume,
    )


@router.get("/career-goals", response_model=list[CareerGoalResponse])
async def list_career_goals(
    identity: IdentityClaims = Depends(get_current_identity),
    service: CareerGoalService = Depends(get_career_goal_service),
) -> list[CareerGoalResponse]:
    goals = await service.list_for_current_user(
        tenant_id=UUID(identity.tenant_id), user_id=UUID(identity.user_id)
    )
    return [_goal_response(g) for g in goals]


@router.post(
    "/career-goals", response_model=CareerGoalResponse, status_code=status.HTTP_201_CREATED
)
async def add_career_goal(
    request: CareerGoalRequest,
    identity: IdentityClaims = Depends(get_current_identity),
    service: CareerGoalService = Depends(get_career_goal_service),
) -> CareerGoalResponse:
    goal = await service.add(
        tenant_id=UUID(identity.tenant_id),
        user_id=UUID(identity.user_id),
        target_role=request.target_role,
        target_date=request.target_date,
        description=request.description,
    )
    return _goal_response(goal)


@router.patch("/career-goals/{goal_id}", response_model=CareerGoalResponse)
async def update_career_goal(
    goal_id: UUID,
    request: CareerGoalUpdateRequest,
    identity: IdentityClaims = Depends(get_current_identity),
    service: CareerGoalService = Depends(get_career_goal_service),
) -> CareerGoalResponse:
    goal = await service.update(
        tenant_id=UUID(identity.tenant_id),
        user_id=UUID(identity.user_id),
        goal_id=goal_id,
        target_role=request.target_role,
        target_date=request.target_date,
        status=request.status,
        description=request.description,
        include_in_resume=request.include_in_resume,
    )
    return _goal_response(goal)


@router.delete("/career-goals/{goal_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_career_goal(
    goal_id: UUID,
    identity: IdentityClaims = Depends(get_current_identity),
    service: CareerGoalService = Depends(get_career_goal_service),
) -> None:
    await service.delete(
        tenant_id=UUID(identity.tenant_id), user_id=UUID(identity.user_id), goal_id=goal_id
    )


@router.delete("/career-goals", status_code=status.HTTP_204_NO_CONTENT)
async def clear_career_goals(
    identity: IdentityClaims = Depends(get_current_identity),
    service: CareerGoalService = Depends(get_career_goal_service),
) -> None:
    await service.clear_all(tenant_id=UUID(identity.tenant_id), user_id=UUID(identity.user_id))


@router.post("/career-goals/{goal_id}/move", response_model=list[CareerGoalResponse])
async def move_career_goal(
    goal_id: UUID,
    request: MoveRequest,
    identity: IdentityClaims = Depends(get_current_identity),
    service: CareerGoalService = Depends(get_career_goal_service),
) -> list[CareerGoalResponse]:
    await service.move(
        tenant_id=UUID(identity.tenant_id),
        user_id=UUID(identity.user_id),
        goal_id=goal_id,
        direction=request.direction,
    )
    goals = await service.list_for_current_user(
        tenant_id=UUID(identity.tenant_id), user_id=UUID(identity.user_id)
    )
    return [_goal_response(g) for g in goals]


def _target_role_response(target_role: TargetRole) -> TargetRoleResponse:
    return TargetRoleResponse(
        id=target_role.id,
        role_name=target_role.role_name,
        tag=target_role.tag,
        required_skills=target_role.required_skills,
    )


@router.get("/career-profile/target-roles", response_model=list[TargetRoleResponse])
async def list_target_roles(
    identity: IdentityClaims = Depends(get_current_identity),
    service: TargetRoleService = Depends(get_target_role_service),
) -> list[TargetRoleResponse]:
    target_roles = await service.list_for_current_user(
        tenant_id=UUID(identity.tenant_id), user_id=UUID(identity.user_id)
    )
    return [_target_role_response(r) for r in target_roles]


@router.post(
    "/career-profile/target-roles",
    response_model=TargetRoleResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_target_role(
    request: TargetRoleRequest,
    identity: IdentityClaims = Depends(get_current_identity),
    service: TargetRoleService = Depends(get_target_role_service),
) -> TargetRoleResponse:
    target_role = await service.add(
        tenant_id=UUID(identity.tenant_id),
        user_id=UUID(identity.user_id),
        role_name=request.role_name,
        tag=request.tag,
    )
    return _target_role_response(target_role)


@router.patch("/career-profile/target-roles/{target_role_id}", response_model=TargetRoleResponse)
async def update_target_role(
    target_role_id: UUID,
    request: TargetRoleRequest,
    identity: IdentityClaims = Depends(get_current_identity),
    service: TargetRoleService = Depends(get_target_role_service),
) -> TargetRoleResponse:
    target_role = await service.update(
        tenant_id=UUID(identity.tenant_id),
        user_id=UUID(identity.user_id),
        target_role_id=target_role_id,
        role_name=request.role_name,
        tag=request.tag,
    )
    return _target_role_response(target_role)


@router.delete(
    "/career-profile/target-roles/{target_role_id}", status_code=status.HTTP_204_NO_CONTENT
)
async def delete_target_role(
    target_role_id: UUID,
    identity: IdentityClaims = Depends(get_current_identity),
    service: TargetRoleService = Depends(get_target_role_service),
) -> None:
    await service.delete(
        tenant_id=UUID(identity.tenant_id),
        user_id=UUID(identity.user_id),
        target_role_id=target_role_id,
    )


@router.post(
    "/career-profile/target-roles/{target_role_id}/required-skills",
    response_model=TargetRoleResponse,
)
async def add_required_skill(
    target_role_id: UUID,
    request: AddRequiredSkillRequest,
    identity: IdentityClaims = Depends(get_current_identity),
    service: TargetRoleService = Depends(get_target_role_service),
) -> TargetRoleResponse:
    target_role = await service.add_required_skill(
        tenant_id=UUID(identity.tenant_id),
        user_id=UUID(identity.user_id),
        target_role_id=target_role_id,
        name=request.name,
    )
    return _target_role_response(target_role)


@router.delete(
    "/career-profile/target-roles/{target_role_id}/required-skills/{skill_name}",
    response_model=TargetRoleResponse,
)
async def remove_required_skill(
    target_role_id: UUID,
    skill_name: str,
    identity: IdentityClaims = Depends(get_current_identity),
    service: TargetRoleService = Depends(get_target_role_service),
) -> TargetRoleResponse:
    target_role = await service.remove_required_skill(
        tenant_id=UUID(identity.tenant_id),
        user_id=UUID(identity.user_id),
        target_role_id=target_role_id,
        name=skill_name,
    )
    return _target_role_response(target_role)


@router.patch(
    "/career-profile/target-roles/{target_role_id}/required-skills/{skill_name}",
    response_model=TargetRoleResponse,
)
async def rename_required_skill(
    target_role_id: UUID,
    skill_name: str,
    request: AddRequiredSkillRequest,
    identity: IdentityClaims = Depends(get_current_identity),
    service: TargetRoleService = Depends(get_target_role_service),
) -> TargetRoleResponse:
    target_role = await service.rename_required_skill(
        tenant_id=UUID(identity.tenant_id),
        user_id=UUID(identity.user_id),
        target_role_id=target_role_id,
        old_name=skill_name,
        new_name=request.name,
    )
    return _target_role_response(target_role)
