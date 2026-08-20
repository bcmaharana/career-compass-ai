"""Request/response schemas for the Recruiter Contacts API."""

from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel


class RecruiterContactRequest(BaseModel):
    name: str
    email: str | None = None
    phone: str | None = None
    company: str | None = None
    linkedin_url: str | None = None
    role_title: str | None = None


class ContactHistoryEntryResponse(BaseModel):
    date: date
    note: str


class RecruiterContactResponse(BaseModel):
    id: UUID
    name: str
    email: str | None
    phone: str | None
    company: str | None
    linkedin_url: str | None
    role_title: str | None
    contact_history: list[ContactHistoryEntryResponse]
    created_at: datetime
    updated_at: datetime


class AddContactNoteRequest(BaseModel):
    note: str
    note_date: date
