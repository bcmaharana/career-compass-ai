# ADR-007: CIKG Storage Strategy — PostgreSQL as System of Record

## Status
Accepted

## Context

`cikg-knowledge-graph-model.md` already designs CIKG relationally —
thin node tables plus per-edge-type tables (`source_id`, `target_id`,
metadata columns) — specifically so a future migration to a dedicated
graph database (Neo4j or similar) would be a near-mechanical export
rather than a redesign. That reasoning is documented as design
motivation inside that document, but the actual *decision* — stay on
PostgreSQL now, and under what conditions that would change — has
never been recorded as a decision in its own right. Six months into
building this, someone will reasonably ask "why aren't we using a
graph database for a knowledge graph?" This ADR exists so the answer is
a recorded decision with named trade-offs, not a re-litigation.

## Decision

**PostgreSQL remains the system of record for CIKG, including graph
traversal.** Concretely:

- Nodes and edges are relational tables, per `cikg-knowledge-graph-model.md`.
- Graph traversal (e.g. "all skills within N hops," career-path
  sequencing, cycle detection for `prerequisite_of`/`specializes`/
  `category_parent` — `cikg-content-governance.md`'s Edge Governance
  section) is implemented with recursive CTEs (`WITH RECURSIVE`)
  against the edge tables.
- Semantic/similarity search uses pgvector (`cikg-semantic-search.md`),
  already provisioned in this platform's Postgres instance — no
  separate vector database.
- **A migration to a dedicated graph database is not planned and is
  not the default trajectory.** It is a decision this ADR explicitly
  defers, to be made only if the Revisit Trigger below is actually hit
  — not adopted speculatively because "it's a knowledge graph, so it
  should be graph-database-backed" on its own.

## Consequences

**Positive:**
- No new infrastructure to operate, monitor, or gain team expertise in
  — the platform already runs, backs up, and scales PostgreSQL.
- Transactional consistency across a node write and its edges comes
  free from Postgres's own ACID guarantees — a graph database
  migration would need to either accept eventual consistency between
  the two stores or take on distributed-transaction complexity, neither
  of which this platform needs at its current or near-term scale.
- Reuses pgvector rather than standing up a second search
  infrastructure for embeddings.
- Every other reference-data pattern in this codebase
  (`prompt_versions`, `model_versions`, `permissions`, `roles`) is
  already relational — CIKG stays consistent with the rest of the
  system's operational model rather than being the one component
  requiring different backup/monitoring/access tooling.

**Negative / accepted trade-offs:**
- Recursive CTE traversal has a real performance ceiling for very deep
  or very branchy graphs, and Postgres query plans for multi-hop graph
  patterns are more verbose to write and reason about than the
  equivalent Cypher query would be in a native graph database. This is
  a genuine, named limitation, not dismissed — it's accepted because
  CIKG's actual query patterns (per `cikg-knowledge-graph-model.md`'s
  worked search examples) are shallow, bounded-depth traversals (one
  or two hops: skill → related skills, role → requires → skill →
  validates ← certification), not deep unbounded pathfinding.
- Some graph-native operations (e.g. weighted shortest-path across a
  large `CareerPath` network, community detection, centrality scoring)
  are either impractical or require hand-written recursive SQL that a
  graph database would provide natively. None of these are required by
  any document in this architecture pass as currently scoped.

## Revisit Trigger

Reconsider a dedicated graph database only when at least one of these
is **demonstrated**, not anticipated:

1. A recursive-CTE traversal query that's actually needed for a
   shipped feature (not a hypothetical one) regularly exceeds an
   agreed latency budget at real production data volume, after normal
   Postgres query optimization (indexing, materialized views for
   common traversal patterns) has been tried.
2. A required feature genuinely needs a graph algorithm class Postgres
   doesn't do well (weighted shortest-path, centrality, community
   detection) — not merely "expressible more elegantly in Cypher,"
   which alone isn't sufficient justification given the migration cost.
3. Edge/node volume grows to a scale where recursive CTE performance
   degrades in ways indexing can't fix — a scale this platform is not
   at during any of the MVP phases in `cikg-mvp-roadmap.md`.

If none of these occur, the relational design stands indefinitely —
this is not a "temporary until Neo4j" placeholder, it's the intended
long-term storage strategy.

## Related Documents

- `docs/architecture/cikg-knowledge-graph-model.md` — the relational-as-graph modeling this formalizes
- `docs/architecture/cikg-semantic-search.md` — pgvector usage
- `docs/architecture/cikg-content-governance.md` — Edge Governance's cycle-detection queries, the primary consumer of recursive traversal
- `docs/adr/ADR-002-database-strategy.md` — the platform's existing PostgreSQL decision this extends
