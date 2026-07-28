"""Prompt registry structure.

Prompts are versioned records, never inline strings in application code.
A prompt change is a new version with `status="draft"`, reviewed and
promoted to `status="approved"` before it can be resolved as "active" for
a given use case — never an in-place edit of an approved version.

Phase 0 status: interface + in-memory reference implementation, useful for
tests and for establishing the contract other modules code against. The
real implementation (Phase 4) is backed by the `PromptVersion` database
table defined in the Phase 0 design package's ERD
(docs/architecture/ai-platform-architecture.md).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class PromptVersion:
    id: str
    name: str
    version: int
    template: str
    status: str  # "draft" | "in_review" | "approved" | "deprecated"
    owner: str
    approved_by: str | None = None


class PromptRegistry(Protocol):
    """Contract for resolving the active, approved prompt for a use case."""

    async def get_active_version(self, *, use_case: str) -> PromptVersion:
        """Return the currently approved PromptVersion for a use case.

        Raises app.core.exceptions.NotFoundError if no approved version
        exists for the given use case.
        """
        ...


class InMemoryPromptRegistry:
    """Reference implementation used in tests and local development
    before the real database-backed registry lands in Phase 4.
    """

    def __init__(self) -> None:
        self._versions: dict[str, PromptVersion] = {}

    def register(self, prompt: PromptVersion) -> None:
        self._versions[prompt.name] = prompt

    async def get_active_version(self, *, use_case: str) -> PromptVersion:
        from app.core.exceptions import NotFoundError

        try:
            return self._versions[use_case]
        except KeyError as exc:
            raise NotFoundError(
                f"No approved prompt version registered for use case '{use_case}'",
                code="PROMPT_NOT_FOUND",
            ) from exc
