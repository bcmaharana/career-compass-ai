"""LLM provider abstraction.

`LLMProviderInterface` is the contract every AI provider adapter
implements (Anthropic first, in app/adapters/ai_providers/ — wired in
Phase 4). Application services in later phases will depend only on this
interface, never on a specific provider SDK, so switching providers or
models is a configuration change, not a code change.

Phase 0 status: interface + request/response shapes only. No real
provider is called yet — see docs/architecture/ai-platform-architecture.md.
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
    rendered_prompt: str
    input_variables: dict[str, str] = field(default_factory=dict)
    max_tokens: int = 1000


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
