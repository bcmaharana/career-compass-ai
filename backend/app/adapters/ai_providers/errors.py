"""Shared error type for AI provider adapters (Anthropic, Ollama, ...).

Lives here rather than in any one provider module so adapters don't
depend on each other just to share an exception class.
"""

from __future__ import annotations

from app.core.exceptions import CareerCompassError


class AIProviderError(CareerCompassError):
    """Raised when the underlying provider call fails or isn't
    configured — callers (LLMService's callers) should treat this as a
    recoverable, user-facing-degradable failure, not a 500."""

    code = "AI_PROVIDER_ERROR"
