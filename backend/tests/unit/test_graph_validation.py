"""Unit tests for DAG cycle-detection (Phase 4.5.1 MVP 2B)."""

from __future__ import annotations

import uuid

import pytest

from app.domain.career_intelligence.graph_validation import would_create_cycle


@pytest.mark.unit
class TestWouldCreateCycle:
    def test_no_edges_no_cycle(self) -> None:
        a, b = uuid.uuid4(), uuid.uuid4()

        assert would_create_cycle([], a, b) is False

    def test_unrelated_existing_edges_no_cycle(self) -> None:
        a, b, c, d = uuid.uuid4(), uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
        existing = [(a, b)]

        assert would_create_cycle(existing, c, d) is False

    def test_self_loop_is_always_a_cycle(self) -> None:
        a = uuid.uuid4()

        assert would_create_cycle([], a, a) is True

    def test_direct_reverse_edge_is_a_cycle(self) -> None:
        a, b = uuid.uuid4(), uuid.uuid4()
        existing = [(a, b)]  # a -> b already approved

        # proposing b -> a would close a 2-node cycle
        assert would_create_cycle(existing, b, a) is True

    def test_transitive_cycle_is_detected(self) -> None:
        a, b, c = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
        existing = [(a, b), (b, c)]  # a -> b -> c already approved

        # proposing c -> a would close a 3-node cycle
        assert would_create_cycle(existing, c, a) is True

    def test_transitive_non_cycle_extends_the_dag_safely(self) -> None:
        a, b, c = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
        existing = [(a, b), (b, c)]

        # a -> c is a valid "shortcut" edge in the same DAG, not a cycle
        assert would_create_cycle(existing, a, c) is False

    def test_diamond_shaped_dag_extension_is_not_a_cycle(self) -> None:
        a, b, c, d = uuid.uuid4(), uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
        existing = [(a, b), (a, c), (b, d), (c, d)]

        # adding a -> d directly is redundant but not cyclic
        assert would_create_cycle(existing, a, d) is False

    def test_disconnected_component_never_creates_a_cycle(self) -> None:
        a, b, c, d = uuid.uuid4(), uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
        existing = [(a, b)]  # a -> b, in a separate component from c/d

        assert would_create_cycle(existing, c, d) is False
