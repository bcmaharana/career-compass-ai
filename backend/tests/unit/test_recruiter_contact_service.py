"""Unit tests for RecruiterContactService — fake repository, no
database.
"""

from __future__ import annotations

import uuid
from datetime import date

import pytest

from app.application.job_application_tracking.recruiter_contact_service import (
    RecruiterContactService,
)
from app.core.exceptions import NotFoundError
from app.domain.job_application_tracking.entities import RecruiterContact

pytestmark = pytest.mark.unit


class FakeRecruiterContactRepository:
    def __init__(self) -> None:
        self.contacts: dict[uuid.UUID, RecruiterContact] = {}

    async def create(self, contact: RecruiterContact) -> RecruiterContact:
        self.contacts[contact.id] = contact
        return contact

    async def get_by_id(self, tenant_id: uuid.UUID, contact_id: uuid.UUID) -> RecruiterContact | None:
        c = self.contacts.get(contact_id)
        return c if c and c.tenant_id == tenant_id else None

    async def list_for_user(self, tenant_id: uuid.UUID, user_id: uuid.UUID) -> list[RecruiterContact]:
        return [
            c for c in self.contacts.values() if c.tenant_id == tenant_id and c.user_id == user_id
        ]

    async def update(self, contact: RecruiterContact) -> RecruiterContact:
        self.contacts[contact.id] = contact
        return contact

    async def soft_delete(self, tenant_id: uuid.UUID, contact_id: uuid.UUID) -> None:
        self.contacts.pop(contact_id, None)


@pytest.fixture
def service() -> tuple[RecruiterContactService, FakeRecruiterContactRepository]:
    repo = FakeRecruiterContactRepository()
    return RecruiterContactService(repo), repo


class TestAddAndUpdate:
    async def test_add_creates_a_contact_creatable_standalone(self, service) -> None:
        svc, _ = service
        tenant_id, user_id = uuid.uuid4(), uuid.uuid4()

        contact = await svc.add(tenant_id=tenant_id, user_id=user_id, name="Jane Recruiter")

        assert contact.name == "Jane Recruiter"
        assert contact.contact_history == []

    async def test_cannot_update_another_users_contact(self, service) -> None:
        svc, _ = service
        tenant_id = uuid.uuid4()
        owner, other = uuid.uuid4(), uuid.uuid4()
        contact = await svc.add(tenant_id=tenant_id, user_id=owner, name="Jane")

        with pytest.raises(NotFoundError):
            await svc.update(
                tenant_id=tenant_id,
                user_id=other,
                contact_id=contact.id,
                name="Someone Else",
                email=None,
                phone=None,
                company=None,
                linkedin_url=None,
                role_title=None,
            )


class TestAddNote:
    async def test_add_note_appends_to_history(self, service) -> None:
        svc, _ = service
        tenant_id, user_id = uuid.uuid4(), uuid.uuid4()
        contact = await svc.add(tenant_id=tenant_id, user_id=user_id, name="Jane")

        updated = await svc.add_note(
            tenant_id=tenant_id,
            user_id=user_id,
            contact_id=contact.id,
            note="Called, discussed timeline.",
            note_date=date(2026, 8, 20),
        )
        updated = await svc.add_note(
            tenant_id=tenant_id,
            user_id=user_id,
            contact_id=contact.id,
            note="Follow-up email sent.",
            note_date=date(2026, 8, 25),
        )

        assert [e.note for e in updated.contact_history] == [
            "Called, discussed timeline.",
            "Follow-up email sent.",
        ]
        assert updated.contact_history[0].date == date(2026, 8, 20)

    async def test_add_note_does_not_touch_other_fields(self, service) -> None:
        svc, _ = service
        tenant_id, user_id = uuid.uuid4(), uuid.uuid4()
        contact = await svc.add(
            tenant_id=tenant_id, user_id=user_id, name="Jane", email="jane@example.com"
        )

        updated = await svc.add_note(
            tenant_id=tenant_id,
            user_id=user_id,
            contact_id=contact.id,
            note="Note",
            note_date=date(2026, 8, 20),
        )

        assert updated.email == "jane@example.com"


class TestDelete:
    async def test_delete_removes_the_contact(self, service) -> None:
        svc, repo = service
        tenant_id, user_id = uuid.uuid4(), uuid.uuid4()
        contact = await svc.add(tenant_id=tenant_id, user_id=user_id, name="Jane")

        await svc.delete(tenant_id=tenant_id, user_id=user_id, contact_id=contact.id)

        assert contact.id not in repo.contacts
