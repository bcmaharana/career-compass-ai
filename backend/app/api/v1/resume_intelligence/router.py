"""Resume Intelligence API routes.

Thin per backend-architecture.md: parse input, call one application
service, map the result to a response schema. Self-service data, no
extra RBAC permission required beyond get_current_identity — same as
every career-profile route.
"""

from __future__ import annotations

import asyncio
from uuid import UUID

from fastapi import APIRouter, Depends, Form, HTTPException, Request, UploadFile, status

from app.api.dependencies import (
    get_current_identity,
    get_resume_extraction_service,
    get_resume_merge_service,
)
from app.api.v1.resume_intelligence.schemas import (
    ResumeMergeRequest,
    ResumeMergeResponse,
    ResumeResponse,
    ResumeSummary,
)
from app.application.resume_intelligence.resume_extraction_service import ResumeExtractionService
from app.application.resume_intelligence.resume_merge_service import ResumeMergeService
from app.core.identity_provider_interface import IdentityClaims
from app.core.logging import get_logger
from app.domain.resume_intelligence.entities import Resume

logger = get_logger(__name__)

router = APIRouter(tags=["resume-intelligence"])

# How often the disconnect race below polls the ASGI connection while the
# (potentially many-minutes-long, LLM-bound) extraction runs in the
# background.
_DISCONNECT_POLL_SECONDS = 1.0


def _resume_response(resume: Resume) -> ResumeResponse:
    return ResumeResponse(
        id=resume.id,
        original_filename=resume.original_filename,
        status=resume.status,
        extracted_data=resume.extracted_data,  # type: ignore[arg-type]  # validated into ExtractedResumeData by pydantic
        error_message=resume.error_message,
        target_role_id=resume.target_role_id,
        created_at=resume.created_at,
    )


def _resume_summary(resume: Resume) -> ResumeSummary:
    return ResumeSummary(
        id=resume.id,
        original_filename=resume.original_filename,
        status=resume.status,
        target_role_id=resume.target_role_id,
        created_at=resume.created_at,
    )


@router.get("/resume-intelligence", response_model=list[ResumeSummary])
async def list_resumes(
    identity: IdentityClaims = Depends(get_current_identity),
    service: ResumeExtractionService = Depends(get_resume_extraction_service),
) -> list[ResumeSummary]:
    resumes = await service.list_for_current_user(
        tenant_id=UUID(identity.tenant_id), user_id=UUID(identity.user_id)
    )
    return [_resume_summary(r) for r in resumes]


@router.get("/resume-intelligence/{resume_id}", response_model=ResumeResponse)
async def get_resume(
    resume_id: UUID,
    identity: IdentityClaims = Depends(get_current_identity),
    service: ResumeExtractionService = Depends(get_resume_extraction_service),
) -> ResumeResponse:
    resume = await service.get_owned_or_raise(
        tenant_id=UUID(identity.tenant_id), user_id=UUID(identity.user_id), resume_id=resume_id
    )
    return _resume_response(resume)


@router.post(
    "/resume-intelligence/upload",
    response_model=ResumeResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_resume(
    request: Request,
    file: UploadFile,
    # Plain Form field, not JSON body — this endpoint is multipart
    # (the file itself requires that), and multipart requests can only
    # carry additional fields as further form fields, not a JSON body
    # alongside the file.
    target_role_id: UUID | None = Form(default=None),
    identity: IdentityClaims = Depends(get_current_identity),
    service: ResumeExtractionService = Depends(get_resume_extraction_service),
) -> ResumeResponse:
    content = await file.read()

    # Extraction can run for minutes (a slow local Ollama model, see
    # ResumeExtractionService's docstring) with no job queue behind it —
    # the frontend's Cancel button (ResumeIntelligencePage.tsx) works by
    # aborting the browser's fetch, which by itself does nothing to stop
    # this coroutine from continuing to run to completion server-side.
    # Without this race, a cancel-and-retry (or several) silently left
    # the original request(s) still running in the background, each one
    # eventually writing its own `failed` Resume row once its own
    # multi-minute timeout hit — a real bug caught live: one upload
    # attempt produced three `failed` history entries. Racing the
    # extraction against a poll of the connection's disconnect state
    # (the documented Starlette pattern for cancelling long-running work
    # on client disconnect) makes Cancel a *real* cancel: the task is
    # actually cancelled, which unwinds the awaited LLMService call
    # (aborting the outbound HTTP request to the provider) before it
    # ever reaches the `resumes.create(...)` call, so no row is written
    # for a cancelled attempt at all.
    extraction_task = asyncio.ensure_future(
        service.upload_and_extract(
            tenant_id=UUID(identity.tenant_id),
            user_id=UUID(identity.user_id),
            filename=file.filename or "resume",
            content=content,
            content_type=file.content_type or "application/octet-stream",
            target_role_id=target_role_id,
        )
    )
    while not extraction_task.done():
        done, _ = await asyncio.wait({extraction_task}, timeout=_DISCONNECT_POLL_SECONDS)
        if extraction_task in done:
            break
        if await request.is_disconnected():
            extraction_task.cancel()
            logger.info(
                "resume_upload_client_disconnected",
                tenant_id=identity.tenant_id,
                user_id=identity.user_id,
            )
            break

    if extraction_task.cancelled():
        # The client is already gone — there's no one to send a response
        # to. Raising still lets FastAPI/Starlette unwind cleanly; the
        # ASGI server drops the (unsendable) response rather than erroring.
        raise HTTPException(status_code=499, detail="Client disconnected before upload finished.")

    resume = extraction_task.result()
    return _resume_response(resume)


@router.post("/resume-intelligence/merge", response_model=ResumeMergeResponse)
async def merge_resume(
    request: ResumeMergeRequest,
    identity: IdentityClaims = Depends(get_current_identity),
    service: ResumeMergeService = Depends(get_resume_merge_service),
) -> ResumeMergeResponse:
    result = await service.merge(
        tenant_id=UUID(identity.tenant_id),
        user_id=UUID(identity.user_id),
        resume_id=request.resume_id,
        accept_headline=request.accept_headline,
        accept_summary=request.accept_summary,
        accepted_skill_indices=request.accepted_skill_indices,
        accepted_experience_indices=request.accepted_experience_indices,
        accepted_education_indices=request.accepted_education_indices,
        accepted_certification_indices=request.accepted_certification_indices,
        accepted_career_highlight_indices=request.accepted_career_highlight_indices,
        accepted_key_achievement_indices=request.accepted_key_achievement_indices,
    )
    return ResumeMergeResponse(
        added_experience_count=result.added_experience_count,
        added_education_count=result.added_education_count,
        added_certification_count=result.added_certification_count,
        added_skills_count=result.added_skills_count,
        added_career_highlight_count=result.added_career_highlight_count,
        added_key_achievement_count=result.added_key_achievement_count,
        updated_headline=result.updated_headline,
        updated_summary=result.updated_summary,
        skipped_experience_titles=result.skipped_experience_titles,
    )


@router.delete("/resume-intelligence/{resume_id}", status_code=status.HTTP_204_NO_CONTENT)
async def discard_resume(
    resume_id: UUID,
    identity: IdentityClaims = Depends(get_current_identity),
    service: ResumeExtractionService = Depends(get_resume_extraction_service),
) -> None:
    await service.discard(
        tenant_id=UUID(identity.tenant_id), user_id=UUID(identity.user_id), resume_id=resume_id
    )
