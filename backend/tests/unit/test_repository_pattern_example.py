"""Repository test pattern (example).

Phase 0 has no real domain entities yet, so this test demonstrates the
pattern future repository tests should follow using
`InMemoryPromptRegistry` as a stand-in "repository-shaped" port: test
against the interface's behavior (found / not found), not against
SQLAlchemy internals. When Phase 1 adds `UserRepository` and a
SQLAlchemy-backed implementation, its unit tests should follow this same
shape, with an in-memory fake substituted for the real database in
`tests/unit/`, and a real-database version of the same test suite living
in `tests/integration/`.
"""

from __future__ import annotations

import pytest

from app.ai_platform.prompts.registry import InMemoryPromptRegistry, PromptVersion
from app.core.exceptions import NotFoundError


@pytest.mark.unit
async def test_get_active_version_returns_registered_prompt() -> None:
    registry = InMemoryPromptRegistry()
    prompt = PromptVersion(
        id="p1",
        name="skill_gap_analysis",
        version=1,
        template="Analyze the gap between {current} and {target}.",
        status="approved",
        owner="career-intelligence-team",
        approved_by="jane.doe",
    )
    registry.register(prompt)

    result = await registry.get_active_version(use_case="skill_gap_analysis")

    assert result == prompt


@pytest.mark.unit
async def test_get_active_version_raises_not_found_for_unknown_use_case() -> None:
    registry = InMemoryPromptRegistry()

    with pytest.raises(NotFoundError) as exc_info:
        await registry.get_active_version(use_case="does_not_exist")

    assert exc_info.value.code == "PROMPT_NOT_FOUND"
