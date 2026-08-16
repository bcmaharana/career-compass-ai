"""Career-path traversal over the `role_progresses_to` graph (Phase 6,
Opportunity Intelligence) — pure logic, no framework, no database.

Distinct from graph_validation.would_create_cycle, which only answers
"is this node reachable" for cycle detection — this module reconstructs
an actual ordered path (nearest rung first), which a cycle check never
needs to do. Same "plain Python BFS beats a recursive CTE at this
content volume" rationale as graph_validation.py.

The graph can branch (e.g. a Senior rung splitting into an IC ladder and
a management track), so "the path" from a role is really a
breadth-first-ordered list of every reachable role in that direction,
nearest first — not necessarily a single linear chain.
"""

from __future__ import annotations

from collections import deque
from uuid import UUID


def _bfs_ordered(adjacency: dict[UUID, list[UUID]], start: UUID) -> list[UUID]:
    """BFS level by level from `start`, excluding `start` itself from the
    output but not from `visited` (a role must never appear in its own
    path, even if a cycle somehow existed upstream of governance's cycle
    check)."""
    visited: set[UUID] = {start}
    ordered: list[UUID] = []
    queue: deque[UUID] = deque([start])
    while queue:
        node = queue.popleft()
        for neighbor in adjacency.get(node, []):
            if neighbor in visited:
                continue
            visited.add(neighbor)
            ordered.append(neighbor)
            queue.append(neighbor)
    return ordered


def traverse_downstream(edges: list[tuple[UUID, UUID]], role_id: UUID) -> list[UUID]:
    """Roles this one typically progresses *to*, nearest first."""
    adjacency: dict[UUID, list[UUID]] = {}
    for source, target in edges:
        adjacency.setdefault(source, []).append(target)
    return _bfs_ordered(adjacency, role_id)


def traverse_upstream(edges: list[tuple[UUID, UUID]], role_id: UUID) -> list[UUID]:
    """Roles that typically progress *to* this one, nearest first."""
    reverse_adjacency: dict[UUID, list[UUID]] = {}
    for source, target in edges:
        reverse_adjacency.setdefault(target, []).append(source)
    return _bfs_ordered(reverse_adjacency, role_id)
