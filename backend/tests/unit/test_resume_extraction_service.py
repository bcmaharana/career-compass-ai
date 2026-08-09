"""Unit tests for ResumeExtractionService.

Uses fake in-memory repositories/adapters satisfying the Protocol
interfaces in app/domain/resume_intelligence/ — no database, no real
storage or LLM call.
"""

from __future__ import annotations

import uuid
from dataclasses import replace
from datetime import UTC, datetime

import pytest

from app.application.resume_intelligence.resume_extraction_service import (
    ResumeExtractionService,
)
from app.core.exceptions import CareerCompassError
from app.domain.resume_intelligence.entities import Resume

PDF_CONTENT_TYPE = "application/pdf"

VALID_LLM_JSON = """{
  "headline": "Senior Backend Engineer",
  "summary": "Backend engineer with 8 years of experience.",
  "skills": [{"name": "Python", "category": null}, {"name": "PostgreSQL", "category": "Databases"}],
  "experience": [
    {"title": "Senior Backend Engineer", "company": "Initech", "location": null,
     "start_date": "2021-01-01", "end_date": null, "description": "Led migrations."}
  ],
  "education": [
    {"institution": "State University", "degree": "B.S. CS", "field_of_study": null,
     "start_date": "2014-09-01", "end_date": "2018-05-31", "description": null}
  ],
  "certifications": [],
  "career_highlights": [
    {"title": "Led migration of monolith to microservices, cutting deploy time 40%.",
     "company": "Initech", "description": null, "occurred_on": null}
  ]
}"""


class FakeResumeRepository:
    def __init__(self) -> None:
        self.resumes: dict[uuid.UUID, Resume] = {}

    async def create(self, resume: Resume) -> Resume:
        self.resumes[resume.id] = resume
        return replace(resume)

    async def get_by_id(self, tenant_id: uuid.UUID, resume_id: uuid.UUID) -> Resume | None:
        resume = self.resumes.get(resume_id)
        return replace(resume) if resume and resume.tenant_id == tenant_id else None

    async def list_for_user(self, tenant_id: uuid.UUID, user_id: uuid.UUID) -> list[Resume]:
        # Dict insertion order (reversed) stands in for "most recent
        # first" here rather than sorting by created_at directly — two
        # uploads in a fast unit test can land on the exact same
        # microsecond timestamp, which real Postgres round-trip latency
        # would never produce, so a created_at sort alone is flaky in
        # this fake specifically.
        candidates = [
            r
            for r in reversed(list(self.resumes.values()))
            if r.tenant_id == tenant_id and r.user_id == user_id and r.deleted_at is None
        ]
        return [replace(r) for r in candidates]

    async def soft_delete(self, tenant_id: uuid.UUID, resume_id: uuid.UUID) -> None:
        resume = self.resumes.get(resume_id)
        if resume and resume.tenant_id == tenant_id:
            self.resumes[resume_id] = replace(resume, deleted_at=datetime.now(UTC))


class FakeStorage:
    def __init__(self) -> None:
        self.uploaded: dict[str, bytes] = {}

    async def upload_private(self, *, key: str, content: bytes, content_type: str) -> None:
        self.uploaded[key] = content

    async def get_presigned_url(self, *, key: str, expires_in_seconds: int = 300) -> str:
        return f"https://example.test/{key}"

    async def delete_private(self, *, key: str) -> None:
        self.uploaded.pop(key, None)


DEFAULT_RESUME_TEXT = (
    "Some resume text. Led migration of monolith to microservices, cutting deploy time 40%.\n"
    "SKILLS\nPython, PostgreSQL"
)


class FakeExtractor:
    def __init__(
        self, *, text: str = DEFAULT_RESUME_TEXT, error: Exception | None = None
    ) -> None:
        self.text = text
        self.error = error

    def extract_text(self, *, content: bytes, content_type: str) -> str:
        if self.error is not None:
            raise self.error
        return self.text


class FakeLLMService:
    def __init__(
        self,
        *,
        reply: str = VALID_LLM_JSON,
        replies: list[str] | None = None,
        error: Exception | None = None,
    ) -> None:
        # `replies` (a queue, one per call, staying on the last entry once
        # exhausted) is for exercising the certifications-undercount retry
        # — a single `reply` can't simulate "first attempt is incomplete,
        # second attempt fixes it" since it's the same string every call.
        self.replies = replies
        self.reply = reply
        self.error = error
        self.calls: list[dict] = []

    async def generate(
        self,
        *,
        use_case: str,
        input_variables: dict[str, str],
        tenant_id: uuid.UUID | None = None,
        user_id: uuid.UUID | None = None,
        max_tokens: int = 1000,
        temperature: float | None = None,
        timeout_seconds: float | None = None,
    ) -> str:
        self.calls.append({"use_case": use_case, "input_variables": input_variables})
        if self.error is not None:
            raise self.error
        if self.replies is not None:
            index = min(len(self.calls) - 1, len(self.replies) - 1)
            return self.replies[index]
        return self.reply


@pytest.fixture
def service() -> tuple[ResumeExtractionService, FakeResumeRepository, FakeStorage, FakeLLMService]:
    resumes = FakeResumeRepository()
    storage = FakeStorage()
    extractor = FakeExtractor()
    llm = FakeLLMService()
    return ResumeExtractionService(resumes, storage, extractor, llm), resumes, storage, llm


