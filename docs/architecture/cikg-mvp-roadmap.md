# CIKG — MVP Implementation Roadmap

Second-pass document, and the one that ties the rest of the second pass
together into a build order — including the four additions made after
the first architecture review (Edge Governance, Knowledge Quality
Score, `cikg-observability.md`, `cikg-api-boundaries.md`) and the three
pre-coding actions from the second review
(`docs/adr/ADR-007-cikg-storage-strategy.md`,
`docs/adr/ADR-008-ai-agent-execution-boundary.md`, and
`cikg-mvp1-seed-data.md`). This is a recommended default sequence, not
a fixed mandate — business priority can reorder MVP 4 onward (e.g. if
Resume Intelligence matters sooner than a fully fleshed Career Level
Framework, MVP 5's Resume Agent slice can move earlier). What shouldn't
move is MVP 1 (Phase 4.5.1) being first: every later slice depends on
the core graph and governance existing.

## Where This Sits in the Existing Phase Numbering

`docs/architecture/system-overview.md` already names Phases 5-8 (Resume
Intelligence, Opportunity Intelligence, Learning Intelligence, AI
Career Coach) as not-yet-started. CIKG is foundational to several of
them at once, so it doesn't fit cleanly inside any single existing
phase number — proposed as **Phase 4.5: Career Intelligence Knowledge
Graph Foundation**, landing between the already-complete Phase 4 (AI
Platform) and Phase 5 (Resume Intelligence), since Resume Intelligence
specifically benefits from CIKG existing first (grounding generated
bullets in real `Skill`/`Role` data and `SkillEvidence`, per
`cikg-ai-agents.md`). Phases 5-8 keep their existing numbers and
descriptions; they now additionally *consume* Phase 4.5's output where
relevant, per the "consume, don't own" relationship `cikg-ddd.md`
establishes. Within Phase 4.5, MVP 1 below is labeled **Phase 4.5.1**
specifically as the concrete, narrow starting point for implementation
— the smallest slice that proves the model before anything else is
built on it.

## The Single Biggest Risk: Content, Not Code

Every document in this pass designs a *structure* that's genuinely
profession-agnostic. Whether the platform's actual *content* ends up
that way is a separate, harder problem — it's entirely possible to
build this architecture correctly and still end up with a catalog that
is 90% technology skills because that's what's easiest to source
content for. **MVP 1's seed content is deliberately designed as a proof
point against this risk, not just a functional demo.**

## MVP Slices

### MVP 1 (Phase 4.5.1) — Core Graph Foundation
The concrete starting point for implementation — deliberately the
narrowest slice that proves the model works at all before anything
else is built on top of it.

**Delivers:** `Skill`, `Role`, `Competency`, `SkillCategory` +
`member_of`, `requires`, `related_to` only (the minimum edge set to
prove hierarchy, requirement, and ontology relationships each work —
`prerequisite_of`/`specializes`/`synonym_of` and their DAG-validation
rules, `cikg-content-governance.md`'s "Edge Governance" section, follow
in MVP 2B once the governance workflow they depend on exists); minimal
content governance (`draft`/`approved` only — defer `in_review`/
multi-reviewer workflow and edge cycle-checking to MVP 2B, a single
approver is enough to prove the lifecycle at this stage); the
`skill_alias` soft-linking table connecting to existing
`CareerProfile.core_competencies`/`TargetRole.required_skills`
(ADR-006 §3), unchanged.

**Seed content — the profession-agnostic proof point:** fully specified
in `cikg-mvp1-seed-data.md` — 5 domains (Technology & Engineering,
Healthcare & Clinical, Finance & Accounting, Skilled Trades, Sales),
~20-30 skills each with category placement and ontology edges, plus
example `Role`s exercising the `requires` edge. Small enough to
hand-curate without the AI-assisted pipeline yet; large enough that if
the model secretly assumes tech-shaped data, it breaks visibly here
instead of silently scaling a bad assumption into thousands of rows
later. This is the platform's architecture-validation dataset, not a
claim of curatorial completeness or domain-expert accuracy — real
content quality is an ongoing curation process
(`cikg-content-governance.md`), not a one-time seed.

**Depends on:** nothing beyond what's already built (existing Postgres,
existing RBAC for the one new `cikg.content.*` permission set).

