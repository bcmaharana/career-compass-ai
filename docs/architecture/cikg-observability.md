# CIKG — Observability and Graph Health

Second-pass addendum. Every other CIKG document defines how content
*should* look when the system is working correctly. This one defines
how to notice when it isn't — the graph equivalent of database health
monitoring, and specifically the earliest warning system for this
platform's single biggest named risk (`cikg-mvp-roadmap.md`): the
catalog quietly skewing toward one profession despite the model being
built to be agnostic.

## Computed Offline, Surfaced to Curators — Not an End-User Feature

Every metric here is computed by a periodic batch job (not per-request)
and surfaced to holders of `cikg.content.*` permissions
(`cikg-content-governance.md`) as a curation backlog/dashboard — none
of it is end-user-facing. This mirrors how `knowledge_quality_score`
(`cikg-semantic-search.md`) is computed offline for ranking; observability
metrics are the curator-facing counterpart of the same underlying
signals, framed as *action items* rather than a *ranking input*.

## Metrics

| Metric | Definition | Action it drives |
|---|---|---|
| **Orphan skills** | `Skill` rows with zero `skill_category_membership` edges | Assign to at least one category — an uncategorized skill is unreachable by hierarchy browsing |
| **Underconnected skills** | `Skill` rows with fewer ontology edges (`related_to`/`prerequisite_of`/`specializes`) than the median for their category | Candidate list for curator attention or AI-suggested-edge generation (`cikg-content-governance.md`'s AI-suggestion pipeline) |
| **Duplicate candidates** | Pairs of `Skill` nodes with high name/embedding similarity (`cikg-semantic-search.md`) and *no* existing `synonym_of` edge or explicit "reviewed, not a duplicate" marker | Review queue for a `synonym_of` decision — flagged, never auto-merged, per that edge type's elevated-scrutiny rule |
| **Conflicting edges** | Count of unresolved competing `content_revision` proposals against the same `entity_id` (`cikg-versioning-confidence.md`) | Backlog for `cikg.content.approve` to resolve; a growing count signals either genuine ambiguity in a content area or a review-capacity bottleneck |
| **Stale content** | `approved` content whose `content_history` hasn't been touched in longer than a per-content-type threshold (distinct from `cikg-market-intelligence.md`'s confidence decay, which is about external data recency — this is about curation attention recency for otherwise-static reference content) | Queue for periodic re-review, not automatic deprecation |
| **Review backlog age** | Time `draft`/`in_review` content (including AI-suggested batches) has sat waiting for a decision | Process-health signal — a growing backlog means either review capacity or batch size needs adjusting (`cikg-content-governance.md`'s `import_batch_id` grouping exists specifically to keep this manageable) |
| **Search zero-result rate** | Share of search queries (`cikg-semantic-search.md`) returning nothing relevant | Seeds the content-creation backlog directly — a real query with no answer is a more reliable signal of what to add next than guessing |

## Profession-Agnosticism Health Check

The metric that most directly answers "is this platform actually
profession-agnostic, or does it just have the structure to be": content
distribution across top-level `SkillCategory` domains
(`cikg-skill-ontology.md`). Computed as each domain's share of total
approved `Skill` count, flagged when any single domain's share exceeds
a set threshold (a starting point worth revisiting once real content
exists, not a number to treat as precise from day one).

This is the direct, ongoing, measurable version of the concern
`cikg-mvp-roadmap.md` names as the platform's biggest risk and
`cikg-skill-ontology.md` addresses with deliberately rotated examples —
observability is what keeps that a continuously-checked property
instead of a one-time intention stated in a document and never
verified again. MVP 1's five-domain seed set (`cikg-mvp-roadmap.md`)
gives this metric a meaningful baseline to compare against from the
very first release, rather than only becoming actionable once the
catalog is already large enough for a skew to be expensive to correct.

## Implementation Note

No new infrastructure — this reuses the existing `structlog`-based
logging already used throughout the backend (`app/core/logging.py`)
for the underlying event trail, plus a periodic job (same category as
the market-data ingestion job in `cikg-market-intelligence.md`) that
computes and persists each metric's current value for dashboard
display. The dashboard/reporting surface itself is an implementation
detail of whichever MVP slice adds curator tooling
(`cikg-mvp-roadmap.md`), not a new architectural component.

## Related Documents

- `docs/architecture/cikg-content-governance.md` — the workflow these metrics feed back into
- `docs/architecture/cikg-versioning-confidence.md` — conflict data this reads
- `docs/architecture/cikg-semantic-search.md` — `knowledge_quality_score`, the ranking-facing counterpart of these signals
- `docs/architecture/cikg-mvp-roadmap.md` — the profession-agnosticism risk this metric set monitors
