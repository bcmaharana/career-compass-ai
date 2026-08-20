"""Recruiter Contacts API routes.

Thin per backend-architecture.md: parse input, call one application
service, map the result to a response schema. Self-service data, no
extra RBAC permission required beyond get_current_identity.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, status

from app.api.dependencies import get_current_identity, get_recruiter_contact_service
from app.api.v1.recruiter_contacts.schemas import (
    AddContactNoteRequest,
    ContactHistoryEntryResponse,
    RecruiterContactRequest,
    RecruiterContactResponse,
)
from app.application.job_application_tracking.recruiter_contact_service import (
    RecruiterContactService,
)
from app.core.identity_provider_interface import IdentityClaims
from app.domain.job_application_tracking.entities import RecruiterContact

router = APIRouter(tags=["recruiter-contacts"])


def _contact_response(contact: RecruiterContact) -> RecruiterContactResponse:
    return RecruiterContactResponse(
        id=contact.id,
        name=contact.name,
        email=contact.email,
        phone=contact.phone,
        company=contact.company,
        linkedin_url=contact.linkedin_url,
        role_title=contact.role_title,
        contact_history=[
            ContactHistoryEntryResponse(date=e.date, note=e.note) for e in contact.contact_history
        ],
        created_at=contact.created_at,
        updated_at=contact.updated_at,
    )


@router.get("/recruiter-contacts", response_model=list[RecruiterContactResponse])
async def list_recruiter_contacts(
    identity: IdentityClaims = Depends(get_current_identity),
    service: RecruiterContactService = Depends(get_recruiter_contact_service),
) -> list[RecruiterContactResponse]:
    contacts = await service.list_for_user(UUID(identity.tenant_id), UUID(identity.user_id))
    return [_contact_response(c) for c in contacts]


@router.post(
    "/recruiter-contacts",
    response_model=RecruiterContactResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_recruiter_contact(
    request: RecruiterContactRequest,
    identity: IdentityClaims = Depends(get_current_identity),
    service: RecruiterContactService = Depends(get_recruiter_contact_service),
) -> RecruiterContactResponse:
    contact = await service.add(
        tenant_id=UUID(identity.tenant_id),
        user_id=UUID(identity.user_id),
        name=request.name,
        email=request.email,
        phone=request.phone,
        company=request.company,
        linkedin_url=request.linkedin_url,
        role_title=request.role_title,
    )
    return _contact_response(contact)


@router.patch("/recruiter-contacts/{contact_id}", response_model=RecruiterContactResponse)
async def update_recruiter_contact(
    contact_id: UUID,
    request: RecruiterContactRequest,
    identity: IdentityClaims = Depends(get_current_identity),
    service: RecruiterContactService = Depends(get_recruiter_contact_service),
) -> RecruiterContactResponse:
    contact = await service.update(
        tenant_id=UUID(identity.tenant_id),
        user_id=UUID(identity.user_id),
        contact_id=contact_id,
        name=request.name,
        email=request.email,
        phone=request.phone,
        company=request.company,
        linkedin_url=request.linkedin_url,
        role_title=request.role_title,
    )
    return _contact_response(contact)


@router.post("/recruiter-contacts/{contact_id}/notes", response_model=RecruiterContactResponse)
async def add_recruiter_contact_note(
    contact_id: UUID,
    request: AddContactNoteRequest,
    identity: IdentityClaims = Depends(get_current_identity),
    service: RecruiterContactService = Depends(get_recruiter_contact_service),
) -> RecruiterContactResponse:
    contact = await service.add_note(
        tenant_id=UUID(identity.tenant_id),
        user_id=UUID(identity.user_id),
        contact_id=contact_id,
        note=request.note,
        note_date=request.note_date,
    )
    return _contact_response(contact)


@router.delete("/recruiter-contacts/{contact_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_recruiter_contact(
    contact_id: UUID,
    identity: IdentityClaims = Depends(get_current_identity),
    service: RecruiterContactService = Depends(get_recruiter_contact_service),
) -> None:
    await service.delete(
        tenant_id=UUID(identity.tenant_id), user_id=UUID(identity.user_id), contact_id=contact_id
    )
