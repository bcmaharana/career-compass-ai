"""Unit tests for JdExtractionService — fake LLM, no real calls."""

from __future__ import annotations

import uuid

import pytest

from app.application.jd_tailoring.jd_extraction_service import JdExtractionService
from app.core.exceptions import CareerCompassError

pytestmark = pytest.mark.unit


class FakeLLMService:
    def __init__(self, response_text: str | None = None, fail: bool = False) -> None:
        self._response_text = response_text
        self._fail = fail

    async def generate(self, *, use_case: str, input_variables: dict[str, str], **kwargs) -> str:
        if self._fail:
            raise CareerCompassError("simulated provider failure")
        return self._response_text or "{}"


class TestExtract:
    async def test_parses_a_clean_json_response(self) -> None:
        llm = FakeLLMService(response_text='{"company": "Acme", "role_title": "Engineer"}')
        service = JdExtractionService(llm)

        result = await service.extract(
            tenant_id=uuid.uuid4(), user_id=uuid.uuid4(), jd_text="We are Acme, hiring an Engineer."
        )

        assert result.company == "Acme"
        assert result.role_title == "Engineer"

    async def test_parses_a_fenced_json_response(self) -> None:
        llm = FakeLLMService(response_text='```json\n{"company": "Acme", "role_title": null}\n```')
        service = JdExtractionService(llm)

        result = await service.extract(tenant_id=uuid.uuid4(), user_id=uuid.uuid4(), jd_text="JD")

        assert result.company == "Acme"
        assert result.role_title is None

    async def test_llm_failure_degrades_to_nulls_without_raising(self) -> None:
        llm = FakeLLMService(fail=True)
        service = JdExtractionService(llm)

        result = await service.extract(tenant_id=uuid.uuid4(), user_id=uuid.uuid4(), jd_text="JD")

        assert result.company is None
        assert result.role_title is None

    async def test_malformed_json_degrades_to_nulls_without_raising(self) -> None:
        llm = FakeLLMService(response_text="not json at all")
        service = JdExtractionService(llm)

        result = await service.extract(tenant_id=uuid.uuid4(), user_id=uuid.uuid4(), jd_text="JD")

        assert result.company is None
        assert result.role_title is None