**Risk:** underestimating how much curator time even 100-150 seed
skills with cross-links takes. Mitigation: this is exactly why it's
hand-curated and small at this stage — validate the model against real
content before investing in AI-assisted scale (MVP 2+).

**Exit criteria:** a `Skill` in each of the 5 seed domains has at least
one populated hierarchy path, at least one ontology edge
(`related_to`/`prerequisite_of`), and at least one `skill_alias` that
successfully resolves an existing test user's free-text
`core_competencies` entry.

### MVP 2A — Search Foundation
Split out from what was originally a single "MVP 2" — search delivers
visible, demonstrable value on its own and shouldn't wait on the full
governance workflow being built first.

**Delivers:** `content_embedding`/`embedding_model` tables, the
Ollama-based free embedding path first (`cikg-semantic-search.md` — no
new paid vendor needed to prove the search architecture), hybrid search
(vector + full-text + graph filter), the `/search` retrieval endpoint
(`cikg-api-boundaries.md`) — **and a simple first version of
`knowledge_quality_score`**, pulled forward from being "just a
concept" in `cikg-semantic-search.md` into an actual MVP 2A deliverable:
search ranking without any quality signal lets an unreviewed or
low-quality relationship rank equally with a well-curated one, which
undermines trust in results from day one. The MVP 2A version is
deliberately simple — `approval_status + source_type + relationship_count`
only. The fuller factor set (usage frequency, freshness, conflict
count) genuinely can't be computed yet at this point: usage data
doesn't exist before search has users, and conflict-count needs MVP
2B's governance workflow to exist first — those factors layer in once
their inputs exist, not held back arbitrarily.

**Depends on:** MVP 1's seed content (nothing to search without it).

**Risk:** low — read-only addition on top of stable MVP 1 content.

**Exit criteria:** the source spec's example queries ("find all skills
related to Product Strategy," "find certifications validating Lean
Portfolio Management," "find roles requiring Azure DevOps") return
correct, sensibly-ranked results against the MVP 1 seed content.