@pytest.mark.unit
class TestUploadAndExtract:
    async def test_successful_extraction_is_parsed_with_normalized_data(self, service) -> None:
        svc, _, storage, llm = service
        tenant_id, user_id = uuid.uuid4(), uuid.uuid4()

        resume = await svc.upload_and_extract(
            tenant_id=tenant_id,
            user_id=user_id,
            filename="resume.pdf",
            content=b"%PDF-1.4 fake bytes",
            content_type=PDF_CONTENT_TYPE,
        )

        assert resume.status == "parsed"
        assert resume.error_message is None
        assert resume.extracted_data is not None
        assert resume.extracted_data["headline"] == "Senior Backend Engineer"
        assert resume.extracted_data["skills"] == [
            {"name": "Python", "category": None},
            {"name": "PostgreSQL", "category": "Databases"},
        ]
        assert len(resume.extracted_data["experience"]) == 1
        assert len(resume.extracted_data["career_highlights"]) == 1
        assert resume.extracted_data["career_highlights"][0]["company"] == "Initech"
        assert resume.file_key in storage.uploaded
        assert llm.calls[0]["use_case"] == "resume_extraction"

    async def test_unsupported_content_type_is_rejected_before_upload(self, service) -> None:
        svc, _, storage, _ = service

        with pytest.raises(CareerCompassError) as exc_info:
            await svc.upload_and_extract(
                tenant_id=uuid.uuid4(),
                user_id=uuid.uuid4(),
                filename="resume.txt",
                content=b"plain text",
                content_type="text/plain",
            )

        assert exc_info.value.code == "UNSUPPORTED_RESUME_TYPE"
        assert storage.uploaded == {}

    async def test_oversized_file_is_rejected(self, service) -> None:
        svc, _, _, _ = service

        with pytest.raises(CareerCompassError) as exc_info:
            await svc.upload_and_extract(
                tenant_id=uuid.uuid4(),
                user_id=uuid.uuid4(),
                filename="resume.pdf",
                content=b"x" * (11 * 1024 * 1024),
                content_type=PDF_CONTENT_TYPE,
            )

        assert exc_info.value.code == "RESUME_TOO_LARGE"

    async def test_text_extraction_failure_yields_a_failed_resume_not_a_raise(self) -> None:
        resumes = FakeResumeRepository()
        storage = FakeStorage()
        extractor = FakeExtractor(
            error=CareerCompassError("bad pdf", code="RESUME_TEXT_EXTRACTION_FAILED")
        )
        llm = FakeLLMService()
        svc = ResumeExtractionService(resumes, storage, extractor, llm)

        resume = await svc.upload_and_extract(
            tenant_id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            filename="resume.pdf",
            content=b"garbage",
            content_type=PDF_CONTENT_TYPE,
        )

        assert resume.status == "failed"
        assert resume.error_message == "bad pdf"
        assert resume.extracted_data is None
        # The file is still uploaded to private storage even though parsing failed.
        assert resume.file_key in storage.uploaded

    async def test_empty_extracted_text_yields_a_failed_resume(self) -> None:
        resumes = FakeResumeRepository()
        storage = FakeStorage()
        extractor = FakeExtractor(text="   ")
        llm = FakeLLMService()
        svc = ResumeExtractionService(resumes, storage, extractor, llm)

        resume = await svc.upload_and_extract(
            tenant_id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            filename="resume.pdf",
            content=b"garbage",
            content_type=PDF_CONTENT_TYPE,
        )

        assert resume.status == "failed"
        assert resume.error_message is not None
        assert llm.calls == []  # never reached the LLM call

    async def test_llm_failure_yields_a_failed_resume(self) -> None:
        resumes = FakeResumeRepository()
        storage = FakeStorage()
        extractor = FakeExtractor()
        llm = FakeLLMService(error=CareerCompassError("no key", code="AI_PROVIDER_NOT_CONFIGURED"))
        svc = ResumeExtractionService(resumes, storage, extractor, llm)

        resume = await svc.upload_and_extract(
            tenant_id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            filename="resume.pdf",
            content=b"garbage",
            content_type=PDF_CONTENT_TYPE,
        )

        assert resume.status == "failed"
        assert resume.error_message == "no key"

    async def test_malformed_llm_json_yields_a_failed_resume(self) -> None:
        resumes = FakeResumeRepository()
        storage = FakeStorage()
        extractor = FakeExtractor()
        llm = FakeLLMService(reply="Sure, here's the resume info in prose, no JSON at all.")
        svc = ResumeExtractionService(resumes, storage, extractor, llm)

        resume = await svc.upload_and_extract(
            tenant_id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            filename="resume.pdf",
            content=b"garbage",
            content_type=PDF_CONTENT_TYPE,
        )

        assert resume.status == "failed"

    async def test_markdown_fenced_json_is_still_parsed(self) -> None:
        resumes = FakeResumeRepository()
        storage = FakeStorage()
        extractor = FakeExtractor()
        llm = FakeLLMService(reply=f"```json\n{VALID_LLM_JSON}\n```")
        svc = ResumeExtractionService(resumes, storage, extractor, llm)

        resume = await svc.upload_and_extract(
            tenant_id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            filename="resume.pdf",
            content=b"garbage",
            content_type=PDF_CONTENT_TYPE,
        )

        assert resume.status == "parsed"
        assert resume.extracted_data is not None
        assert resume.extracted_data["headline"] == "Senior Backend Engineer"

    async def test_trailing_commas_are_tolerated(self) -> None:
        """A trailing comma before a closing brace/bracket is a common
        small-model JSON slip — safe to fix mechanically since it never
        changes what the model actually said."""
        resumes = FakeResumeRepository()
        storage = FakeStorage()
        extractor = FakeExtractor()
        reply = """{
          "headline": "Senior Backend Engineer",
          "summary": null,
          "skills": [{"name": "Python", "category": null,}, {"name": "AWS", "category": null},],
          "experience": [],
          "education": [],
          "certifications": [],
        }"""
        llm = FakeLLMService(reply=reply)
        svc = ResumeExtractionService(resumes, storage, extractor, llm)

        resume = await svc.upload_and_extract(
            tenant_id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            filename="resume.pdf",
            content=b"garbage",
            content_type=PDF_CONTENT_TYPE,
        )

        assert resume.status == "parsed"
        assert resume.extracted_data is not None
        assert resume.extracted_data["skills"] == [
            {"name": "Python", "category": None},
            {"name": "AWS", "category": None},
        ]

    async def test_genuinely_broken_json_still_fails_cleanly_with_the_real_error(self) -> None:
        """A missing colon (or other real syntax error) isn't something
        the trailing-comma fixup can or should paper over — it must still
        surface as a clean, retryable failure with the original error,
        not the confusing "fixed" attempt's own new error."""
        resumes = FakeResumeRepository()
        storage = FakeStorage()
        extractor = FakeExtractor()
        llm = FakeLLMService(reply='{"headline" "Missing colon here"}')
        svc = ResumeExtractionService(resumes, storage, extractor, llm)

        resume = await svc.upload_and_extract(
            tenant_id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            filename="resume.pdf",
            content=b"garbage",
            content_type=PDF_CONTENT_TYPE,
        )

        assert resume.status == "failed"
        assert resume.error_message is not None
        assert "not valid JSON" in resume.error_message

    async def test_non_iso_dates_from_a_weaker_model_are_normalized(self) -> None:
        """Real bug caught live: qwen2.5:7b (unlike Claude) doesn't
        reliably follow the prompt's "YYYY-MM-DD" instruction, and
        returned "Apr 2023" for a start_date. Left as-is, that string
        later crashed ResumeResponse's Pydantic validation on the very
        same upload response (a raw 500, not a handled error) — this
        guards against that regressing.
        """
        resumes = FakeResumeRepository()
        storage = FakeStorage()
        extractor = FakeExtractor()
        reply = """{
          "headline": null, "summary": null, "skills": [],
          "experience": [
            {"title": "Engineer", "company": "Acme", "start_date": "Apr 2023",
             "end_date": "2025", "description": null}
          ],
          "education": [
            {"institution": "State University", "start_date": "Sep 2018", "end_date": "2022-05"}
          ],
          "certifications": []
        }"""
        llm = FakeLLMService(reply=reply)
        svc = ResumeExtractionService(resumes, storage, extractor, llm)

        resume = await svc.upload_and_extract(
            tenant_id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            filename="resume.pdf",
            content=b"garbage",
            content_type=PDF_CONTENT_TYPE,
        )

        assert resume.status == "parsed"
        assert resume.extracted_data is not None
        experience = resume.extracted_data["experience"][0]
        assert experience["start_date"] == "2023-04-01"
        assert experience["end_date"] == "2025-01-01"
        education = resume.extracted_data["education"][0]
        assert education["start_date"] == "2018-09-01"
        assert education["end_date"] == "2022-05-01"

    async def test_an_unparseable_date_is_dropped_not_fatal(self) -> None:
        resumes = FakeResumeRepository()
        storage = FakeStorage()
        extractor = FakeExtractor()
        reply = """{
          "headline": null, "summary": null, "skills": [],
          "experience": [
            {"title": "Engineer", "company": "Acme", "start_date": "sometime last year",
             "end_date": null, "description": null}
          ],
          "education": [], "certifications": []
        }"""
        llm = FakeLLMService(reply=reply)
        svc = ResumeExtractionService(resumes, storage, extractor, llm)

        resume = await svc.upload_and_extract(
            tenant_id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            filename="resume.pdf",
            content=b"garbage",
            content_type=PDF_CONTENT_TYPE,
        )

        assert resume.status == "parsed"
        assert resume.extracted_data is not None
        assert resume.extracted_data["experience"][0]["start_date"] is None

    async def test_incomplete_experience_entries_are_dropped_not_fatal(self) -> None:
        resumes = FakeResumeRepository()
        storage = FakeStorage()
        extractor = FakeExtractor()
        reply = """{
          "headline": null, "summary": null, "skills": [],
          "experience": [
            {"title": "Missing company", "company": null},
            {"title": "Engineer", "company": "Acme", "start_date": "2020-01-01", "end_date": null}
          ],
          "education": [], "certifications": []
        }"""
        llm = FakeLLMService(reply=reply)
        svc = ResumeExtractionService(resumes, storage, extractor, llm)

        resume = await svc.upload_and_extract(
            tenant_id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            filename="resume.pdf",
            content=b"garbage",
            content_type=PDF_CONTENT_TYPE,
        )

        assert resume.status == "parsed"
        assert resume.extracted_data is not None
        assert len(resume.extracted_data["experience"]) == 1
        assert resume.extracted_data["experience"][0]["company"] == "Acme"

    async def test_dropped_bullet_markers_are_restored_from_source(self) -> None:
        """Live-observed with Groq's llama-3.3-70b-versatile: the prompt
        has explicit, worked-example instructions to preserve a source
        line's "• " prefix into the description field (the UI renders
        "• "-prefixed lines as an actual bulleted list — see
        ExperienceSection.tsx's DescriptionText) — this holds on some
        models but not others. Groq kept every line's content, order,
        and the newlines between them completely intact, but stripped
        the "• " prefix from every single line, even the ones a
        different model preserved correctly from the exact same prompt.
        Restored deterministically from the resume's own text rather
        than chasing another provider-specific prompt tweak. Mirrors the
        real resume structure that surfaced this: a plain intro line
        with no bullet, followed by genuinely bulleted lines.
        """
        resume_text = (
            "EXPERIENCE\n"
            "Acme Corp | Engineer | Jan 2020 - Present\n"
            "Led a distributed team across three time zones.\n"
            "• Reduced infrastructure spend by 30%.\n"
            "• Shipped three major releases this year.\n"
        )
        description_value = (
            "Led a distributed team across three time zones.\\n"
            "Reduced infrastructure spend by 30%.\\n"
            "Shipped three major releases this year."
        )
        reply = f"""{{
          "headline": null, "summary": null, "skills": [],
          "experience": [
            {{"title": "Engineer", "company": "Acme Corp", "location": null,
             "start_date": "2020-01-01", "end_date": null,
             "description": "{description_value}"}}
          ],
          "education": [], "certifications": []
        }}"""
        resumes = FakeResumeRepository()
        storage = FakeStorage()
        extractor = FakeExtractor(text=resume_text)
        llm = FakeLLMService(reply=reply)
        svc = ResumeExtractionService(resumes, storage, extractor, llm)

        resume = await svc.upload_and_extract(
            tenant_id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            filename="resume.pdf",
            content=b"garbage",
            content_type=PDF_CONTENT_TYPE,
        )

        assert resume.extracted_data is not None
        description = resume.extracted_data["experience"][0]["description"]
        assert description == (
            "Led a distributed team across three time zones.\n"
            "• Reduced infrastructure spend by 30%.\n"
            "• Shipped three major releases this year."
        )

    async def test_wrongly_added_bullet_marker_is_stripped(self) -> None:
        """Live-observed on qwen2.5:3b: a two-role resume where the
        FIRST role was 100% bulleted in the source (no intro line) and
        the SECOND role had a genuine plain intro line before its
        bullets. The model correctly bulleted every line of the first
        role, then over-generalized that pattern onto the second role's
        intro line too — bulleting a line the source never bulleted.
        The earlier, add-only version of this fix couldn't catch this
        at all; it must now be stripped back off.
        """
        resume_text = (
            "EXPERIENCE\n"
            "Acme Corp | Engineer | Jan 2020 - Present\n"
            "Led a distributed team across three time zones on a major platform.\n"
            "• Reduced infrastructure spend by 30% within the first year.\n"
            "• Shipped three major releases across the fiscal year.\n"
        )
        description_value = (
            "• Led a distributed team across three time zones on a major platform.\\n"
            "• Reduced infrastructure spend by 30% within the first year.\\n"
            "• Shipped three major releases across the fiscal year."
        )
        reply = f"""{{
          "headline": null, "summary": null, "skills": [],
          "experience": [
            {{"title": "Engineer", "company": "Acme Corp", "location": null,
             "start_date": "2020-01-01", "end_date": null,
             "description": "{description_value}"}}
          ],
          "education": [], "certifications": []
        }}"""
        resumes = FakeResumeRepository()
        storage = FakeStorage()
        extractor = FakeExtractor(text=resume_text)
        llm = FakeLLMService(reply=reply)
        svc = ResumeExtractionService(resumes, storage, extractor, llm)

        resume = await svc.upload_and_extract(
            tenant_id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            filename="resume.pdf",
            content=b"garbage",
            content_type=PDF_CONTENT_TYPE,
        )

        assert resume.extracted_data is not None
        description = resume.extracted_data["experience"][0]["description"]
        assert description == (
            "Led a distributed team across three time zones on a major platform.\n"
            "• Reduced infrastructure spend by 30% within the first year.\n"
            "• Shipped three major releases across the fiscal year."
        )

    async def test_bullet_restored_despite_a_dropped_trademark_symbol(self) -> None:
        """Real bug caught live: the source line was genuinely bulleted
        and read "...AI-Empowered SAFe® programs...", but the model
        reproduced every actual word correctly while dropping the "®"
        trademark symbol — which broke the exact/substring match this
        restoration relies on, since a plain lowercase+whitespace
        normalization doesn't account for decorative symbols a model can
        silently drop. The bullet must still be restored.
        """
        resume_text = (
            "EXPERIENCE\n"
            "Acme Corp | Engineer | Jan 2020 - Present\n"
            "Some intro line that is long enough to be checked properly here.\n"
            "• Design and deliver AI-Empowered SAFe® programs for enterprise teams.\n"
        )
        description_value = (
            "Some intro line that is long enough to be checked properly here.\\n"
            "Design and deliver AI-Empowered SAFe programs for enterprise teams."
        )
        reply = f"""{{
          "headline": null, "summary": null, "skills": [],
          "experience": [
            {{"title": "Engineer", "company": "Acme Corp", "location": null,
             "start_date": "2020-01-01", "end_date": null,
             "description": "{description_value}"}}
          ],
          "education": [], "certifications": []
        }}"""
        resumes = FakeResumeRepository()
        storage = FakeStorage()
        extractor = FakeExtractor(text=resume_text)
        llm = FakeLLMService(reply=reply)
        svc = ResumeExtractionService(resumes, storage, extractor, llm)

        resume = await svc.upload_and_extract(
            tenant_id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            filename="resume.pdf",
            content=b"garbage",
            content_type=PDF_CONTENT_TYPE,
        )

        assert resume.extracted_data is not None
        description = resume.extracted_data["experience"][0]["description"]
        assert description == (
            "Some intro line that is long enough to be checked properly here.\n"
            "• Design and deliver AI-Empowered SAFe programs for enterprise teams."
        )

    async def test_career_highlights_without_a_title_are_dropped_not_fatal(self) -> None:
        resumes = FakeResumeRepository()
        storage = FakeStorage()
        extractor = FakeExtractor(
            text="Some resume text. Improved flow efficiency by 25%. More text."
        )
        reply = """{
          "headline": null, "summary": null, "skills": [],
          "experience": [], "education": [], "certifications": [],
          "career_highlights": [
            {"title": null, "company": "Acme"},
            {"title": "Improved flow efficiency by 25%.", "company": null,
             "description": null, "occurred_on": null}
          ]
        }"""
        llm = FakeLLMService(reply=reply)
        svc = ResumeExtractionService(resumes, storage, extractor, llm)

        resume = await svc.upload_and_extract(
            tenant_id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            filename="resume.pdf",
            content=b"garbage",
            content_type=PDF_CONTENT_TYPE,
        )

        assert resume.status == "parsed"
        assert resume.extracted_data is not None
        assert len(resume.extracted_data["career_highlights"]) == 1
        assert resume.extracted_data["career_highlights"][0]["title"] == (
            "Improved flow efficiency by 25%."
        )


    async def test_certifications_undercount_triggers_a_retry_that_fixes_it(self) -> None:
        """Real, reproducible live behavior: the exact same prompt against
        the exact same resume extracted all 13 certifications on one call
        and only 11 of 13 on the next (confirmed by directly re-running
        the identical Groq request twice) — genuine model flakiness, not
        a prompt-instruction gap. A first fix attempt (a self-reported
        `certifications_source_item_count` integer) was ALSO verified
        live not to work — the model just echoed the length of what it
        had already written into `certifications`, so the "check" never
        caught anything. The current design asks for a separate
        `certification_names_found` transcription array first; a
        mismatch against `certifications`' actual length triggers one
        retry.
        """
        incomplete_reply = """{
          "headline": null, "summary": null, "skills": [],
          "experience": [], "education": [],
          "certification_names_found": ["PMP", "PMI-ACP", "CSM"],
          "certifications": [{"name": "PMP", "issuing_organization": "PMI"}],
          "career_highlights": []
        }"""
        complete_reply = """{
          "headline": null, "summary": null, "skills": [],
          "experience": [], "education": [],
          "certification_names_found": ["PMP", "PMI-ACP", "CSM"],
          "certifications": [
            {"name": "PMP", "issuing_organization": "PMI"},
            {"name": "PMI-ACP", "issuing_organization": "PMI"},
            {"name": "CSM", "issuing_organization": "Scrum Alliance"}
          ],
          "career_highlights": []
        }"""
        resumes = FakeResumeRepository()
        storage = FakeStorage()
        extractor = FakeExtractor(text="CERTIFICATIONS\nPMP, PMI-ACP, CSM\nEXPERIENCE\nfoo")
        llm = FakeLLMService(replies=[incomplete_reply, complete_reply])
        svc = ResumeExtractionService(resumes, storage, extractor, llm)

        resume = await svc.upload_and_extract(
            tenant_id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            filename="resume.pdf",
            content=b"garbage",
            content_type=PDF_CONTENT_TYPE,
        )

        assert len(llm.calls) == 2  # retried exactly once
        assert resume.status == "parsed"
        assert resume.extracted_data is not None
        assert len(resume.extracted_data["certifications"]) == 3
        # The internal self-check field is never leaked into the data
        # written to the profile/returned over the API.
        assert "certification_names_found" not in resume.extracted_data

    async def test_certifications_count_matching_does_not_retry(self) -> None:
        reply = """{
          "headline": null, "summary": null, "skills": [],
          "experience": [], "education": [],
          "certification_names_found": ["PMP"],
          "certifications": [{"name": "PMP", "issuing_organization": "PMI"}],
          "career_highlights": []
        }"""
        resumes = FakeResumeRepository()
        storage = FakeStorage()
        extractor = FakeExtractor(text="CERTIFICATIONS\nPMP\nEXPERIENCE\nfoo")
        llm = FakeLLMService(reply=reply)
        svc = ResumeExtractionService(resumes, storage, extractor, llm)

        resume = await svc.upload_and_extract(
            tenant_id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            filename="resume.pdf",
            content=b"garbage",
            content_type=PDF_CONTENT_TYPE,
        )

        assert len(llm.calls) == 1  # count matched — no retry needed
        assert resume.status == "parsed"
        assert resume.extracted_data is not None
        assert len(resume.extracted_data["certifications"]) == 1

    async def test_still_incomplete_after_one_retry_is_accepted_not_retried_forever(self) -> None:
        """Never retried more than once — a resume that fails twice in a
        row likely has a genuinely ambiguous certifications section, and
        the second attempt's result is used as-is rather than looping.
        """
        incomplete_reply = """{
          "headline": null, "summary": null, "skills": [],
          "experience": [], "education": [],
          "certification_names_found": ["PMP", "PMI-ACP", "CSM"],
          "certifications": [{"name": "PMP", "issuing_organization": "PMI"}],
          "career_highlights": []
        }"""
        resumes = FakeResumeRepository()
        storage = FakeStorage()
        # Deliberately only "PMP" in the source text (matching the
        # model's own certifications array exactly) — the retry itself
        # is still triggered by the self-reported certification_names_found
        # mismatch (3 vs 1) below, independent of the heuristic source
        # count; keeping the two aligned here isolates this test to the
        # retry-cap behavior alone, without also exercising the separate,
        # already-tested backfill-of-missing-names path.
        extractor = FakeExtractor(text="CERTIFICATIONS\nPMP\nEXPERIENCE\nfoo")
        llm = FakeLLMService(reply=incomplete_reply)
        svc = ResumeExtractionService(resumes, storage, extractor, llm)

        resume = await svc.upload_and_extract(
            tenant_id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            filename="resume.pdf",
            content=b"garbage",
            content_type=PDF_CONTENT_TYPE,
        )

        assert len(llm.calls) == 2  # capped at _MAX_EXTRACTION_ATTEMPTS
        assert resume.status == "parsed"
        assert resume.extracted_data is not None
        assert len(resume.extracted_data["certifications"]) == 1

    async def test_heuristic_parse_of_the_resume_text_alone_triggers_a_retry(self) -> None:
        """Even when the model's own response has no
        `certification_names_found` field at all (an older prompt
        version, or a model that just doesn't produce it — observed live
        on both a weak and a strong model), a real undercount is still
        caught: certification_line_parser.py finds 3 names in the raw
        resume text, the model's response only has 2.
        """
        resume_text = "CERTIFICATIONS\nPMP | CSM | SSGB\nEXPERIENCE\nfoo"
        incomplete_reply = """{
          "headline": null, "summary": null, "skills": [],
          "experience": [], "education": [],
          "certifications": [{"name": "PMP", "issuing_organization": "PMI"}],
          "career_highlights": []
        }"""
        complete_reply = """{
          "headline": null, "summary": null, "skills": [],
          "experience": [], "education": [],
          "certifications": [
            {"name": "PMP", "issuing_organization": "PMI"},
            {"name": "CSM", "issuing_organization": "Scrum Alliance"},
            {"name": "SSGB", "issuing_organization": "ASQ"}
          ],
          "career_highlights": []
        }"""
        resumes = FakeResumeRepository()
        storage = FakeStorage()
        extractor = FakeExtractor(text=resume_text)
        llm = FakeLLMService(replies=[incomplete_reply, complete_reply])
        svc = ResumeExtractionService(resumes, storage, extractor, llm)

        resume = await svc.upload_and_extract(
            tenant_id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            filename="resume.pdf",
            content=b"garbage",
            content_type=PDF_CONTENT_TYPE,
        )

        assert len(llm.calls) == 2  # retried once, based on the heuristic parse alone
        assert resume.extracted_data is not None
        assert len(resume.extracted_data["certifications"]) == 3

    async def test_a_name_still_missing_after_retry_is_backfilled_as_not_specified(
        self,
    ) -> None:
        """A name the model never wrote at all, even after a retry, is
        unioned in afterward with the honest "not specified" issuer —
        deterministic, no extra LLM call. This used to ask a small,
        separate call to infer a real issuer for exactly this kind of
        name; removed after a real, explicitly requested product change
        (see _verified_issuer's docstring): a name reaching this path
        already means no issuer was ever stated for it in the resume's
        own text, so there's nothing legitimate to look up.
        """
        resume_text = (
            "CERTIFICATIONS\nPMP | CSM | Digital Product Management\nEXPERIENCE\nfoo"
        )
        incomplete_reply = """{
          "headline": null, "summary": null, "skills": [],
          "experience": [], "education": [],
          "certifications": [
            {"name": "PMP", "issuing_organization": "PMI"},
            {"name": "CSM", "issuing_organization": "Scrum Alliance"}
          ],
          "career_highlights": []
        }"""
        resumes = FakeResumeRepository()
        storage = FakeStorage()
        extractor = FakeExtractor(text=resume_text)
        # Both extraction attempts return the same incomplete result — a
        # genuinely stubborn miss, no 3rd (backfill) call anymore.
        llm = FakeLLMService(replies=[incomplete_reply, incomplete_reply])
        svc = ResumeExtractionService(resumes, storage, extractor, llm)

        resume = await svc.upload_and_extract(
            tenant_id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            filename="resume.pdf",
            content=b"garbage",
            content_type=PDF_CONTENT_TYPE,
        )

        assert len(llm.calls) == 2  # both are the extraction retry, nothing else
        assert resume.extracted_data is not None
        certifications = resume.extracted_data["certifications"]
        assert len(certifications) == 3
        backfilled = next(c for c in certifications if c["name"] == "Digital Product Management")
        assert backfilled["issuing_organization"] == "Not specified in resume"

    async def test_unstated_issuer_is_overwritten_even_for_well_known_credentials(self) -> None:
        """Live-observed on a real resume that lists certifications as a
        bare flat list with zero issuer information anywhere ("PMP |
        CSM | SSGB | ..."): the model filled in real-world issuers from
        general knowledge for the well-known ones — some correct (PMP ->
        PMI), but at least one factually wrong (the user's actual SSGB
        is from a different organization than the model's guess), with
        nothing distinguishing a right guess from a wrong one. Per an
        explicit product decision after that finding, issuing_organization
        must now come ONLY from what the resume text itself states, no
        matter how well-known the credential — this resume states none,
        so every certification's issuer is overwritten to "Not specified
        in resume" regardless of what the model returned. A genuinely
        resume-stated issuer must still survive.
        """
        resume_text = "CERTIFICATIONS\nPMP | CSM | SSGB\nEXPERIENCE\nfoo"
        reply = """{
          "headline": null, "summary": null, "skills": [],
          "experience": [], "education": [],
          "certifications": [
            {"name": "PMP", "issuing_organization": "PMI (Project Management Institute)"},
            {"name": "CSM", "issuing_organization": "Scrum Alliance"},
            {"name": "SSGB", "issuing_organization": "Six Sigma/ASQ"}
          ],
          "career_highlights": []
        }"""
        resumes = FakeResumeRepository()
        storage = FakeStorage()
        extractor = FakeExtractor(text=resume_text)
        llm = FakeLLMService(reply=reply)
        svc = ResumeExtractionService(resumes, storage, extractor, llm)

        resume = await svc.upload_and_extract(
            tenant_id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            filename="resume.pdf",
            content=b"garbage",
            content_type=PDF_CONTENT_TYPE,
        )

        assert resume.extracted_data is not None
        certifications = resume.extracted_data["certifications"]
        assert len(certifications) == 3
        assert all(c["issuing_organization"] == "Not specified in resume" for c in certifications)

    async def test_null_issuer_gets_the_fallback_not_dropped(self) -> None:
        """Real regression caught live on qwen2.5:3b: a weaker model
        correctly extracted every certification name but wrote null for
        issuing_organization on ALL of them instead of the literal "Not
        specified in resume" string the prompt asks for. The code used
        to require a non-empty issuer just to keep the entry at all —
        with every issuer null, every certification was silently
        dropped, tripping the "all discarded" safety check and failing
        the whole upload outright (a much worse outcome than the
        original bug). Now that "not specified" is the expected common
        case rather than a rare fallback, a missing issuer must not cost
        the certification name itself — it defaults to the honest
        fallback in code instead of depending on the model to write it.
        """
        resume_text = "CERTIFICATIONS\nPMP | CSM\nEXPERIENCE\nfoo"
        reply = """{
          "headline": null, "summary": null, "skills": [],
          "experience": [], "education": [],
          "certifications": [
            {"name": "PMP", "issuing_organization": null},
            {"name": "CSM", "issuing_organization": null}
          ],
          "career_highlights": []
        }"""
        resumes = FakeResumeRepository()
        storage = FakeStorage()
        extractor = FakeExtractor(text=resume_text)
        llm = FakeLLMService(reply=reply)
        svc = ResumeExtractionService(resumes, storage, extractor, llm)

        resume = await svc.upload_and_extract(
            tenant_id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            filename="resume.pdf",
            content=b"garbage",
            content_type=PDF_CONTENT_TYPE,
        )

        assert resume.status == "parsed"  # not "failed" — this is the actual regression
        assert resume.extracted_data is not None
        certifications = resume.extracted_data["certifications"]
        assert len(certifications) == 2
        assert all(c["issuing_organization"] == "Not specified in resume" for c in certifications)

    async def test_issuer_actually_stated_in_the_resume_is_kept(self) -> None:
        """The opposite case: when the resume text itself explicitly
        pairs a certification with an issuer, that stated issuer must
        survive verification, not be discarded along with the inferred
        ones."""
        resume_text = (
            "CERTIFICATIONS\n"
            "PMP - Project Management Institute\n"
            "EXPERIENCE\nfoo"
        )
        reply = """{
          "headline": null, "summary": null, "skills": [],
          "experience": [], "education": [],
          "certifications": [
            {"name": "PMP", "issuing_organization": "Project Management Institute"}
          ],
          "career_highlights": []
        }"""
        resumes = FakeResumeRepository()
        storage = FakeStorage()
        extractor = FakeExtractor(text=resume_text)
        llm = FakeLLMService(reply=reply)
        svc = ResumeExtractionService(resumes, storage, extractor, llm)

        resume = await svc.upload_and_extract(
            tenant_id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            filename="resume.pdf",
            content=b"garbage",
            content_type=PDF_CONTENT_TYPE,
        )

        assert resume.extracted_data is not None
        certifications = resume.extracted_data["certifications"]
        assert len(certifications) == 1
        assert certifications[0]["issuing_organization"] == "Project Management Institute"

    async def test_reversed_skill_name_and_category_are_swapped_back(self) -> None:
        """Live-observed on qwen2.5:3b, and a striking case: the prompt's
        own worked example explicitly shows {"name": "Agile & Scaling",
        "category": "SAFe 6"} as a WRONG output to avoid — the model
        reproduced that exact reversed shape for real, on a resume whose
        real "CORE COMPETENCIES" section genuinely groups skills under
        "Agile & Scaling" as a subheading with several individual skills
        beneath it. Detected without needing the source text at all: a
        subheading legitimately repeats across several skill entries, an
        individual skill name essentially never does — so whichever
        value repeats is treated as the subheading regardless of which
        JSON key the model put it under, and swapped into "category" if
        it was wrongly sitting in "name".
        """
        resume_text = (
            "CORE COMPETENCIES\n"
            "Agile & Scaling: SAFe 6, Lean Portfolio Management, Scrum\n"
            "EXPERIENCE\nfoo"
        )
        reply = """{
          "headline": null, "summary": null,
          "skills": [
            {"name": "Agile & Scaling", "category": "SAFe 6"},
            {"name": "Agile & Scaling", "category": "Lean Portfolio Management"},
            {"name": "Agile & Scaling", "category": "Scrum"}
          ],
          "experience": [], "education": [], "certifications": []
        }"""
        resumes = FakeResumeRepository()
        storage = FakeStorage()
        extractor = FakeExtractor(text=resume_text)
        llm = FakeLLMService(reply=reply)
        svc = ResumeExtractionService(resumes, storage, extractor, llm)

        resume = await svc.upload_and_extract(
            tenant_id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            filename="resume.pdf",
            content=b"garbage",
            content_type=PDF_CONTENT_TYPE,
        )

        assert resume.extracted_data is not None
        skills = resume.extracted_data["skills"]
        assert len(skills) == 3
        assert {s["name"] for s in skills} == {"SAFe 6", "Lean Portfolio Management", "Scrum"}
        assert all(s["category"] == "Agile & Scaling" for s in skills)

    async def test_skill_name_that_happens_to_repeat_without_a_category_is_untouched(
        self,
    ) -> None:
        """A skill name repeated with no category attached at all isn't
        the reversed-subheading pattern (nothing to swap it with) — left
        exactly as the model returned it rather than guessing."""
        resume_text = "SKILLS\nPython, Python, SQL\nEXPERIENCE\nfoo"
        reply = """{
          "headline": null, "summary": null,
          "skills": [
            {"name": "Python", "category": null},
            {"name": "Python", "category": null},
            {"name": "SQL", "category": null}
          ],
          "experience": [], "education": [], "certifications": []
        }"""
        resumes = FakeResumeRepository()
        storage = FakeStorage()
        extractor = FakeExtractor(text=resume_text)
        llm = FakeLLMService(reply=reply)
        svc = ResumeExtractionService(resumes, storage, extractor, llm)

        resume = await svc.upload_and_extract(
            tenant_id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            filename="resume.pdf",
            content=b"garbage",
            content_type=PDF_CONTENT_TYPE,
        )

        assert resume.extracted_data is not None
        skills = resume.extracted_data["skills"]
        assert len(skills) == 3
        assert all(s["name"] == "Python" or s["name"] == "SQL" for s in skills)
        assert all(s["category"] is None for s in skills)

    async def test_no_skills_section_forces_empty_skills_list(self) -> None:
        """Live-observed on a real resume with no Skills/Core
        Competencies heading anywhere (only Executive Summary,
        Certifications, Professional Experience): the model invented a
        "skills" list anyway by mining noun phrases out of the Executive
        Summary's prose and lifting a near-duplicate of a certification
        name — a prompt instruction for this exact failure mode ("empty
        skills array is correct when no dedicated section exists") had
        already been tried and did not hold. Caught deterministically
        now: no heading means the model's entire skills output for this
        resume is discarded, not just the parts that happen to overlap
        certifications (see skills_section_detector.py)."""
        resume_text = "CERTIFICATIONS\nPMP | CSM\nEXPERIENCE\nSome text here."
        reply = """{
          "headline": null, "summary": null,
          "skills": [
            {"name": "PMP", "category": null},
            {"name": "CSM", "category": null},
            {"name": "Stakeholder Management", "category": null}
          ],
          "experience": [], "education": [],
          "certifications": [
            {"name": "PMP", "issuing_organization": "PMI"},
            {"name": "CSM", "issuing_organization": "Scrum Alliance"}
          ],
          "career_highlights": []
        }"""
        resumes = FakeResumeRepository()
        storage = FakeStorage()
        extractor = FakeExtractor(text=resume_text)
        llm = FakeLLMService(reply=reply)
        svc = ResumeExtractionService(resumes, storage, extractor, llm)

        resume = await svc.upload_and_extract(
            tenant_id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            filename="resume.pdf",
            content=b"garbage",
            content_type=PDF_CONTENT_TYPE,
        )

        assert resume.extracted_data is not None
        assert resume.extracted_data["skills"] == []

    async def test_no_certifications_section_forces_empty_certifications_list(self) -> None:
        """Live-observed on a real resume with only a Professional
        Experience section (no Certifications/Licenses heading
        anywhere): the model produced 7 "certifications" that were
        never invented from nothing — they were pulled verbatim out of
        an experience bullet like "Delivered SAFe® certification
        programs, including Leading SAFe, Scrum Master, Product Owner/
        Product Manager, DevOps, and Agile Software Engineer", confusing
        certification programs this person DELIVERS to others with
        certifications this person HOLDS. Caught deterministically, same
        rule as the skills-section gate above: no dedicated
        Certifications heading anywhere means the model's entire
        certifications output for this resume is discarded, reusing
        certification_line_parser's own heading detection.
        """
        resume_text = (
            "PROFESSIONAL EXPERIENCE\n"
            "Acme Corp | Agile Coach | Jan 2020 - Present\n"
            "Delivered SAFe certification programs, including Leading SAFe, "
            "Scrum Master, and Product Owner/Product Manager.\n"
        )
        reply = """{
          "headline": null, "summary": null, "skills": [],
          "experience": [], "education": [],
          "certifications": [
            {"name": "Leading SAFe", "issuing_organization": null},
            {"name": "Scrum Master", "issuing_organization": null},
            {"name": "Product Owner/Product Manager", "issuing_organization": null}
          ],
          "career_highlights": []
        }"""
        resumes = FakeResumeRepository()
        storage = FakeStorage()
        extractor = FakeExtractor(text=resume_text)
        llm = FakeLLMService(reply=reply)
        svc = ResumeExtractionService(resumes, storage, extractor, llm)

        resume = await svc.upload_and_extract(
            tenant_id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            filename="resume.pdf",
            content=b"garbage",
            content_type=PDF_CONTENT_TYPE,
        )

        assert resume.extracted_data is not None
        assert resume.extracted_data["certifications"] == []

    async def test_skills_near_duplicating_a_certification_are_dropped(self) -> None:
        """With a genuine Skills section present (so the no-section rule
        above doesn't apply), a skill entry that's merely a differently-
        worded near-duplicate of a certification name — not an exact
        match — must still be dropped. Real bug caught live: "SAFe 6
        Practice Consultant" (skill) vs. "Advanced SAFe 6 Practice
        Consultant" (certification) slipped through the old exact-match
        check into Core Competencies. A genuinely distinct skill in the
        same list must survive."""
        resume_text = (
            "CERTIFICATIONS\nAdvanced SAFe 6 Practice Consultant\n"
            "SKILLS\nSAFe 6 Practice Consultant, Stakeholder Management\n"
            "EXPERIENCE\nSome text here."
        )
        reply = """{
          "headline": null, "summary": null,
          "skills": [
            {"name": "SAFe 6 Practice Consultant", "category": null},
            {"name": "Stakeholder Management", "category": null}
          ],
          "experience": [], "education": [],
          "certifications": [
            {"name": "Advanced SAFe 6 Practice Consultant",
             "issuing_organization": "Scaled Agile, Inc."}
          ],
          "career_highlights": []
        }"""
        resumes = FakeResumeRepository()
        storage = FakeStorage()
        extractor = FakeExtractor(text=resume_text)
        llm = FakeLLMService(reply=reply)
        svc = ResumeExtractionService(resumes, storage, extractor, llm)

        resume = await svc.upload_and_extract(
            tenant_id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            filename="resume.pdf",
            content=b"garbage",
            content_type=PDF_CONTENT_TYPE,
        )

        assert resume.extracted_data is not None
        assert resume.extracted_data["skills"] == [
            {"name": "Stakeholder Management", "category": None}
        ]

    async def test_short_skill_name_matching_a_certification_is_not_dropped(self) -> None:
        """Real regression caught live on a genuine resume: "LeSS" and
        "SAFe 6" are both legitimately listed as BOTH a Core Competencies
        skill AND (separately) a held certification — a person can know
        a framework/methodology (the skill) and also hold a specific
        credential related to it (the certification), and a resume can
        deliberately mention both. Both got wrongly dropped from
        skills: "LeSS" via an exact name collision with the
        certification "LeSS" itself, "SAFe 6" as a coincidental
        substring of the much longer certification "Advanced SAFe 6
        Practice Consultant". Short names are now exempt from this
        dedup check entirely — a longer, genuinely-duplicated name (see
        the test above) must still be caught.
        """
        resume_text = (
            "CERTIFICATIONS\nAdvanced SAFe 6 Practice Consultant, LeSS\n"
            "SKILLS\nSAFe 6, LeSS, Stakeholder Management\n"
            "EXPERIENCE\nSome text here."
        )
        reply = """{
          "headline": null, "summary": null,
          "skills": [
            {"name": "SAFe 6", "category": null},
            {"name": "LeSS", "category": null},
            {"name": "Stakeholder Management", "category": null}
          ],
          "experience": [], "education": [],
          "certifications": [
            {"name": "Advanced SAFe 6 Practice Consultant",
             "issuing_organization": "Scaled Agile, Inc."},
            {"name": "LeSS", "issuing_organization": "Not specified in resume"}
          ],
          "career_highlights": []
        }"""
        resumes = FakeResumeRepository()
        storage = FakeStorage()
        extractor = FakeExtractor(text=resume_text)
        llm = FakeLLMService(reply=reply)
        svc = ResumeExtractionService(resumes, storage, extractor, llm)

        resume = await svc.upload_and_extract(
            tenant_id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            filename="resume.pdf",
            content=b"garbage",
            content_type=PDF_CONTENT_TYPE,
        )

        assert resume.extracted_data is not None
        skill_names = {s["name"] for s in resume.extracted_data["skills"]}
        assert skill_names == {"SAFe 6", "LeSS", "Stakeholder Management"}

    async def test_career_highlight_not_present_in_source_text_is_dropped(self) -> None:
        """The deterministic backstop for a real observed hallucination:
        the model reproduced this prompt's own fictional worked example
        text almost verbatim instead of leaving the list empty, on a
        resume with no such content at all."""
        resume_text = "JANE DOE\nSUMMARY\nSome real resume content.\nEXPERIENCE\nfoo"
        reply = """{
          "headline": null, "summary": null, "skills": [],
          "experience": [], "education": [], "certifications": [],
          "career_highlights": [
            {"title": "Led a cross-functional redesign that cut onboarding time by 40%.",
             "company": null, "description": null, "occurred_on": null}
          ]
        }"""
        resumes = FakeResumeRepository()
        storage = FakeStorage()
        extractor = FakeExtractor(text=resume_text)
        llm = FakeLLMService(reply=reply)
        svc = ResumeExtractionService(resumes, storage, extractor, llm)

        resume = await svc.upload_and_extract(
            tenant_id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            filename="resume.pdf",
            content=b"garbage",
            content_type=PDF_CONTENT_TYPE,
        )

        assert resume.extracted_data is not None
        assert resume.extracted_data["career_highlights"] == []

    async def test_career_highlight_duplicating_an_experience_bullet_is_dropped(self) -> None:
        """Live-observed: a real bullet correctly extracted into
        "experience" also got duplicated into "career_highlights" as a
        separate entry, despite the prompt explicitly saying not to."""
        resume_text = (
            "JANE DOE\nSUMMARY\ntext\nEXPERIENCE\n"
            "Acme Corp | Engineer\n"
            "Led enterprise transformation across 11 portfolios and 55 teams, "
            "improving delivery maturity."
        )
        reply = """{
          "headline": null, "summary": null, "skills": [],
          "experience": [
            {"title": "Engineer", "company": "Acme Corp", "location": null,
             "start_date": "2020-01-01", "end_date": null,
             "description": "Led enterprise transformation across 11 portfolios and 55 teams, improving delivery maturity."}
          ],
          "education": [], "certifications": [],
          "career_highlights": [
            {"title": "Led enterprise transformation across 11 portfolios and 55 teams, improving delivery maturity.",
             "company": null, "description": null, "occurred_on": null}
          ]
        }"""
        resumes = FakeResumeRepository()
        storage = FakeStorage()
        extractor = FakeExtractor(text=resume_text)
        llm = FakeLLMService(reply=reply)
        svc = ResumeExtractionService(resumes, storage, extractor, llm)

        resume = await svc.upload_and_extract(
            tenant_id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            filename="resume.pdf",
            content=b"garbage",
            content_type=PDF_CONTENT_TYPE,
        )

        assert resume.extracted_data is not None
        assert len(resume.extracted_data["experience"]) == 1
        assert resume.extracted_data["career_highlights"] == []

    async def test_award_line_misplaced_in_career_highlights_is_reclassified(self) -> None:
        """Live-observed on qwen2.5:3b: three genuine "Company - Award
        Name: Description" recognition lines all landed in
        career_highlights as single unsplit strings (company and
        description both null), leaving key_achievements empty even
        though the resume had real award content — despite the prompt's
        own explicit worked example for this exact shape. Reclassified
        deterministically: an unsplit career_highlights entry matching
        that shape is moved to key_achievements with its fields split,
        exactly as Step 2 specifies.
        """
        resume_text = (
            "JANE DOE\nSUMMARY\ntext\nEXPERIENCE\nfoo\n"
            "RECOGNITIONS\n"
            "Bank of America - Honorary Mention: Recognized for training 2,000+ "
            "employees on Agile delivery\n"
        )
        reply = """{
          "headline": null, "summary": null, "skills": [],
          "experience": [], "education": [], "certifications": [],
          "career_highlights": [
            {"title": "Bank of America - Honorary Mention: Recognized for training 2,000+ \
employees on Agile delivery",
             "company": null, "description": null, "occurred_on": null}
          ],
          "key_achievements": []
        }"""
        resumes = FakeResumeRepository()
        storage = FakeStorage()
        extractor = FakeExtractor(text=resume_text)
        llm = FakeLLMService(reply=reply)
        svc = ResumeExtractionService(resumes, storage, extractor, llm)

        resume = await svc.upload_and_extract(
            tenant_id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            filename="resume.pdf",
            content=b"garbage",
            content_type=PDF_CONTENT_TYPE,
        )

        assert resume.extracted_data is not None
        assert resume.extracted_data["career_highlights"] == []
        key_achievements = resume.extracted_data["key_achievements"]
        assert len(key_achievements) == 1
        assert key_achievements[0]["company"] == "Bank of America"
        assert key_achievements[0]["title"] == "Honorary Mention"
        assert (
            key_achievements[0]["description"]
            == "Recognized for training 2,000+ employees on Agile delivery"
        )

    async def test_genuine_plain_highlight_with_a_dash_is_not_reclassified(self) -> None:
        """A genuine plain career_highlights line that happens to
        contain a dash and colon for unrelated reasons — but with an
        overly long "award title" portion — must not be reclassified;
        that length is exactly the signal that it's ordinary sentence
        punctuation, not the company/award/detail structure."""
        resume_text = (
            "JANE DOE\nSUMMARY\ntext\nEXPERIENCE\nfoo\n"
            "HIGHLIGHTS\n"
            "Led a cross-functional redesign - reducing onboarding friction across "
            "every team in the organization: cut setup time from 10 minutes to 2 "
            "minutes company-wide\n"
        )
        reply = """{
          "headline": null, "summary": null, "skills": [],
          "experience": [], "education": [], "certifications": [],
          "career_highlights": [
            {"title": "Led a cross-functional redesign - reducing onboarding friction \
across every team in the organization: cut setup time from 10 minutes to 2 minutes \
company-wide",
             "company": null, "description": null, "occurred_on": null}
          ],
          "key_achievements": []
        }"""
        resumes = FakeResumeRepository()
        storage = FakeStorage()
        extractor = FakeExtractor(text=resume_text)
        llm = FakeLLMService(reply=reply)
        svc = ResumeExtractionService(resumes, storage, extractor, llm)

        resume = await svc.upload_and_extract(
            tenant_id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            filename="resume.pdf",
            content=b"garbage",
            content_type=PDF_CONTENT_TYPE,
        )

        assert resume.extracted_data is not None
        assert resume.extracted_data["key_achievements"] == []
        assert len(resume.extracted_data["career_highlights"]) == 1

    async def test_short_career_highlight_is_not_dropped_by_source_verification(self) -> None:
        """A short candidate is left unverified rather than risking a
        false-positive drop of something real but brief."""
        resume_text = "JANE DOE\nSUMMARY\ntext\nEXPERIENCE\nfoo"
        reply = """{
          "headline": null, "summary": null, "skills": [],
          "experience": [], "education": [], "certifications": [],
          "career_highlights": [
            {"title": "Top performer.", "company": null, "description": null, "occurred_on": null}
          ]
        }"""
        resumes = FakeResumeRepository()
        storage = FakeStorage()
        extractor = FakeExtractor(text=resume_text)
        llm = FakeLLMService(reply=reply)
        svc = ResumeExtractionService(resumes, storage, extractor, llm)

        resume = await svc.upload_and_extract(
            tenant_id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            filename="resume.pdf",
            content=b"garbage",
            content_type=PDF_CONTENT_TYPE,
        )

        assert resume.extracted_data is not None
        assert len(resume.extracted_data["career_highlights"]) == 1

    async def test_null_headline_is_backfilled_from_the_raw_text(self) -> None:
        """The deterministic backstop for the live-observed case: a
        small local model returns headline=null even though the
        resume's own text clearly has one on the line right after the
        name."""
        resume_text = (
            "JANE DOE\n"
            "Senior Data Platform Engineer | Cloud Infrastructure Lead\n"
            "jane@example.com - 555-123-4567\n"
            "SUMMARY\n"
            "Experienced engineer...\n"
        )
        reply = """{
          "headline": null, "summary": "Experienced engineer...", "skills": [],
          "experience": [], "education": [], "certifications": [],
          "career_highlights": []
        }"""
        resumes = FakeResumeRepository()
        storage = FakeStorage()
        extractor = FakeExtractor(text=resume_text)
        llm = FakeLLMService(reply=reply)
        svc = ResumeExtractionService(resumes, storage, extractor, llm)

        resume = await svc.upload_and_extract(
            tenant_id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            filename="resume.pdf",
            content=b"garbage",
            content_type=PDF_CONTENT_TYPE,
        )

        assert resume.extracted_data is not None
        assert (
            resume.extracted_data["headline"]
            == "Senior Data Platform Engineer | Cloud Infrastructure Lead"
        )

    async def test_headline_fallback_is_not_used_when_the_model_already_found_one(self) -> None:
        """The fallback must never override a headline the model DID
        extract, even if it differs (e.g. the model's own phrasing)."""
        resume_text = "JANE DOE\nA Line That Would Also Look Like A Headline\nSUMMARY\ntext\n"
        reply = """{
          "headline": "Model's Own Headline", "summary": null, "skills": [],
          "experience": [], "education": [], "certifications": [],
          "career_highlights": []
        }"""
        resumes = FakeResumeRepository()
        storage = FakeStorage()
        extractor = FakeExtractor(text=resume_text)
        llm = FakeLLMService(reply=reply)
        svc = ResumeExtractionService(resumes, storage, extractor, llm)

        resume = await svc.upload_and_extract(
            tenant_id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            filename="resume.pdf",
            content=b"garbage",
            content_type=PDF_CONTENT_TYPE,
        )

        assert resume.extracted_data is not None
        assert resume.extracted_data["headline"] == "Model's Own Headline"

    async def test_headline_stays_null_when_no_fallback_candidate_exists(self) -> None:
        """A resume that genuinely has no headline line (e.g. straight
        from name into a section heading) must not have one invented."""
        resume_text = "JANE DOE\nSUMMARY\nExperienced engineer...\n"
        reply = """{
          "headline": null, "summary": "Experienced engineer...", "skills": [],
          "experience": [], "education": [], "certifications": [],
          "career_highlights": []
        }"""
        resumes = FakeResumeRepository()
        storage = FakeStorage()
        extractor = FakeExtractor(text=resume_text)
        llm = FakeLLMService(reply=reply)
        svc = ResumeExtractionService(resumes, storage, extractor, llm)

        resume = await svc.upload_and_extract(
            tenant_id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            filename="resume.pdf",
            content=b"garbage",
            content_type=PDF_CONTENT_TYPE,
        )

        assert resume.extracted_data is not None
        assert resume.extracted_data["headline"] is None


