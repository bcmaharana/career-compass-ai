"""Job Application Tracking API routes.

Thin per backend-architecture.md: parse input, call one application
service, map the result to a response schema. Self-service data, no
extra RBAC permission required beyond get_current_identity.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, status

from app.api.dependencies import (
    get_current_identity,
    get_interview_round_service,
    get_job_application_service,
    get_job_application_summary_service,
)
from app.api.v1.career_profile.schemas import MoveRequest
from app.api.v1.job_application_tracking.schemas import (
    InterviewRoundRequest,
    InterviewRoundResponse,
    JobApplicationRequest,
    JobApplicationResponse,
    JobApplicationSummaryResponse,
    JobApplicationUpdateRequest,
    NextInterviewResponse,
    StatusCountResponse,
    StuckApplicationResponse,
)
from app.application.job_application_tracking.interview_round_service import (
    InterviewRoundService,
)
from app.application.job_application_tracking.job_application_service import (
    JobApplicationService,
)
from app.application.job_application_tracking.job_application_summary_service import (
    JobApplicationSummary,
    JobApplicationSummaryService,
)
from app.core.identity_provider_interface import IdentityClaims
from app.domain.job_application_tracking.entities import InterviewRound, JobApplication

router = APIRouter(tags=["job-application-tracking"])


def _round_response(round_: InterviewRound) -> InterviewRoundResponse:
    return InterviewRoundResponse(
        id=round_.id,
        job_application_id=round_.job_application_id,
        stage_label=round_.stage_label,
        round_date=round_.round_date,
        interviewer_name=round_.interviewer_name,
        interviewer_title=round_.interviewer_title,
        notes=round_.notes,
        display_order=round_.display_order,
    )


def _application_response(application: JobApplication) -> JobApplicationResponse:
    return JobApplicationResponse(
        id=application.id,
        company=application.company,
        role_title=application.role_title,
        status=application.status,
        status_changed_at=application.status_changed_at,
        target_role_id=application.target_role_id,
        source_title=application.source_title,
        source_company=application.source_company,
        source_redirect_url=application.source_redirect_url,
        jd_tailoring_session_id=application.jd_tailoring_session_id,
        recruiter_id=application.recruiter_id,
        applied_at=application.applied_at,
        notes=application.notes,
        interview_rounds=[_round_response(r) for r in application.interview_rounds],
        created_at=application.created_at,
        updated_at=application.updated_at,
    )


def _summary_response(summary: JobApplicationSummary) -> JobApplicationSummaryResponse:
    return JobApplicationSummaryResponse(
        status_counts=[
            StatusCountResponse(status=sc.status, count=sc.count) for sc in summary.status_counts
        ],
        next_interview=(
            NextInterviewResponse(
                application_id=summary.next_interview.application_id,
                company=summary.next_interview.company,
                role_title=summary.next_interview.role_title,
                stage_label=summary.next_interview.stage_label,
                round_date=summary.next_interview.round_date,
            )
            if summary.next_interview is not None
            else None
        ),
        stuck_count=summary.stuck_count,
        stuck_examples=[
            StuckApplicationResponse(
                application_id=s.application_id,
                company=s.company,
                role_title=s.role_title,
                status=s.status,
                days_in_status=s.days_in_status,
            )
            for s in summary.stuck_examples
        ],
    )


@router.get("/job-applications", response_model=list[JobApplicationResponse])
async def list_job_applications(
    identity: IdentityClaims = Depends(get_current_identity),
    service: JobApplicationService = Depends(get_job_application_service),
) -> list[JobApplicationResponse]:
    applications = await service.list_for_user(UUID(identity.tenant_id), UUID(identity.user_id))
    return [_application_response(a) for a in applications]


@router.get("/job-applications/tracked-provider-ids", response_model=list[str])
async def list_tracked_provider_ids(
    identity: IdentityClaims = Depends(get_current_identity),
    service: JobApplicationService = Depends(get_job_application_service),
) -> list[str]:
    provider_ids = await service.list_tracked_provider_ids(
        UUID(identity.tenant_id), UUID(identity.user_id)
    )
    return sorted(provider_ids)


@router.get("/job-applications/summary", response_model=JobApplicationSummaryResponse)
async def get_job_application_summary(
    identity: IdentityClaims = Depends(get_current_identity),
    service: JobApplicationSummaryService = Depends(get_job_application_summary_service),
) -> JobApplicationSummaryResponse:
    summary = await service.get_summary(UUID(identity.tenant_id), UUID(identity.user_id))
    return _summary_response(summary)


@router.post(
    "/job-applications", response_model=JobApplicationResponse, status_code=status.HTTP_201_CREATED
)
async def create_job_application(
    request: JobApplicationRequest,
    identity: IdentityClaims = Depends(get_current_identity),
    service: JobApplicationService = Depends(get_job_application_service),
) -> JobApplicationResponse:
    application = await service.create(
        tenant_id=UUID(identity.tenant_id),
        user_id=UUID(identity.user_id),
        company=request.company,
        role_title=request.role_title,
        target_role_id=request.target_role_id,
        status=request.status,
        applied_at=request.applied_at,
        notes=request.notes,
        recruiter_id=request.recruiter_id,
    )
    return _application_response(application)


@router.patch("/job-applications/{application_id}", response_model=JobApplicationResponse)
async def update_job_application(
    application_id: UUID,
    request: JobApplicationUpdateRequest,
    identity: IdentityClaims = Depends(get_current_identity),
    service: JobApplicationService = Depends(get_job_application_service),
) -> JobApplicationResponse:
    application = await service.update(
        tenant_id=UUID(identity.tenant_id),
        user_id=UUID(identity.user_id),
        application_id=application_id,
        company=request.company,
        role_title=request.role_title,
        status=request.status,
        target_role_id=request.target_role_id,
        applied_at=request.applied_at,
        notes=request.notes,
        recruiter_id=request.recruiter_id,
    )
    return _application_response(application)


@router.post(
    "/job-applications/{application_id}/unlink-session", response_model=JobApplicationResponse
)
async def unlink_job_application_session(
    application_id: UUID,
    identity: IdentityClaims = Depends(get_current_identity),
    service: JobApplicationService = Depends(get_job_application_service),
) -> JobApplicationResponse:
    application = await service.unlink_session(
        tenant_id=UUID(identity.tenant_id),
        user_id=UUID(identity.user_id),
        application_id=application_id,
    )
    return _application_response(application)


@router.delete("/job-applications/{application_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_job_application(
    application_id: UUID,
    identity: IdentityClaims = Depends(get_current_identity),
    service: JobApplicationService = Depends(get_job_application_service),
) -> None:
    await service.delete(
        tenant_id=UUID(identity.tenant_id), user_id=UUID(identity.user_id), application_id=application_id
    )


@router.post(
    "/job-applications/{application_id}/interview-rounds",
    response_model=InterviewRoundResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_interview_round(
    application_id: UUID,
    request: InterviewRoundRequest,
    identity: IdentityClaims = Depends(get_current_identity),
    service: InterviewRoundService = Depends(get_interview_round_service),
) -> InterviewRoundResponse:
    round_ = await service.add(
        tenant_id=UUID(identity.tenant_id),
        user_id=UUID(identity.user_id),
        application_id=application_id,
        stage_label=request.stage_label,
        round_date=request.round_date,
        interviewer_name=request.interviewer_name,
        interviewer_title=request.interviewer_title,
        notes=request.notes,
    )
    return _round_response(round_)


@router.patch("/interview-rounds/{round_id}", response_model=InterviewRoundResponse)
async def update_interview_round(
    round_id: UUID,
    request: InterviewRoundRequest,
    identity: IdentityClaims = Depends(get_current_identity),
    service: InterviewRoundService = Depends(get_interview_round_service),
) -> InterviewRoundResponse:
    round_ = await service.update(
        tenant_id=UUID(identity.tenant_id),
        user_id=UUID(identity.user_id),
        round_id=round_id,
        stage_label=request.stage_label,
        round_date=request.round_date,
        interviewer_name=request.interviewer_name,
        interviewer_title=request.interviewer_title,
        notes=request.notes,
    )
    return _round_response(round_)


@router.delete("/interview-rounds/{round_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_interview_round(
    round_id: UUID,
    identity: IdentityClaims = Depends(get_current_identity),
    service: InterviewRoundService = Depends(get_interview_round_service),
) -> None:
    await service.delete(
        tenant_id=UUID(identity.tenant_id), user_id=UUID(identity.user_id), round_id=round_id
    )


@router.post("/interview-rounds/{round_id}/move", status_code=status.HTTP_204_NO_CONTENT)
async def move_interview_round(
    round_id: UUID,
    request: MoveRequest,
    identity: IdentityClaims = Depends(get_current_identity),
    service: InterviewRoundService = Depends(get_interview_round_service),
) -> None:
    await service.move(
        tenant_id=UUID(identity.tenant_id),
        user_id=UUID(identity.user_id),
        round_id=round_id,
        direction=request.direction,
    )