### MVP 2B — Governance Expansion
**Delivers:** full governance lifecycle (`draft`→`in_review`→`approved`,
`content_revision`/`content_history` per `cikg-versioning-confidence.md`),
the AI-suggestion path with human approval, batch review
(`import_batch_id`), and edge governance's DAG/cycle validation
(`cikg-content-governance.md`'s "Edge Governance" section) — this is
where `prerequisite_of`, `specializes`, and `synonym_of` become
available, since they specifically need the review workflow and cycle
checks this slice delivers.

**Depends on:** MVP 1 (entities to govern); independent of MVP 2A —
could in principle be built in parallel with it, though reviewing
AI-suggested *search-relevant* content is more useful once search
exists to show what it's for.

**Risk:** AI-suggested content volume outpacing review capacity even
with batch review. Mitigation: keep AI-suggestion generation rate-
limited/scoped to specific domains per batch, don't turn on unbounded
catalog expansion yet.

**Exit criteria:** an AI-suggested `draft` edge (including a
`prerequisite_of` proposal that would create a cycle) is correctly
blocked at approval time, and a human-approved batch becomes visible to
search/gap-analysis within the same review cycle.

### MVP 3 — Skill Evidence
**Delivers:** `SkillEvidence` (`cikg-skill-evidence.md`), wired to the
already-existing `Experience`/`Certification`/`PeerEndorsement`/
`CareerHighlight`/`KeyAchievement` entities — this slice is mostly UI
and linking logic, not new core-graph schema.

**Depends on:** MVP 1 (needs `Skill` ids to link evidence to, via
`skill_alias` resolution).

**Risk:** low — this is additive to stable, already-shipped Career
Profile entities.

**Exit criteria:** a test user's existing `Experience` rows can be
linked as evidence for their existing `core_competencies` entries, and
evidence strength (Claimed/Referenced/Corroborated) computes correctly.

### MVP 4 — Career Level Framework (Schema + Limited Mapping, Not Broad Population)
**Deliberately narrower than originally scoped.** The schema
(`CareerLevel`, `CareerTrack`) is the easy part; the hard part is
*classification* — where a given title actually lands is genuinely
ambiguous and inconsistent across companies (an "Enterprise Architect,"
"Principal Consultant," or "Agile Coach" title means meaningfully
different scope at different organizations), and broadly populating
`Role.career_level_id` across every seed `Role` before that
classification judgment has been validated risks encoding wrong
mappings at scale before anyone's checked whether the ten-band scale
itself holds up in practice.

**Delivers:** `CareerLevel`, `CareerTrack` schema
(`cikg-career-levels.md`) in full, plus `Role.career_level_id`/
`career_track_id` populated for only a **small, deliberately
low-ambiguity set** — the worked examples `cikg-career-levels.md`
already validated on paper (e.g. the investment-banking-VP-vs-tech-VP
pair, a nursing progression, a skilled-trades progression) — rather
than exhaustively mapping every seed `Role`. `CareerPath.next_role`
sequences follow the same limited scope: prove the mechanism on 2-3
paths, not all 5 domains at once.

**Depends on:** MVP 1's `Role` nodes.

**Risk:** the ten-band scale or track set needing adjustment once
tested against real classification judgment calls — exactly why this
slice stays small: cheaper to revise a 10-role mapping than a
fully-populated one. Treat the specific bands/tracks as a
`cikg.content.admin`-managed reference scale (`cikg-content-governance.md`)
that can be refined post-launch, not a frozen schema decision. Broader
population across the remaining seed `Role`s is a follow-on slice,
undertaken only after this limited set has validated the scale holds up
— not bundled into this one.

**Exit criteria:** 2-3 `CareerPath`s (not one per domain) correctly
ordered by `CareerLevel.ordinal`, spanning at least 2 different
`CareerTrack`s, with each mapped `Role`'s level/track assignment
reviewed and confirmed correct by a curator rather than just schema-valid.

### MVP 5 — First AI Agent (Resume Agent)
**Delivers:** `agent_session` + `ai_invocations.agent_session_id`
(`cikg-ai-agents.md`), the tool-use orchestration loop, and the Resume
Agent specifically — chosen first because it directly unblocks the
already-planned Phase 5 (Resume Intelligence) and because it exercises
every other MVP slice at once (reads `SkillEvidence`, `Skill`/`Role`
via semantic search, respects tenant-scoped permissions).

**Depends on:** MVP 1, 2A, and 3 (graph, search, and evidence all need
to exist for grounded generation to mean anything). Does not strictly
require 2B — an agent can ground itself in `approved` content whether
that content arrived via full governance review or MVP 1's simpler
single-approver flow — though in practice 2B will have shipped first
since it's a smaller, earlier slice.

**Risk:** ungrounded/hallucinated bullet generation if evidence-linking
adoption (MVP 3) is low at this point — mitigation is the UI
distinction `cikg-skill-evidence.md` already specifies (grounded vs.
"review before using" flagging), not a blocker on shipping the agent.

**Exit criteria:** the Resume Agent generates at least one bullet
correctly grounded in a real `SkillEvidence` row, with a traceable
`source_data_ref`, logged under a real `agent_session`.

## Beyond MVP — Phase 6+ Strategic Enhancement

**Market Intelligence** (`Region`, `SkillMarketSnapshot`/
`RoleMarketSnapshot`, `cikg-market-intelligence.md`) is deliberately
**not** part of the core MVP 1-5 sequence, moved out rather than kept as
a trailing "MVP 6." It's fully designed and ready to build whenever
it's prioritized, but it has a dependency none of MVP 1-5 share: a
signed vendor contract with data-licensing terms reviewed
(`cikg-market-intelligence.md`'s "open decision"), which is a business/
procurement timeline, not an engineering one. Keeping it numbered
alongside MVP 1-5 implied it was on the same critical path; it isn't —
the rest of CIKG (graph, search, evidence, career levels, the first AI
agent) delivers complete, standalone value without it. Revisit as a
real roadmap slice once a provider is under contract; until then it
stays a designed-but-unscheduled capability, same category as the
"Can Defer" items below.

**Exit criteria (whenever scheduled):** at least one seed domain has
real demand/salary data visibly informing gap-analysis prioritization.

## Also Deferred Past MVP

Beyond Market Intelligence, explicitly not required for MVP 1-5 to
deliver real value:

- **Full multi-reviewer workflow** — MVP 1's single-approver model is
  sufficient until content volume genuinely needs multiple review
  stages; upgrading is additive to `cikg-content-governance.md`'s
  existing `content_revision.status` states, not a redesign.
- **Advanced career assessment** (inferring someone's actual level from
  their evidence, rather than `cikg-career-levels.md` just providing
  the scale) — a natural future AI Agent, not part of the initial
  Career Coach/Resume Agent pair.
- **External verification integrations** (confirming a certification
  number against its issuing provider) — the extensibility point
  `cikg-skill-evidence.md` already reserves a slot for
  (`evidence_type = 'assessment'`) without requiring it now.

## Cross-Cutting Risks (Apply Across All Slices)

| Risk | Mitigation |
|---|---|
| Catalog quietly skews tech-heavy despite the model being profession-agnostic | MVP 1's deliberately diverse seed set as an early forcing function, not a later audit; `cikg-observability.md`'s domain-distribution metric keeps checking this continuously afterward, not just at launch |
| AI-suggested content erodes trust if review is rushed | Hard no-auto-promotion rule (`cikg-content-governance.md`) holds regardless of content-volume pressure |
| Scope creep — building every document's worth of capability before validating any of it | Each MVP has explicit exit criteria; a slice isn't "started" until the prior one meets its exit criteria |
| pgvector/HNSW performance at real scale | Not a near-term risk at MVP-stage content volume; revisit only if/when catalog size approaches a scale where index rebuild cost becomes noticeable (no specific number predicted here — genuinely unknown until real usage data exists) |
| Graph or governance problems going unnoticed until they've compounded | `cikg-observability.md`'s health metrics (orphan skills, review backlog age, conflict counts) surface these as an ongoing operational signal, not something only caught by manual audit |

## What This Roadmap Deliberately Does Not Include

The physical PostgreSQL schema (exact column types/constraints/
migrations) and the detailed security/tenant-extension implementation
are execution-level detail for each MVP slice as it's built, not
architecture decisions this roadmap needs to pre-resolve — consistent
with the foundational pass's own scoping. The REST API's *boundaries*
(resource hierarchy, read/write permission split, versioning strategy)
are now defined in `cikg-api-boundaries.md`; the exact
request/response schema for each endpoint is still left to each MVP
slice, the same granularity every other domain in this codebase
already designs at.

## Related Documents

Every other second-pass document — `cikg-content-governance.md`
(including its Edge Governance section), `cikg-skill-ontology.md`,
`cikg-skill-evidence.md`, `cikg-semantic-search.md` (including
Knowledge Quality Score), `cikg-ai-agents.md`, `cikg-market-intelligence.md`,
`cikg-career-levels.md`, `cikg-versioning-confidence.md`,
`cikg-observability.md`, `cikg-api-boundaries.md`, `cikg-mvp1-seed-data.md`
— plus `docs/adr/ADR-006-career-intelligence-knowledge-graph.md`,
`docs/adr/ADR-007-cikg-storage-strategy.md`,
`docs/adr/ADR-008-ai-agent-execution-boundary.md`, and the three
foundational-pass documents (`cikg-overview.md`, `cikg-ddd.md`,
`cikg-knowledge-graph-model.md`).
