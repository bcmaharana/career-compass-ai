"""Unit tests for JdTailoringSessionService — fake repositories/LLM, no
database, no real LLM calls. Mirrors the fake pattern established in
tests/unit/test_interview_answer_service.py.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest

from app.adapters.documents.resume_data import ResumeData
from app.application.jd_tailoring.jd_tailoring_session_service import (
    JdTailoringSessionService,
    _strip_markdown_formatting,
)
from app.core.exceptions import CareerCompassError, NotFoundError
from app.domain.career_profile.entities import CareerProfile, CoreCompetency, Experience
from app.domain.identity.entities import User
from app.domain.jd_tailoring.entities import JdTailoringMessage, JdTailoringSession

pytestmark = pytest.mark.unit


class FakeJdTailoringSessionRepository:
    def __init__(self) -> None:
        self.sessions: dict[uuid.UUID, JdTailoringSession] = {}

    async def create(self, session: JdTailoringSession) -> JdTailoringSession:
        self.sessions[session.id] = session
        return session

    async def get_by_id(self, tenant_id: uuid.UUID, session_id: uuid.UUID) -> JdTailoringSession | None:
        s = self.sessions.get(session_id)
        return s if s and s.tenant_id == tenant_id else None

    async def get_by_source_provider_id(self, tenant_id, user_id, provider_id):
        raise NotImplementedError("not exercised by these tests")

    async def list_for_user(self, tenant_id: uuid.UUID, user_id: uuid.UUID) -> list[JdTailoringSession]:
        return [
            s for s in self.sessions.values() if s.tenant_id == tenant_id and s.user_id == user_id
        ]

    async def update(self, session: JdTailoringSession) -> JdTailoringSession:
        self.sessions[session.id] = session
        return session

    async def soft_delete(self, tenant_id: uuid.UUID, session_id: uuid.UUID) -> None:
        self.sessions.pop(session_id, None)


class FakeJdTailoringMessageRepository:
    def __init__(self) -> None:
        self.messages: list[JdTailoringMessage] = []

    async def create(self, message: JdTailoringMessage) -> JdTailoringMessage:
        self.messages.append(message)
        return message

    async def list_by_session(self, tenant_id: uuid.UUID, session_id: uuid.UUID) -> list[JdTailoringMessage]:
        return [m for m in self.messages if m.tenant_id == tenant_id and m.session_id == session_id]


def _make_profile(*, tenant_id: uuid.UUID, user_id: uuid.UUID, **overrides) -> CareerProfile:
    now = datetime.now(UTC)
    defaults: dict[str, object] = dict(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        user_id=user_id,
        current_version=1,
        headline=None,
        summary=None,
        career_readiness_score=None,
        photo_url=None,
        core_competencies=[],
        created_at=now,
        updated_at=now,
    )
    defaults.update(overrides)
    return CareerProfile(**defaults)  # type: ignore[arg-type]


def _make_user(*, tenant_id: uuid.UUID) -> User:
    now = datetime.now(UTC)
    return User(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        org_id=None,
        email="jordan@example.com",
        salutation=None,
        first_name="Jordan",
        last_name="Rivera",
        hashed_password="x",
        status="active",
        mfa_enabled=False,
        created_at=now,
        updated_at=now,
    )


def _make_experience(*, tenant_id: uuid.UUID, career_profile_id: uuid.UUID, **overrides) -> Experience:
    now = datetime.now(UTC)
    defaults: dict[str, object] = dict(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        career_profile_id=career_profile_id,
        title="Engineer",
        company="Acme",
        location=None,
        start_date=None,
        end_date=None,
        description="Built things.",
        display_order=1,
        created_at=now,
        updated_at=now,
    )
    defaults.update(overrides)
    return Experience(**defaults)  # type: ignore[arg-type]


def _make_resume_data(*, tenant_id: uuid.UUID, user_id: uuid.UUID, **profile_overrides) -> ResumeData:
    profile = _make_profile(tenant_id=tenant_id, user_id=user_id, **profile_overrides)
    return ResumeData(
        profile=profile,
        user=_make_user(tenant_id=tenant_id),
        experiences=[],
        educations=[],
        certifications=[],
        career_highlights=[],
        key_achievements=[],
        career_goals=[],
        recommendations=[],
        role_label=None,
    )


class FakeResumeExportService:
    """Stands in for ResumeExportService.gather_resume_data_with_master_fallback
    — the fallback logic itself (falling back to Master when a Target
    Role Profile is unpopulated) is unit-tested directly against the
    real ResumeExportService in test_resume_export_service.py; this
    fake just returns whatever ResumeData was configured, or raises
    NotFoundError to exercise the "no profile at all yet" degrade path.
    """

    def __init__(self, data: ResumeData | None = None, raise_not_found: bool = False) -> None:
        self._data = data
        self._raise_not_found = raise_not_found
        self.calls: list[uuid.UUID | None] = []

    async def gather_resume_data_with_master_fallback(self, *, tenant_id, user_id, target_role_id):
        self.calls.append(target_role_id)
        if self._raise_not_found or self._data is None:
            raise NotFoundError("Career profile not found.", code="CAREER_PROFILE_NOT_FOUND")
        return self._data.profile, self._data


class FakeLLMService:
    def __init__(self, response_text: str | None = None, fail: bool = False) -> None:
        self._response_text = response_text
        self._fail = fail
        self.call_count = 0
        self.last_input_variables: dict[str, str] | None = None

    async def generate(
        self,
        *,
        use_case: str,
        input_variables: dict[str, str],
        tenant_id=None,
        user_id=None,
        max_tokens: int = 1000,
        temperature: float | None = None,
        timeout_seconds: float | None = None,
    ) -> str:
        self.call_count += 1
        self.last_input_variables = input_variables
        if self._fail:
            raise CareerCompassError("simulated provider failure")
        return self._response_text or "A sample reply."


def _service(
    llm: FakeLLMService | None = None, resume_export: FakeResumeExportService | None = None
):
    sessions_repo = FakeJdTailoringSessionRepository()
    messages_repo = FakeJdTailoringMessageRepository()
    return (
        JdTailoringSessionService(
            sessions_repo,
            messages_repo,
            resume_export or FakeResumeExportService(raise_not_found=True),
            llm or FakeLLMService(),
        ),
        sessions_repo,
        messages_repo,
    )


class TestStartSession:
    async def test_start_from_listing_snapshots_listing_fields(self) -> None:
        service, _, _ = _service()
        tenant_id, user_id = uuid.uuid4(), uuid.uuid4()

        session = await service.start_from_listing(
            tenant_id=tenant_id,
            user_id=user_id,
            target_role_id=None,
            provider_id="adzuna-1",
            title="Engineer",
            company="Acme",
            redirect_url="https://example.com/job/1",
            jd_text="We need a great engineer.",
        )

        assert session.source_type == "job_listing"
        assert session.source_provider_id == "adzuna-1"
        assert session.jd_text == "We need a great engineer."

    async def test_start_custom_has_no_listing_only_fields(self) -> None:
        service, _, _ = _service()
        tenant_id, user_id = uuid.uuid4(), uuid.uuid4()

        session = await service.start_custom(
            tenant_id=tenant_id,
            user_id=user_id,
            target_role_id=None,
            jd_text="Custom JD text.",
            company="Globex",
            role_title="Engineer",
        )

        assert session.source_type == "custom"
        # source_title/source_company ARE set for a custom session too
        # (see the entity docstring) — only the listing-only fields stay
        # unset.
        assert session.source_title == "Engineer"
        assert session.source_company == "Globex"
        assert session.source_provider_id is None
        assert session.source_redirect_url is None


class TestOwnership:
    async def test_cannot_access_another_users_session(self) -> None:
        service, _, _ = _service()
        tenant_id = uuid.uuid4()
        owner, other = uuid.uuid4(), uuid.uuid4()
        session = await service.start_custom(
            tenant_id=tenant_id,
            user_id=owner,
            target_role_id=None,
            jd_text="JD",
            company="Globex",
            role_title="Engineer",
        )

        with pytest.raises(NotFoundError):
            await service.get_owned_or_raise(tenant_id=tenant_id, user_id=other, session_id=session.id)


class TestSendMessage:
    async def test_sends_and_persists_both_messages(self) -> None:
        # Deliberately no leading/trailing whitespace in the fixture
        # response — send_message() mirrors ChatService's own
        # _generate_reply, which returns the LLM's text as-is (unlike
        # InterviewAnswerService, which strips it), so this asserts the
        # actual, correct contract rather than assuming stripping.
        llm = FakeLLMService(response_text="Here's my assessment...")
        service, _, messages_repo = _service(llm)
        tenant_id, user_id = uuid.uuid4(), uuid.uuid4()
        session = await service.start_custom(
            tenant_id=tenant_id,
            user_id=user_id,
            target_role_id=None,
            jd_text="JD text",
            company="Globex",
            role_title="Engineer",
        )

        turn = await service.send_message(
            tenant_id=tenant_id, user_id=user_id, session_id=session.id, content="How do I match?"
        )

        assert turn.user_message.content == "How do I match?"
        assert turn.assistant_message.content == "Here's my assessment..."
        assert len(messages_repo.messages) == 2
        assert llm.call_count == 1

    async def test_grounds_the_prompt_in_the_jd_text_and_profile(self) -> None:
        llm = FakeLLMService()
        # Default fake resume_export raises NotFoundError (no profile
        # at all yet) — grounding with an empty context is itself a
        # real, exercised degrade path (see the try/except NotFoundError
        # in _generate_reply).
        service, sessions_repo, _ = _service(llm)
        tenant_id, user_id = uuid.uuid4(), uuid.uuid4()
        session = await service.start_custom(
            tenant_id=tenant_id,
            user_id=user_id,
            target_role_id=None,
            jd_text="A specific JD.",
            company="Globex",
            role_title="Engineer",
        )

        await service.send_message(
            tenant_id=tenant_id, user_id=user_id, session_id=session.id, content="Question"
        )

        assert llm.last_input_variables is not None
        assert llm.last_input_variables["jd_text"] == "A specific JD."
        assert llm.last_input_variables["user_message"] == "Question"

    async def test_profile_context_includes_real_experience_facts_not_just_headline(
        self,
    ) -> None:
        # Confirmed live (2026-08-19): headline + competency names alone
        # gave the model nothing concrete to reference, and it invented
        # specific years/employers/certifications anyway. Real
        # Experience/Education/Certification facts must actually reach
        # the prompt.
        tenant_id, user_id = uuid.uuid4(), uuid.uuid4()
        data = _make_resume_data(
            tenant_id=tenant_id,
            user_id=user_id,
            headline="Senior Backend Engineer",
            core_competencies=[
                CoreCompetency(name="Python", category=None),
                CoreCompetency(name="Kubernetes", category=None),
            ],
        )
        data.experiences.append(
            _make_experience(
                tenant_id=tenant_id,
                career_profile_id=data.profile.id,
                title="Staff Engineer",
                company="Acme Corp",
                description="Led a payments platform migration.",
            )
        )
        llm = FakeLLMService()
        service, _, _ = _service(llm, resume_export=FakeResumeExportService(data))
        session = await service.start_custom(
            tenant_id=tenant_id,
            user_id=user_id,
            target_role_id=None,
            jd_text="JD",
            company="Globex",
            role_title="Engineer",
        )

        await service.send_message(
            tenant_id=tenant_id, user_id=user_id, session_id=session.id, content="How do I fit?"
        )

        assert llm.last_input_variables is not None
        context = llm.last_input_variables["profile_context"]
        assert "Senior Backend Engineer" in context
        assert "Python" in context and "Kubernetes" in context
        assert "Staff Engineer at Acme Corp" in context
        assert "Led a payments platform migration" in context
        assert "ONLY information you have" in context

    async def test_no_profile_data_produces_an_empty_context_not_an_error(self) -> None:
        llm = FakeLLMService()
        service, _, _ = _service(llm, resume_export=FakeResumeExportService(raise_not_found=True))
        tenant_id, user_id = uuid.uuid4(), uuid.uuid4()
        session = await service.start_custom(
            tenant_id=tenant_id,
            user_id=user_id,
            target_role_id=None,
            jd_text="JD",
            company="Globex",
            role_title="Engineer",
        )

        await service.send_message(
            tenant_id=tenant_id, user_id=user_id, session_id=session.id, content="Hi"
        )

        assert llm.last_input_variables is not None
        assert llm.last_input_variables["profile_context"] == ""

    async def test_passes_the_sessions_target_role_id_through_to_gather(self) -> None:
        tenant_id, user_id = uuid.uuid4(), uuid.uuid4()
        target_role_id = uuid.uuid4()
        resume_export = FakeResumeExportService(
            _make_resume_data(tenant_id=tenant_id, user_id=user_id)
        )
        service, _, _ = _service(resume_export=resume_export)
        session = await service.start_custom(
            tenant_id=tenant_id,
            user_id=user_id,
            target_role_id=target_role_id,
            jd_text="JD",
            company="Globex",
            role_title="Engineer",
        )

        await service.send_message(
            tenant_id=tenant_id, user_id=user_id, session_id=session.id, content="Hi"
        )

        assert resume_export.calls == [target_role_id]

    async def test_llm_failure_degrades_to_a_fallback_reply_without_raising(self) -> None:
        llm = FakeLLMService(fail=True)
        service, _, messages_repo = _service(llm)
        tenant_id, user_id = uuid.uuid4(), uuid.uuid4()
        session = await service.start_custom(
            tenant_id=tenant_id,
            user_id=user_id,
            target_role_id=None,
            jd_text="JD",
            company="Globex",
            role_title="Engineer",
        )

        turn = await service.send_message(
            tenant_id=tenant_id, user_id=user_id, session_id=session.id, content="Hello"
        )

        assert "trouble reaching the AI" in turn.assistant_message.content
        # The user's message is still persisted even though the LLM failed.
        assert any(m.content == "Hello" for m in messages_repo.messages)

    async def test_strips_markdown_the_model_still_slips_in_despite_the_prompt(self) -> None:
        # Confirmed live (2026-08-19): the prompt instructs plain text,
        # but a real reply still contained a "### Gaps..." header even
        # though it correctly avoided ** bold and tables that time.
        raw = (
            "Some prose.\n\n"
            "### Gaps you should watch for\n"
            "- No formal certification\n\n"
            "**Overall fit:** strong"
        )
        llm = FakeLLMService(response_text=raw)
        service, _, _ = _service(llm)
        tenant_id, user_id = uuid.uuid4(), uuid.uuid4()
        session = await service.start_custom(
            tenant_id=tenant_id,
            user_id=user_id,
            target_role_id=None,
            jd_text="JD",
            company="Globex",
            role_title="Engineer",
        )

        turn = await service.send_message(
            tenant_id=tenant_id, user_id=user_id, session_id=session.id, content="Hi"
        )

        assert "#" not in turn.assistant_message.content
        assert "**" not in turn.assistant_message.content
        assert "Gaps you should watch for" in turn.assistant_message.content
        assert "Overall fit: strong" in turn.assistant_message.content


class TestStripMarkdownFormatting:
    def test_strips_headers(self) -> None:
        assert _strip_markdown_formatting("### A header\nBody text") == "A header\nBody text"

    def test_strips_bold_and_bold_underscore(self) -> None:
        assert _strip_markdown_formatting("This is **bold** and __also bold__.") == (
            "This is bold and also bold."
        )

    def test_strips_horizontal_rules(self) -> None:
        assert _strip_markdown_formatting("Above\n---\nBelow") == "Above\n\nBelow"

    def test_strips_table_separator_row_and_flattens_pipes(self) -> None:
        raw = "| A | B |\n|---|---|\n| 1 | 2 |"
        result = _strip_markdown_formatting(raw)
        assert "---" not in result
        assert "A" in result and "B" in result and "1" in result and "2" in result

    def test_leaves_plain_text_untouched(self) -> None:
        assert _strip_markdown_formatting("Just plain prose, nothing special.") == (
            "Just plain prose, nothing special."
        )
