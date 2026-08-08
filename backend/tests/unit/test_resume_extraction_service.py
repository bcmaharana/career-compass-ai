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


class FakeExtractor:
    def __init__(self, *, text: str = "Some resume text", error: Exception | None = None) -> None:
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

    async def test_career_highlights_without_a_title_are_dropped_not_fatal(self) -> None:
        resumes = FakeResumeRepository()
        storage = FakeStorage()
        extractor = FakeExtractor()
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
        extractor = FakeExtractor()
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
        extractor = FakeExtractor()
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
        extractor = FakeExtractor()
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

    async def test_a_name_still_missing_after_retry_is_backfilled_via_a_separate_call(
        self,
    ) -> None:
        """The real fix for the live-observed failure: a name the model
        never wrote at all, even after a retry, is unioned in afterward
        via a small, separate issuer-inference call — rather than being
        silently lost the way it was before this existed.
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
        backfill_reply = '{"Digital Product Management": "Product School"}'
        resumes = FakeResumeRepository()
        storage = FakeStorage()
        extractor = FakeExtractor(text=resume_text)
        # Both extraction attempts return the same incomplete result (a
        # genuinely stubborn miss), then the 3rd call is the backfill.
        llm = FakeLLMService(replies=[incomplete_reply, incomplete_reply, backfill_reply])
        svc = ResumeExtractionService(resumes, storage, extractor, llm)

        resume = await svc.upload_and_extract(
            tenant_id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            filename="resume.pdf",
            content=b"garbage",
            content_type=PDF_CONTENT_TYPE,
        )

        assert len(llm.calls) == 3  # 2 extraction attempts + 1 backfill call
        assert llm.calls[2]["use_case"] == "resume_certification_issuer_backfill"
        assert resume.extracted_data is not None
        certifications = resume.extracted_data["certifications"]
        assert len(certifications) == 3
        backfilled = next(c for c in certifications if c["name"] == "Digital Product Management")
        assert backfilled["issuing_organization"] == "Product School"

    async def test_backfill_failure_does_not_fail_the_whole_resume(self) -> None:
        """The bonus enrichment step is best-effort — a provider error
        on the small backfill call must not turn an otherwise-successful
        extraction into a failed resume."""
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

        class FlakyOnThirdCallLLM(FakeLLMService):
            async def generate(self, **kwargs):  # type: ignore[no-untyped-def]
                if len(self.calls) == 2:  # about to be the 3rd (backfill) call
                    self.calls.append({"use_case": kwargs["use_case"], "input_variables": {}})
                    raise CareerCompassError("provider down", code="AI_PROVIDER_REQUEST_FAILED")
                return await super().generate(**kwargs)

        resumes = FakeResumeRepository()
        storage = FakeStorage()
        extractor = FakeExtractor(text=resume_text)
        llm = FlakyOnThirdCallLLM(replies=[incomplete_reply, incomplete_reply])
        svc = ResumeExtractionService(resumes, storage, extractor, llm)

        resume = await svc.upload_and_extract(
            tenant_id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            filename="resume.pdf",
            content=b"garbage",
            content_type=PDF_CONTENT_TYPE,
        )

        assert resume.status == "parsed"  # not "failed" — backfill errors are swallowed
        assert resume.extracted_data is not None
        assert len(resume.extracted_data["certifications"]) == 2  # missing name just not added


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
