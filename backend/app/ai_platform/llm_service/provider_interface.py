"""LLM provider abstraction.

`LLMProviderInterface` is the contract every AI provider adapter
implements. Application services depend only on this interface (via
app/ai_platform/llm_service/service.py's LLMService), never on a
specific provider SDK, so switching providers or models is a
configuration change, not a code change.

Phase 4 status: real Anthropic adapter lives in
app/adapters/ai_providers/anthropic_provider.py — see
docs/architecture/ai-platform-architecture.md. `model_name` is the
literal provider model string (e.g. "claude-sonnet-5"), resolved from
the active ModelVersion by LLMService — the provider adapter itself
never chooses it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


@dataclass(frozen=True, slots=True)
class LLMRequest:
    """A single request to the LLM service.

    `prompt_version_id` and `model_version_id` are resolved by the prompt
    and model registries (see ../prompts/registry.py and
    ../models/registry.py) before this request is built — the provider
    adapter never chooses these itself.
    """

    prompt_version_id: str
    model_version_id: str
    model_name: str
    rendered_prompt: str
    input_variables: dict[str, str] = field(default_factory=dict)
    max_tokens: int = 1000
    # None means "use the provider's own default" (chat wants some
    # warmth/variety in its replies, so it never sets this). Structured
    # extraction use cases pass 0.0 instead — correctness matters more
    # than variety there, and non-zero sampling was observed live to
    # make a small local model (qwen2.5:7b) inconsistently omit fields
    # (e.g. a resume's headline) that a deterministic pass reliably caught.
    temperature: float | None = None
    # None means "use the provider's own default" — OllamaProvider's is
    # 600s. Resume extraction overrides this explicitly: a long resume
    # plus a longer, more detailed prompt (added to fix skill/category
    # extraction quality) pushed a real qwen2.5:7b run past 600s (observed
    # live taking somewhere between 900s and 1800s) — the same class of
    # "local CPU inference is slow" problem that already forced 180s to
    # 600s once before, not a new kind of issue. A per-request override
    # avoids raising the default for every use case (a hung chat request
    # has no reason to wait 30 minutes) just to accommodate this one.
    timeout_seconds: float | None = None


@dataclass(frozen=True, slots=True)
class LLMResponse:
    """The result of an LLM invocation, including the metadata the
    governance module needs to log (see ../governance/invocation_logger.py).
    """

    text: str
    prompt_version_id: str
    model_version_id: str
    input_tokens: int
    output_tokens: int
    latency_ms: float


class LLMProviderInterface(Protocol):
    """Contract every concrete AI provider adapter must implement."""

    async def generate(self, request: LLMRequest) -> LLMResponse:
        """Send a request to the underlying model provider and return a
        normalized response.

        Raises app.core.exceptions.CareerCompassError (or a subclass) on
        failure — provider-specific exceptions must be translated at the
        adapter boundary, never leaked to callers.
        """
        ...
