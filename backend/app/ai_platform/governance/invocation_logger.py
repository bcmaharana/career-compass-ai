"""AI invocation logging structure.

Every LLM invocation must be logged with enough detail to answer "what
was asked, what generated the answer, and what did it cost" after the
fact. This is the hook point evaluations and bias-check batch jobs
(Phase 3+) will read from.

Phase 0 status: interface + structlog-backed reference implementation.
The real implementation (Phase 4) additionally persists to the
`AIConversation` / lineage fields on `Recommendation` described in the
Phase 0 design package's ERD.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from app.core.logging import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class InvocationRecord:
    prompt_version_id: str
    model_version_id: str
    input_tokens: int
    output_tokens: int
    latency_ms: float
    tenant_id: str | None = None
    user_id: str | None = None


class InvocationLogger(Protocol):
    """Contract for recording an AI invocation for governance/observability."""

    async def log_invocation(self, record: InvocationRecord) -> None: ...


class StructlogInvocationLogger:
    """Reference implementation: writes invocation records to structured
    logs. Sufficient for Phase 0 tests and local development; Phase 4
    adds a database-backed implementation for durable, queryable history.
    """

    async def log_invocation(self, record: InvocationRecord) -> None:
        logger.info(
            "ai_invocation",
            prompt_version_id=record.prompt_version_id,
            model_version_id=record.model_version_id,
            input_tokens=record.input_tokens,
            output_tokens=record.output_tokens,
            latency_ms=record.latency_ms,
            tenant_id=record.tenant_id,
            user_id=record.user_id,
        )
