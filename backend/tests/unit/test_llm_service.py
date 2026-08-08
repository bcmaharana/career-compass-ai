"""Unit tests for LLMService — prompt/model resolution, per-provider
dispatch keyed by ModelVersion.provider, and invocation logging."""

from __future__ import annotations

import uuid

import pytest

from app.ai_platform.governance.invocation_logger import InvocationRecord
from app.ai_platform.llm_service.provider_interface import LLMRequest, LLMResponse
from app.ai_platform.llm_service.service import LLMService, ProviderNotConfiguredError
from app.ai_platform.models.registry import ModelVersion
from app.ai_platform.prompts.registry import PromptVersion
from app.core.exceptions import NotFoundError


class FakePromptRegistry:
    def __init__(self, version: PromptVersion) -> None:
        self.version = version
        self.requested_use_cases: list[str] = []

    async def get_active_version(self, *, use_case: str) -> PromptVersion:
        self.requested_use_cases.append(use_case)
        return self.version


class FakeModelRegistry:
    def __init__(self, model: ModelVersion) -> None:
        self.model = model
        self.calls: list[dict] = []

    async def get_active_model(
        self, *, tenant_id: str | None = None, user_id: str | None = None
    ) -> ModelVersion:
        self.calls.append({"tenant_id": tenant_id, "user_id": user_id})
        return self.model


class FakeProvider:
    def __init__(self, *, text: str = "Here's my advice.") -> None:
        self.text = text
        self.requests: list[LLMRequest] = []

    async def generate(self, request: LLMRequest) -> LLMResponse:
        self.requests.append(request)
        return LLMResponse(
            text=self.text,
            prompt_version_id=request.prompt_version_id,
            model_version_id=request.model_version_id,
            input_tokens=42,
            output_tokens=13,
            latency_ms=250.0,
        )


class FakeInvocationLogger:
    def __init__(self) -> None:
        self.records: list[InvocationRecord] = []

    async def log_invocation(self, record: InvocationRecord) -> None:
        self.records.append(record)


def _prompt_version() -> PromptVersion:
    return PromptVersion(
        id=str(uuid.uuid4()),
        name="career_coach_chat",
        version=1,
        template="System: coach.\n{conversation_history}\nUser: {user_message}",
        status="approved",
        owner="platform",
        approved_by="platform",
    )


def _model_version(*, provider: str = "anthropic") -> ModelVersion:
    return ModelVersion(
        id=str(uuid.uuid4()),
        provider=provider,
        model_name="claude-sonnet-5",
        version="1",
        status="active",
        cost_per_1k_tokens=0.006,
        is_default=True,
    )


@pytest.mark.unit
class TestGenerate:
    async def test_renders_template_and_dispatches_to_the_matching_provider(self) -> None:
        prompt = _prompt_version()
        model = _model_version(provider="anthropic")
        prompts = FakePromptRegistry(prompt)
        models = FakeModelRegistry(model)
        anthropic_provider = FakeProvider(text="Great question.")
        invocations = FakeInvocationLogger()
        service = LLMService(
            providers={"anthropic": anthropic_provider},
            prompts=prompts,
            models=models,
            invocations=invocations,
        )
        tenant_id, user_id = uuid.uuid4(), uuid.uuid4()

        result = await service.generate(
            use_case="career_coach_chat",
            input_variables={"conversation_history": "(none)", "user_message": "Hi"},
            tenant_id=tenant_id,
            user_id=user_id,
        )

        assert result == "Great question."
        assert prompts.requested_use_cases == ["career_coach_chat"]
        assert models.calls == [{"tenant_id": str(tenant_id), "user_id": str(user_id)}]

        [request] = anthropic_provider.requests
        assert request.model_name == "claude-sonnet-5"
        assert request.rendered_prompt == "System: coach.\n(none)\nUser: Hi"

    async def test_logs_invocation_with_token_and_latency_from_the_response(self) -> None:
        model = _model_version()
        invocations = FakeInvocationLogger()
        service = LLMService(
            providers={"anthropic": FakeProvider()},
            prompts=FakePromptRegistry(_prompt_version()),
            models=FakeModelRegistry(model),
            invocations=invocations,
        )
        tenant_id, user_id = uuid.uuid4(), uuid.uuid4()

        await service.generate(
            use_case="career_coach_chat",
            input_variables={"conversation_history": "", "user_message": "Hi"},
            tenant_id=tenant_id,
            user_id=user_id,
        )

        [record] = invocations.records
        assert record.model_version_id == model.id
        assert record.input_tokens == 42
        assert record.output_tokens == 13
        assert record.latency_ms == 250.0
        assert record.tenant_id == str(tenant_id)
        assert record.user_id == str(user_id)

    async def test_raises_when_no_provider_is_registered_for_the_models_provider(self) -> None:
        service = LLMService(
            providers={"anthropic": FakeProvider()},
            prompts=FakePromptRegistry(_prompt_version()),
            models=FakeModelRegistry(_model_version(provider="ollama")),
            invocations=FakeInvocationLogger(),
        )

        with pytest.raises(ProviderNotConfiguredError):
            await service.generate(
                use_case="career_coach_chat",
                input_variables={"conversation_history": "", "user_message": "Hi"},
            )

    async def test_propagates_not_found_when_no_prompt_is_approved(self) -> None:
        class RaisingPromptRegistry:
            async def get_active_version(self, *, use_case: str) -> PromptVersion:
                raise NotFoundError("no prompt", code="PROMPT_NOT_FOUND")

        service = LLMService(
            providers={"anthropic": FakeProvider()},
            prompts=RaisingPromptRegistry(),
            models=FakeModelRegistry(_model_version()),
            invocations=FakeInvocationLogger(),
        )

        with pytest.raises(NotFoundError):
            await service.generate(use_case="unknown", input_variables={})
