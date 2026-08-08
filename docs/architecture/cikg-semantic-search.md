# CIKG — Semantic Search Architecture

Second-pass document. Answers the source spec's example queries
("find all skills related to Product Strategy," "find roles requiring
Azure DevOps") with a concrete retrieval design. The platform's
Postgres is already pgvector-enabled (`docs/architecture/system-overview.md`
lists "PostgreSQL 16 (pgvector-enabled)" in the stack) — this design
uses what's already provisioned rather than introducing a separate
search infrastructure.

## What Gets Embedded

Every CIKG node type with meaningful natural-language content, at
`approved` status only (`cikg-content-governance.md` — `draft`/
`in_review` content is invisible to every read path, search included):

`Skill` (name + description + aliases), `Role` (title + description +
responsibilities), `CareerPath` (name + narrative), `LearningResource`
(title + description), `InterviewQuestion` (question text + ideal-answer
template), `Company` (culture notes), `Competency`, `Industry`,
`Certification`. Purely structural nodes with no free-text worth
embedding (e.g. a bare `Technology` row that's just a name) skip
embedding and rely on exact/full-text match only.

## Storage: One Polymorphic Embedding Table, Not a Column Per Node Type

```
content_embedding (
    id UUID PRIMARY KEY,
    entity_type TEXT NOT NULL,          -- 'skill' | 'role' | 'career_path' | ...
    entity_id UUID NOT NULL,
    embedding_model_id UUID NOT NULL REFERENCES embedding_model(id),
    embedding VECTOR(N) NOT NULL,       -- pgvector column, N = the model's dimensionality
    source_text_hash TEXT NOT NULL,     -- hash of the exact text that was embedded, to detect staleness
    generated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (entity_type, entity_id, embedding_model_id)
)

embedding_model (        -- mirrors ModelVersion's role for LLMs (app/ai_platform/models/registry.py)
    id UUID PRIMARY KEY,
    provider TEXT NOT NULL,     -- 'voyage' | 'ollama'
    model_name TEXT NOT NULL,
    dimensions INT NOT NULL,
    is_default BOOLEAN NOT NULL DEFAULT false
)
```

One shared table rather than a vector column bolted onto ten different
node tables, for three reasons: (1) adding an eleventh embeddable node
type later is a content-type string, not a migration; (2) supporting
multiple embedding models simultaneously (evaluating a new model before
cutting over) is additional rows, not a schema change or a
side-by-side column pair; (3) `source_text_hash` gives a cheap way to
detect "this embedding is stale because the underlying content changed"
without re-diffing the full text on every check.

## Embedding Provider — The Same Dual-Provider Pattern Already Established

The AI Platform already solved "pluggable provider, paid option +
free local option" for LLMs (`app/adapters/ai_providers/anthropic_provider.py` +
`ollama_provider.py`, both implementing `LLMProviderInterface`,
selected via `ModelVersion.provider`). Embeddings get the identical
treatment rather than a new pattern:

```
class EmbeddingProviderInterface(Protocol):
    async def embed(self, *, texts: list[str], model_name: str) -> list[list[float]]: ...
```

- **Paid option**: Voyage AI — Anthropic's own recommended embedding
  partner (Anthropic doesn't offer a first-party embeddings endpoint),
  fitting the same "real API key, real cost" category as the existing
  `AnthropicProvider`.
- **Free local option**: Ollama, which already runs locally for chat
  (`qwen2.5:3b`/`7b`) and also serves embedding-capable models (e.g.
  `nomic-embed-text`) through the same `/api/embed` REST endpoint
  pattern the existing `OllamaProvider` already uses for chat — no new
  infrastructure, just a new model pulled into the same Ollama install.

Resolved via `embedding_model.is_default` exactly the way
`ModelVersion.is_default` already resolves the platform's default chat
model — no new resolution mechanism to design.

## Indexing

pgvector's **HNSW** index type over IVFFlat: better recall/speed at
query time for a read-heavy, moderate-write workload (CIKG content
changes at curation pace, not per-request), at the cost of slower index
builds — an acceptable trade for this access pattern. Revisit toward
IVFFlat only if the catalog grows large enough that HNSW build/memory
cost becomes a real operational problem (a scale this platform isn't
at during the MVP phases, `cikg-mvp-roadmap.md`).

```sql
CREATE INDEX ON content_embedding USING hnsw (embedding vector_cosine_ops);
```

Combined with a standard Postgres GIN index on a `tsvector` generated
column over each node's searchable text, for the full-text half of
hybrid search below.

## Hybrid Search: Vector + Full-Text + Graph Filter

Pure vector similarity alone under-serves the spec's exact-match cases
("find roles requiring **Azure DevOps**" needs "Azure DevOps" to match
exactly, not just semantically-nearby tools). Pure full-text alone
misses genuinely-related-but-differently-worded results ("Product
Strategy" should surface "Product Positioning" even without shared
keywords). Three signals combine per query:

1. **Vector similarity** (pgvector cosine distance) — semantic
   nearness, catches paraphrases and related concepts.
2. **Full-text match** (Postgres `tsvector`/`ts_rank`) — exact and
   near-exact keyword matches, including `Skill.ats_keywords`.
3. **Graph-relationship filter** — structured constraints from the
   edges already modeled (`cikg-knowledge-graph-model.md`), e.g.
   restricting results to a category subtree (`skill_category_membership`)
   or to skills a specific `Role` requires.

Combined via score fusion (e.g. reciprocal rank fusion across the
vector and full-text result sets, then the graph filter applied as a
hard constraint before ranking, not blended into the score) — exact
weighting is an implementation/tuning detail for the roadmap phase, not
a foundational architecture decision; what's fixed here is that all
three signals are first-class, not vector-only.

### Worked Example: "Find all skills related to Product Strategy"

1. Resolve "Product Strategy" to a `Skill` node (exact/alias match via
   `skill_alias`, same resolution the free-text-linking layer already
   uses — ADR-006 §3).
2. Graph traversal: follow `related_to` edges directly from that node
   (structured, exact).
3. Vector similarity: embed "Product Strategy" (or reuse the resolved
   node's stored embedding) and find nearby `Skill` embeddings, to
   surface conceptually related skills that don't have an explicit
   `related_to` edge yet — this is also how **AI-suggested `related_to`
   edges get their candidates** (`cikg-content-governance.md`'s
   AI-suggestion pipeline): high vector similarity between two skills
   with no existing edge is exactly the signal that generates a `draft`
   `related_to` proposal for a curator to review.
4. Union and rank both result sets; edges from step 2 rank above
   embedding-only matches from step 3, since an approved, curated
   relationship is more trustworthy than a similarity score
   (`cikg-versioning-confidence.md`'s curated-outranks-AI principle
   applied to search ranking, not just content approval).

## Knowledge Quality Score — A Fourth Ranking Signal

The three hybrid-search signals above (vector, full-text, graph filter)
answer "how relevant is this to the query." They don't answer a
different question that matters just as much for ranking: **among
several relevant, approved results, which one is actually the better
answer?** Two `Skill` nodes can be equally relevant to a query and
equally `approved`, while one is richly connected, evidenced across the
platform, and recently curated, and the other is a thin, isolated stub
that happened to pass review. `knowledge_quality_score` captures that
difference — computed periodically per node (a background job, not
per-query), used only to weight ranking among relevant results, never
computed live in the query path.

**This is deliberately distinct from two other scores already defined
elsewhere, worth disambiguating explicitly since all three sound
similar:**

| Score | Defined in | Measures | Visible to end users? |
|---|---|---|---|
| `confidence` | `cikg-versioning-confidence.md` | How much a specific content *revision* should be trusted, given its source (curated/AI/import) | No — internal, drives approval workflow and conflict resolution |
| Evidence strength (Claimed/Referenced/Corroborated) | `cikg-skill-evidence.md` | How well a *person's* skill claim is substantiated by their own experience | Yes — shown to the user about their own profile |
| `knowledge_quality_score` | This document | How well-developed a *catalog node* is, for ranking purposes | No — internal ranking input only, never shown as a raw number |

Showing any of these as a bare number to an end user would imply a
false precision none of them actually has — `knowledge_quality_score`
in particular is a ranking heuristic, not a claim about truth.

### Composite Factors

| Factor | Direction | Notes |
|---|---|---|
| Source authorship | + for `curated` over `ai_suggested`-then-approved | Both are equally *visible* (only `approved` content is ever surfaced at all — approval status itself is a visibility gate per `cikg-content-governance.md`, not a ranking factor among already-approved results), but a human-authored node carries slightly more weight than one a human only reviewed after an AI draft |
| Relationship richness | + | Count of approved edges (in + out) touching this node, relative to the typical count for its category — a "Quantum Computing" `Skill` with two edges ranks below a "Python" `Skill` with thirty, all else equal |
| Evidence linkage | + | Count of `SkillEvidence` rows across the platform referencing this skill (`cikg-skill-evidence.md`) — an **aggregate count only**, never exposing which tenants/users, consistent with tenant isolation; a real signal that a skill is actually used in practice, not just theoretically defined |
| Usage frequency | + | How often this node appears in and is selected from search results — **deferred until basic usage analytics exist** (`system-overview.md` lists Analytics as a not-yet-started cross-cutting domain); not computable at MVP |
| Freshness | + | Time since the node's last approved `content_history` entry — reuses the decay-function *shape* from `cikg-versioning-confidence.md` (half-life based), but measures curation recency, a different concept from that document's use of decay for time-sensitive external data like market snapshots |
| Conflict count | − | Number of times this node/edge has been the subject of a competing `content_revision` (`cikg-versioning-confidence.md`'s conflict resolution) — repeated conflict suggests contested or ambiguous content, worth a small demotion until resolved, not a hard exclusion |

Weighting across these factors is a tuning concern for implementation,
not a foundational decision this document needs to fix — what's fixed
here is the factor set, that it's computed offline (not per-query), and
that it never appears as raw output.

## Re-Embedding Triggers

An embedding goes stale exactly when the content it represents changes.
Tied directly to `cikg-versioning-confidence.md`'s approval flow:
whenever a `content_revision` is approved and applied to a live entity,
its `content_embedding` row(s) are queued for regeneration
(asynchronously — a background job, not synchronous with the approval
action, so the governance UI stays responsive). `source_text_hash`
lets a periodic reconciliation job cheaply verify nothing was missed
without re-embedding everything on a schedule.

## Related Documents

- `docs/architecture/cikg-knowledge-graph-model.md` — the entities and edges being searched
- `docs/architecture/cikg-content-governance.md` — what "approved" means for search visibility
- `docs/architecture/cikg-versioning-confidence.md` — re-embedding trigger source
- `docs/architecture/cikg-ai-agents.md` — agents as another consumer of this same retrieval layer (RAG)
- `docs/architecture/ai-platform-architecture.md` — the existing provider-abstraction pattern this mirrors