@pytest.mark.unit
class TestGetLatestAndDiscard:
    async def test_list_for_current_user_returns_all_uploads_most_recent_first(
        self, service
    ) -> None:
        """Resumes are a real history now, not a single superseded slot —
        a person can keep multiple versions, each tailored to a
        different target role, so every upload stays listed until
        explicitly deleted."""
        svc, _, _, _ = service
        tenant_id, user_id = uuid.uuid4(), uuid.uuid4()

        first = await svc.upload_and_extract(
            tenant_id=tenant_id,
            user_id=user_id,
            filename="a.pdf",
            content=b"a",
            content_type=PDF_CONTENT_TYPE,
        )
        second = await svc.upload_and_extract(
            tenant_id=tenant_id,
            user_id=user_id,
            filename="b.pdf",
            content=b"b",
            content_type=PDF_CONTENT_TYPE,
        )

        resumes = await svc.list_for_current_user(tenant_id=tenant_id, user_id=user_id)
        assert [r.id for r in resumes] == [second.id, first.id]

    async def test_discard_soft_deletes_so_it_no_longer_appears_in_the_list(self, service) -> None:
        svc, _, _, _ = service
        tenant_id, user_id = uuid.uuid4(), uuid.uuid4()

        kept = await svc.upload_and_extract(
            tenant_id=tenant_id,
            user_id=user_id,
            filename="keep.pdf",
            content=b"a",
            content_type=PDF_CONTENT_TYPE,
        )
        discarded = await svc.upload_and_extract(
            tenant_id=tenant_id,
            user_id=user_id,
            filename="discard.pdf",
            content=b"b",
            content_type=PDF_CONTENT_TYPE,
        )
        await svc.discard(tenant_id=tenant_id, user_id=user_id, resume_id=discarded.id)

        resumes = await svc.list_for_current_user(tenant_id=tenant_id, user_id=user_id)
        assert [r.id for r in resumes] == [kept.id]

    async def test_discard_is_idempotent_for_a_nonexistent_or_foreign_resume(self, service) -> None:
        svc, _, _, _ = service
        # Should not raise even though nothing exists at this id.
        await svc.discard(tenant_id=uuid.uuid4(), user_id=uuid.uuid4(), resume_id=uuid.uuid4())

    async def test_get_owned_or_raise_rejects_a_foreign_users_resume(self, service) -> None:
        svc, _, _, _ = service
        tenant_id = uuid.uuid4()
        owner, intruder = uuid.uuid4(), uuid.uuid4()

        resume = await svc.upload_and_extract(
            tenant_id=tenant_id,
            user_id=owner,
            filename="a.pdf",
            content=b"a",
            content_type=PDF_CONTENT_TYPE,
        )

        with pytest.raises(CareerCompassError) as exc_info:
            await svc.get_owned_or_raise(tenant_id=tenant_id, user_id=intruder, resume_id=resume.id)
        assert exc_info.value.code == "RESUME_NOT_FOUND"

    async def test_upload_can_be_tagged_to_a_target_role(self, service) -> None:
        svc, _, _, _ = service
        tenant_id, user_id = uuid.uuid4(), uuid.uuid4()
        target_role_id = uuid.uuid4()

        resume = await svc.upload_and_extract(
            tenant_id=tenant_id,
            user_id=user_id,
            filename="a.pdf",
            content=b"a",
            content_type=PDF_CONTENT_TYPE,
            target_role_id=target_role_id,
        )

        assert resume.target_role_id == target_role_id
