"""Service layer test pattern (example).

Demonstrates testing a service against its declared dependencies (here,
an `InvocationLogger` port) using a fake, rather than mocking internals.
Future application services (Phase 1 onward) should follow this same
shape: construct the service with fake repository/adapter
implementations, call it, and assert on observable behavior — never
reach into private attributes.
"""

from __future__ import annotations

import pytest

from app.ai_platform.governance.invocation_logger import InvocationRecord


class FakeInvocationLogger:
    """A minimal test double satisfying the InvocationLogger protocol."""

    def __init__(self) -> None:
        self.logged: list[InvocationRecord] = []

    async def log_invocation(self, record: InvocationRecord) -> None:
        self.logged.append(record)


@pytest.mark.unit
async def test_fake_invocation_logger_records_calls() -> None:
    logger = FakeInvocationLogger()
    record = InvocationRecord(
        prompt_version_id="prompt-1",
        model_version_id="model-1",
        input_tokens=120,
        output_tokens=45,
        latency_ms=350.0,
        tenant_id="tenant-abc",
        user_id="user-xyz",
    )

    await logger.log_invocation(record)

    assert logger.logged == [record]
    assert logger.logged[0].tenant_id == "tenant-abc"
