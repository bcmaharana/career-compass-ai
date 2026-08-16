"""Unit tests for career_path_traversal's BFS path reconstruction."""

from __future__ import annotations

import uuid

import pytest

from app.domain.career_intelligence.career_path_traversal import (
    traverse_downstream,
    traverse_upstream,
)

pytestmark = pytest.mark.unit


def _ids(n: int) -> list[uuid.UUID]:
    return [uuid.uuid4() for _ in range(n)]


class TestTraverseDownstream:
    def test_linear_chain_returns_nearest_first(self) -> None:
        a, b, c, d = _ids(4)
        edges = [(a, b), (b, c), (c, d)]

        assert traverse_downstream(edges, a) == [b, c, d]

    def test_no_outgoing_edges_returns_empty(self) -> None:
        a, b = _ids(2)
        edges = [(b, a)]  # only points *at* a, nothing *from* it

        assert traverse_downstream(edges, a) == []

    def test_branching_graph_includes_every_branch(self) -> None:
        a, b, c, d = _ids(4)
        edges = [(a, b), (a, c), (b, d)]

        result = traverse_downstream(edges, a)

        assert set(result) == {b, c, d}
        # b and c are both one hop away, so both appear before d (two hops).
        assert result.index(d) > result.index(b)

    def test_never_includes_the_start_node_even_with_a_cycle(self) -> None:
        a, b = _ids(2)
        edges = [(a, b), (b, a)]

        assert a not in traverse_downstream(edges, a)


class TestTraverseUpstream:
    def test_linear_chain_returns_nearest_predecessor_first(self) -> None:
        a, b, c, d = _ids(4)
        edges = [(a, b), (b, c), (c, d)]

        assert traverse_upstream(edges, d) == [c, b, a]

    def test_no_incoming_edges_returns_empty(self) -> None:
        a, b = _ids(2)
        edges = [(a, b)]

        assert traverse_upstream(edges, a) == []
