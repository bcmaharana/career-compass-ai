"""Recruiter Contact application service — standalone, reusable across
applications, creatable on its own before any JobApplication ever
references it. `add_note` appends to the contact_history list in
place, same idiom as any other [{...}]-column mutator in this app
(e.g. InterviewTopicService's reference_links).
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from uuid import UUID

from app.core.exceptions import NotFoundError
from app.domain.job_application_tracking.entities import ContactHistoryEntry, RecruiterContact
from app.domain.job_application_tracking.repositories import RecruiterContactRepository


class RecruiterContactService:
    def __init__(self, contacts: RecruiterContactRepository) -> None:
        self._contacts = contacts

    async def _get_owned_or_raise(
        self, tenant_id: UUID, user_id: UUID, contact_id: UUID
    ) -> RecruiterContact:
        contact = await self._contacts.get_by_id(tenant_id, contact_id)
        if contact is None or contact.user_id != user_id:
            raise NotFoundError(
                "Recruiter contact not found.", code="RECRUITER_CONTACT_NOT_FOUND"
            )
        return contact

    async def add(
        self,
        *,
        tenant_id: UUID,
        user_id: UUID,
        name: str,
        email: str | None = None,
        phone: str | None = None,
        company: str | None = None,
        linkedin_url: str | None = None,
        role_title: str | None = None,
    ) -> RecruiterContact:
        now = datetime.now(UTC)
        return await self._contacts.create(
            RecruiterContact(
                id=uuid.uuid4(),
                tenant_id=tenant_id,
                user_id=user_id,
                name=name,
                created_at=now,
                updated_at=now,
                email=email,
                phone=phone,
                company=company,
                linkedin_url=linkedin_url,
                role_title=role_title,
            )
        )

    async def list_for_user(self, tenant_id: UUID, user_id: UUID) -> list[RecruiterContact]:
        return await self._contacts.list_for_user(tenant_id, user_id)

    async def update(
        self,
        *,
        tenant_id: UUID,
        user_id: UUID,
        contact_id: UUID,
        name: str,
        email: str | None,
        phone: str | None,
        company: str | None,
        linkedin_url: str | None,
        role_title: str | None,
    ) -> RecruiterContact:
        contact = await self._get_owned_or_raise(tenant_id, user_id, contact_id)
        contact.name = name
        contact.email = email
        contact.phone = phone
        contact.company = company
        contact.linkedin_url = linkedin_url
        contact.role_title = role_title
        return await self._contacts.update(contact)

    async def add_note(
        self, *, tenant_id: UUID, user_id: UUID, contact_id: UUID, note: str, note_date: date
    ) -> RecruiterContact:
        contact = await self._get_owned_or_raise(tenant_id, user_id, contact_id)
        contact.contact_history = [
            *contact.contact_history,
            ContactHistoryEntry(date=note_date, note=note),
        ]
        return await self._contacts.update(contact)

    async def delete(self, *, tenant_id: UUID, user_id: UUID, contact_id: UUID) -> None:
        await self._get_owned_or_raise(tenant_id, user_id, contact_id)
        await self._contacts.soft_delete(tenant_id, contact_id)
