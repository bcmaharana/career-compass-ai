"""Embedding provider abstraction.

`EmbeddingProviderInterface` is the contract every embedding provider
adapter implements — mirrors `app/ai_platform/llm_service/provider_interface.py`'s
`LLMProviderInterface` pattern (application services depend only on
this interface, never a specific provider SDK, so switching providers
or models is a configuration change, not a code change).

Deliberately simpler than `LLMRequest`/`LLMResponse`: there's no
prompt/model registry resolution step and no per-invocation governance
logging requirement for embeddings the way there is for chat (see
`app/ai_platform/governance/invocation_logger.py`) — a plain method
taking primitive types is enough. `EmbeddingIndexingService`
(app/application/career_intelligence/embedding_service.py) is the one
caller, and it already knows which model to ask for via
`Settings.cikg_embedding_model`.

Phase 4.5.1 MVP 2A status: real Ollama adapter lives in
app/adapters/ai_providers/ollama_embedding_provider.py. No paid
provider is wired yet — see cikg-mvp-roadmap.md's MVP 2A scope ("the
Ollama-based free embedding path first... no new paid vendor needed").
"""

from __future__ import annotations

from typing import Protocol


class EmbeddingProviderInterface(Protocol):
    """Contract every concrete embedding provider adapter must implement."""

    async def embed(self, *, texts: list[str], model_name: str) -> list[list[float]]:
        """Return one embedding vector per input text, in the same order.

        Raises app.core.exceptions.CareerCompassError (or a subclass) on
        failure — provider-specific exceptions must be translated at the
        adapter boundary, never leaked to callers. Callers (SearchService)
        must be prepared for this to raise and degrade gracefully rather
        than treat it as always-available.
        """
        ...
