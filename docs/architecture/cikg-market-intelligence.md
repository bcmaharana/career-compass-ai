# CIKG — Skill Market Intelligence Model

Second-pass document. Covers the source spec's "Future AI Features:
Salary Intelligence, Labor Market Analytics" — labor-market demand,
compensation, and growth-trend data layered onto `Skill`/`Role` nodes.

## This Needs a Real External Data Source — Named as an Open Decision

Unlike the rest of CIKG (which the platform curates or generates
itself), market intelligence is inherently **external, licensed data**
— labor market statistics, compensation benchmarks, and job-posting
demand signals come from a small number of commercial providers (e.g.
Lightcast, LinkedIn Economic Graph, Levels.fyi-style compensation
data) or public sources with narrower coverage (e.g. the U.S. Bureau of
Labor Statistics, useful for aggregate trend data but not skill-level
granularity). **This document does not select a vendor** — that's a
cost/licensing decision for whoever owns the product, the same category
of decision Firebase/Twilio were for phone login: requires an account,
a budget, and (specific to this data) a redistribution-rights review of
that provider's license terms before any of their data can be stored
and displayed in-product. The architecture below is deliberately
provider-agnostic so that decision doesn't block the design.

## Pluggable Provider — Third Instance of an Established Pattern

```
class MarketDataProviderInterface(Protocol):
    async def fetch_skill_snapshot(self, *, skill_name: str, region_id: UUID | None) -> MarketSnapshotData: ...
    async def fetch_role_snapshot(self, *, role_title: str, region_id: UUID | None) -> MarketSnapshotData: ...
```

This is the same shape as `LLMProviderInterface`
(`app/ai_platform/llm_service/provider_interface.py`) and the
`EmbeddingProviderInterface` proposed in `cikg-semantic-search.md`:
swap providers by adding a new adapter class and a registry row, no
change to anything that calls the interface. Whichever vendor is
selected, integration is one new file under
`app/adapters/market_data_providers/`.

## Data Model

```
Region (
    id UUID PRIMARY KEY,
    name TEXT NOT NULL,             -- "United States", "California", "San Francisco Bay Area"
    geo_level TEXT NOT NULL,        -- 'country' | 'state_province' | 'metro'
    parent_region_id UUID REFERENCES region(id)
)

SkillMarketSnapshot (
    id UUID PRIMARY KEY,
    skill_id UUID NOT NULL REFERENCES skill(id),
    region_id UUID REFERENCES region(id),   -- NULL = global/national aggregate
    demand_score NUMERIC,           -- normalized 0-100, provider-defined methodology
    median_salary NUMERIC,
    salary_p25 NUMERIC, salary_p75 NUMERIC, salary_p90 NUMERIC,
    growth_rate_yoy NUMERIC,
    snapshot_date DATE NOT NULL,
    source TEXT NOT NULL,           -- provider name
    confidence NUMERIC NOT NULL,    -- see decay below
    import_batch_id UUID            -- same governance grouping as cikg-content-governance.md
)

RoleMarketSnapshot ( -- identical shape, role_id instead of skill_id )
```

`Region` is a simple strict tree (country → state/province → metro) —
unlike `SkillCategory`'s deliberate DAG (`cikg-skill-ontology.md`),
geography genuinely nests one way, so a single `parent_region_id` is
sufficient here rather than the many-to-many `category_parent` edge
table pattern.

Both snapshot tables are reference data (no `tenant_id`, same default
as the rest of CIKG) — market conditions aren't tenant-specific. An
enterprise tenant wanting to overlay its own internal compensation
bands on top of public market data is a `tenant_private`
extension (`cikg-content-governance.md`'s visibility mechanism),
not a change to this model.

## Time-Series, Not a Single Current Value

Every snapshot is dated and additive — a new `SkillMarketSnapshot` row
per ingestion run, never an update-in-place of the previous one. This
is what makes `growth_rate_yoy` derivable/verifiable from the raw
history rather than trusted as a single opaque number a provider
reports, and it's what "labor market analytics" (trend charts, not just
point-in-time lookups) needs structurally.

## Confidence Decay — Applying `cikg-versioning-confidence.md`'s Shared Function

Market data is the primary real use case for the decay function that
document defines generically:

```
effective_confidence = base_confidence × 0.5 ^ (age_in_days / half_life_days)
```

| Field | Half-life (starting point, tunable per provider) | Why |
|---|---|---|
| `demand_score` | 30-60 days | Job-posting volume shifts fast |
| `median_salary` / percentiles | 180-365 days | Compensation moves slower than demand |
| `growth_rate_yoy` | 365 days | A year-over-year figure is inherently annual-cadence |

A snapshot's `effective_confidence` is computed at query time (not
stored), so it's always accurate to the moment it's displayed rather
than needing a background job to keep a stored value fresh. Low
`effective_confidence` doesn't hide a snapshot — the UI should show
staleness honestly (e.g. "salary data as of 8 months ago, may be
outdated") rather than silently dropping the only data available for a
niche skill with infrequent ingestion.

## Ingestion — Reuses Governance's Batch Pattern, No New Pipeline Concept

Market data ingestion is a scheduled job that calls
`MarketDataProviderInterface`, maps each response to
`SkillMarketSnapshot`/`RoleMarketSnapshot` rows, and tags them with a
shared `import_batch_id` — the exact same `bulk_import` +
`import_batch_id` mechanism `cikg-content-governance.md` already
defines for populating the rest of the catalog. No separate
market-data-specific pipeline is needed; it's one more `source_attribution`
value flowing through the existing content-revision/review machinery,
though in practice market snapshots are lower-touch for review than a
new `Skill` definition (numeric data from a licensed provider, not a
semantic claim needing curator judgment) — batch approval by a curator
confirming the ingestion run looks sane, not row-by-row review.

## How This Gets Used

- **Learning Agent** (`cikg-ai-agents.md`) can prioritize a skill gap by
  market demand, not just by role requirement — "closing this gap is
  both required for your target role *and* in high demand regionally."
- **Career Coach Agent** can ground compensation-related coaching
  conversations in real (if imperfect, honestly-labeled) data instead
  of the model's own training-data guesses.
- **Career Path Intelligence** (future) can annotate path steps with
  market trend context.

## Trade-Off Worth Naming Explicitly

Whichever provider is eventually selected, its data-licensing terms
constrain what this platform can do with the data — some providers
license "display to your own users" but prohibit bulk redistribution or
long-term raw storage beyond a caching window. That's a real constraint
on the time-series design above (unlimited historical retention may not
be licensed, depending on provider) and needs to be confirmed against
the specific vendor's contract before implementation, not assumed away
by this architecture.

## Related Documents

- `docs/architecture/cikg-versioning-confidence.md` — the decay function this uses
- `docs/architecture/cikg-content-governance.md` — the batch-import mechanism this reuses
- `docs/architecture/cikg-ai-agents.md` — consumers of this data
