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

# In-memory upload_token -> (owning user_id, running extraction task)
# registry, keyed by a client-generated token (see ResumeIntelligencePage's
# UploadCard) rather than resume_id, since no Resume row exists yet while
# extraction is in flight. This is what makes Cancel an explicit, reliable
# stop rather than relying solely on the disconnect race below — verified
# live (see CLAUDE.md) that request.is_disconnected() never fires through
# Docker Desktop's Windows networking in this dev setup, so a browser
# abort() alone left the server-side extraction running for its full
# multi-minute duration regardless. A plain module-level dict is safe here
# without a lock: this backend runs a single asyncio event loop, and every
# access below is a synchronous dict operation with no `await` in between.
_active_uploads: dict[str, tuple[str, asyncio.Task[Resume]]] = {}


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
    # Client-generated correlation id (ResumeIntelligencePage.tsx's
    # UploadCard) that lets a later, separate request to the /cancel
    # endpoint below find and cancel THIS specific extraction task.
    # Optional only for backward compatibility with any in-flight
    # frontend build that predates this field; a real Cancel click
    # can't be routed to the right task without it.
    upload_token: str | None = Form(default=None),
    identity: IdentityClaims = Depends(get_current_identity),
    service: ResumeExtractionService = Depends(get_resume_extraction_service),
) -> ResumeResponse:
    content = await file.read()

    # Extraction can run for minutes (a slow local Ollama model, see
    # ResumeExtractionService's docstring) with no job queue behind it.
    # Two independent mechanisms can cancel `extraction_task`, both
    # converging on the same cancel-and-unwind behavior below: (1) the
    # disconnect-poll loop just under this comment, which only helps
    # behind a real reverse proxy that actually surfaces a client
    # disconnect to Starlette — verified live NOT to happen through
    # Docker Desktop's Windows networking in this dev setup (see
    # CLAUDE.md), so it's kept but not relied on; (2) the explicit
    # `/upload/{upload_token}/cancel` endpoint below, which is what the
    # frontend's Cancel button actually calls, and works regardless of
    # whether this connection's disconnect is ever detected. Either path
    # calling extraction_task.cancel() unwinds the awaited LLMService
    # call (aborting the outbound HTTP request to the provider) before
    # it ever reaches the `resumes.create(...)` call, so no row is
    # written for a cancelled attempt at all.
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
    if upload_token:
        _active_uploads[upload_token] = (identity.user_id, extraction_task)

    try:
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
            # Either the client disconnected (see above) or explicitly
            # cancelled via the /cancel endpoint — either way there's no
            # useful response to send back. Raising still lets
            # FastAPI/Starlette unwind cleanly; a genuinely-gone client
            # never sees this, and an explicit-cancel caller's browser
            # already gave up on this same request itself (see
            # UploadCard's handleCancel, which aborts its own fetch
            # alongside calling /cancel).
            raise HTTPException(
                status_code=499, detail="Upload was cancelled before it finished."
            )

        resume = extraction_task.result()
        return _resume_response(resume)
    finally:
        if upload_token:
            _active_uploads.pop(upload_token, None)


@router.post(
    "/resume-intelligence/upload/{upload_token}/cancel",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def cancel_upload(
    upload_token: str,
    identity: IdentityClaims = Depends(get_current_identity),
) -> None:
    """Cancels every extraction currently in flight for this user, not
    just the one matching `upload_token` (accepted in the URL for a
    RESTful shape, but deliberately not the only thing checked here).

    A real bug found live: the frontend only ever remembers the ONE
    most recent upload_token (see upload-progress-store.ts) — but
    nothing prevents more than one extraction from being in flight for
    the same user at once (e.g. a retry fired before an earlier
    attempt's Cancel had actually been confirmed, or the earlier
    attempt was simply never cancelled and is still silently running).
    Cancelling only the latest, remembered token left any earlier,
    now-forgotten task completely unreachable — it kept running to
    completion in the background regardless of what Cancel did, which
    is exactly the "cancel just releases the button, the process is
    still running" behavior reported live. Sweeping every entry owned
    by this user closes that gap: however many overlapping attempts
    accumulated, one Cancel click stops all of them. Idempotent and
    silent when there's nothing to cancel (already finished) — same
    "no error over a no-op" convention as discard_resume above.
    """
    for _token, (owner_user_id, task) in list(_active_uploads.items()):
        if owner_user_id == identity.user_id:
            task.cancel()


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
        target_role_id=request.target_role_id,
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
