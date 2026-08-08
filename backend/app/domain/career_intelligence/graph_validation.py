"""DAG cycle-detection for directed CIKG ontology/hierarchy edges
(Phase 4.5.1 MVP 2B) — pure logic, no framework, no database.

Applies to `prerequisite_of`, `specializes`, and `category_parent` —
the three "Directed, DAG-required" edge types per
cikg-content-governance.md's Edge Governance constraint table. A plain
BFS over an adjacency map built from already-approved edges: nothing
recursive-CTE-based exists anywhere in this codebase yet, and at CIKG's
current content volume (~110 nodes) a Python traversal is simpler to
write, test, and reason about than introducing one.
"""

from __future__ import annotations

from collections import deque
from uuid import UUID


def would_create_cycle(
    existing_edges: list[tuple[UUID, UUID]], new_source: UUID, new_target: UUID
) -> bool:
    """True if adding the directed edge `new_source -> new_target` would
    create a cycle, given the already-approved edges of that same type.

    A cycle forms exactly when `new_source` is already reachable *from*
    `new_target` by following existing edges forward — that reachable
    path plus the new edge closes the loop back to where it started.
    """
    if new_source == new_target:
        return True

    adjacency: dict[UUID, list[UUID]] = {}
    for source, target in existing_edges:
        adjacency.setdefault(source, []).append(target)

    visited: set[UUID] = set()
    queue: deque[UUID] = deque([new_target])
    while queue:
        node = queue.popleft()
        if node == new_source:
            return True
        if node in visited:
            continue
        visited.add(node)
        queue.extend(adjacency.get(node, []))

    return False
