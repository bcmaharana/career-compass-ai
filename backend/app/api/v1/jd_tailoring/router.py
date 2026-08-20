"""JD Tailoring API routes.

Thin per backend-architecture.md: parse input, call one application
service, map the result to a response schema. Self-service data, no
extra RBAC permission required beyond get_current_identity — same as
every career-profile route.
"""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, status

from app.api.dependencies import (
    get_current_identity,
    get_jd_extraction_service,
    get_jd_tailoring_intake_service,
    get_jd_tailoring_session_service,
    get_tailored_resume_service,
)
from app.api.v1.jd_tailoring.schemas import (
    JdExtractionRequest,
    JdExtractionResponse,
    JdTailoringMessageResponse,
    JdTailoringSessionResponse,
    SendMessageRequest,
    SendMessageResponse,
    StartCustomRequest,
    StartFromListingRequest,
    StartSessionResponse,
)
from app.application.jd_tailoring.jd_extraction_service import JdExtractionService
from app.application.jd_tailoring.jd_tailoring_intake_service import JdTailoringIntakeService
from app.application.jd_tailoring.jd_tailoring_session_service import JdTailoringSessionService
from app.application.jd_tailoring.tailored_resume_service import (
    TailoredResumeDownloadUrls,
    TailoredResumeService,
)
from app.core.identity_provider_interface import IdentityClaims
from app.domain.jd_tailoring.entities import JdTailoringMessage, JdTailoringSession

router = APIRouter(tags=["jd-tailoring"])


def _message_response(message: JdTailoringMessage) -> JdTailoringMessageResponse:
    return JdTailoringMessageResponse(
        id=message.id, role=message.role.value, content=message.content, created_at=message.created_at
    )


def _session_response(
    session: JdTailoringSession, download_urls: TailoredResumeDownloadUrls
) -> JdTailoringSessionResponse:
    return JdTailoringSessionResponse(
        id=session.id,
        target_role_id=session.target_role_id,
        source_type=session.source_type,
        source_title=session.source_title,
        source_company=session.source_company,
        source_redirect_url=session.source_redirect_url,
        jd_text=session.jd_text,
        tailored_resume_status=session.tailored_resume_status,
        tailored_resume_error=session.tailored_resume_error,
        tailored_resume_generated_at=session.tailored_resume_generated_at,
        tailored_resume_docx_url=download_urls.docx_url,
        tailored_resume_pdf_url=download_urls.pdf_url,
        created_at=session.created_at,
    )


@router.post(
    "/jd-tailoring/sessions/from-listing",
    response_model=StartSessionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def start_session_from_listing(
    request: StartFromListingRequest,
    identity: IdentityClaims = Depends(get_current_identity),
    intake: JdTailoringIntakeService = Depends(get_jd_tailoring_intake_service),
    tailored_resume: TailoredResumeService = Depends(get_tailored_resume_service),
) -> StartSessionResponse:
    result = await intake.start_from_listing(
        tenant_id=UUID(identity.tenant_id),
        user_id=UUID(identity.user_id),
        target_role_id=request.target_role_id,
        provider_id=request.provider_id,
        title=request.title,
        company=request.company,
        redirect_url=request.redirect_url,
        jd_text=request.jd_text,
    )
    urls = await tailored_resume.get_download_urls(result.session)
    return StartSessionResponse(
        session=_session_response(result.session, urls),
        job_application_id=result.job_application.id,
    )


@router.post(
    "/jd-tailoring/sessions/custom",
    response_model=StartSessionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def start_custom_session(
    request: StartCustomRequest,
    identity: IdentityClaims = Depends(get_current_identity),
    intake: JdTailoringIntakeService = Depends(get_jd_tailoring_intake_service),
    tailored_resume: TailoredResumeService = Depends(get_tailored_resume_service),
) -> StartSessionResponse:
    result = await intake.start_custom(
        tenant_id=UUID(identity.tenant_id),
        user_id=UUID(identity.user_id),
        target_role_id=request.target_role_id,
        jd_text=request.jd_text,
        company=request.company,
        role_title=request.role_title,
    )
    urls = await tailored_resume.get_download_urls(result.session)
    return StartSessionResponse(
        session=_session_response(result.session, urls),
        job_application_id=result.job_application.id,
    )


@router.post("/jd-tailoring/extract", response_model=JdExtractionResponse)
async def extract_jd_fields(
    request: JdExtractionRequest,
    identity: IdentityClaims = Depends(get_current_identity),
    service: JdExtractionService = Depends(get_jd_extraction_service),
) -> JdExtractionResponse:
    result = await service.extract(
        tenant_id=UUID(identity.tenant_id), user_id=UUID(identity.user_id), jd_text=request.jd_text
    )
    return JdExtractionResponse(company=result.company, role_title=result.role_title)


@router.get("/jd-tailoring/sessions", response_model=list[JdTailoringSessionResponse])
async def list_sessions(
    identity: IdentityClaims = Depends(get_current_identity),
    service: JdTailoringSessionService = Depends(get_jd_tailoring_session_service),
    tailored_resume: TailoredResumeService = Depends(get_tailored_resume_service),
) -> list[JdTailoringSessionResponse]:
    sessions = await service.list_for_user(UUID(identity.tenant_id), UUID(identity.user_id))
    responses = []
    for session in sessions:
        urls = await tailored_resume.get_download_urls(session)
        responses.append(_session_response(session, urls))
    return responses


@router.get(
    "/jd-tailoring/sessions/{session_id}/messages",
    response_model=list[JdTailoringMessageResponse],
)
async def list_session_messages(
    session_id: UUID,
    identity: IdentityClaims = Depends(get_current_identity),
    service: JdTailoringSessionService = Depends(get_jd_tailoring_session_service),
) -> list[JdTailoringMessageResponse]:
    messages = await service.list_messages(
        tenant_id=UUID(identity.tenant_id), user_id=UUID(identity.user_id), session_id=session_id
    )
    return [_message_response(m) for m in messages]


@router.post(
    "/jd-tailoring/sessions/{session_id}/messages", response_model=SendMessageResponse
)
async def send_session_message(
    session_id: UUID,
    request: SendMessageRequest,
    identity: IdentityClaims = Depends(get_current_identity),
    service: JdTailoringSessionService = Depends(get_jd_tailoring_session_service),
) -> SendMessageResponse:
    turn = await service.send_message(
        tenant_id=UUID(identity.tenant_id),
        user_id=UUID(identity.user_id),
        session_id=session_id,
        content=request.content,
    )
    return SendMessageResponse(
        session_id=turn.session_id,
        user_message=_message_response(turn.user_message),
        assistant_message=_message_response(turn.assistant_message),
    )


@router.post(
    "/jd-tailoring/sessions/{session_id}/generate-resume",
    response_model=JdTailoringSessionResponse,
)
async def generate_tailored_resume(
    session_id: UUID,
    format: Literal["docx", "pdf"],
    identity: IdentityClaims = Depends(get_current_identity),
    service: TailoredResumeService = Depends(get_tailored_resume_service),
) -> JdTailoringSessionResponse:
    session, _url = await service.generate(
        tenant_id=UUID(identity.tenant_id),
        user_id=UUID(identity.user_id),
        session_id=session_id,
        format=format,
    )
    # get_download_urls covers both formats in one call, including the
    # one just generated — simpler than threading the single-format
    # `_url` generate() already returned through separately.
    urls = await service.get_download_urls(session)
    return _session_response(session, urls)


@router.delete("/jd-tailoring/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_session(
    session_id: UUID,
    identity: IdentityClaims = Depends(get_current_identity),
    service: JdTailoringSessionService = Depends(get_jd_tailoring_session_service),
) -> None:
    await service.soft_delete(
        tenant_id=UUID(identity.tenant_id), user_id=UUID(identity.user_id), session_id=session_id
    )


@router.delete(
    "/jd-tailoring/sessions/{session_id}/messages", status_code=status.HTTP_204_NO_CONTENT
)
async def clear_session_messages(
    session_id: UUID,
    identity: IdentityClaims = Depends(get_current_identity),
    service: JdTailoringSessionService = Depends(get_jd_tailoring_session_service),
) -> None:
    """Clears just the conversation — the session itself (JD text,
    target role link, any generated tailored resume) is untouched. The
    distinct action from DELETE .../sessions/{id} above, which removes
    the whole session."""
    await service.clear_messages(
        tenant_id=UUID(identity.tenant_id), user_id=UUID(identity.user_id), session_id=session_id
    )


@router.delete(
    "/jd-tailoring/sessions/{session_id}/messages/{message_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_session_message(
    session_id: UUID,
    message_id: UUID,
    identity: IdentityClaims = Depends(get_current_identity),
    service: JdTailoringSessionService = Depends(get_jd_tailoring_session_service),
) -> None:
    """Removes exactly one message — e.g. one piece of AI-suggested
    advice the person doesn't want to keep — leaving every other
    message and the session itself untouched."""
    await service.delete_message(
        tenant_id=UUID(identity.tenant_id),
        user_id=UUID(identity.user_id),
        session_id=session_id,
        message_id=message_id,
    )
