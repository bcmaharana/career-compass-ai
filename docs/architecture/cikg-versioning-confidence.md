# CIKG — Data Versioning and Confidence Model

Second-pass document. Defines the mechanics behind
`cikg-content-governance.md`'s lifecycle — how a "new draft version"
actually gets stored without breaking every edge that references the
entity being edited, and how much any given piece of content should be
trusted.

## The Stable-ID Problem

`cikg-ddd.md` established that edges reference nodes by id, and that
this is what makes the graph a graph rather than a document tree. If
editing a `Skill` created an entirely new row with a new id (naive
"append-only versioning"), every edge pointing at the old id would need
repointing — a cascading update across a potentially large number of
edge tables, every time a description gets fixed. That's the wrong
trade-off.

**Resolution: synthesize the two patterns already proven separately
elsewhere in this codebase.**

- From `PromptVersion` (`app/ai_platform/prompts/registry.py`): a
  `draft → in_review → approved` staging lifecycle before anything goes
  live (already adopted wholesale in `cikg-content-governance.md`).
- From `CareerProfileVersion` (`app/domain/career_profile/entities.py`):
  the *entity's own id stays stable across edits*; history is captured
  in a separate snapshot table, not by minting a new id per change.

Combined:

```
content_revision (          -- the staging area; nothing here is live yet
    id UUID PRIMARY KEY,
    entity_type TEXT NOT NULL,      -- 'skill' | 'role' | 'edge:requires' | ...
    entity_id UUID,                 -- the STABLE id being revised; NULL if this revision is a brand-new entity not yet created
    proposed_data JSONB NOT NULL,   -- full proposed attribute set
    revision_number INT NOT NULL,
    status TEXT NOT NULL,           -- draft | in_review | approved | rejected
    confidence NUMERIC,             -- 0.0-1.0, see below
    source_attribution TEXT NOT NULL,  -- 'curated' | 'ai_suggested' | 'bulk_import'
    import_batch_id UUID,           -- groups a batch for bulk review (cikg-content-governance.md)
    reviewed_by UUID,
    review_notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    reviewed_at TIMESTAMPTZ
)

content_history (           -- append-only audit trail, written when a revision is approved
    id UUID PRIMARY KEY,
    entity_type TEXT NOT NULL,
    entity_id UUID NOT NULL,
    version_number INT NOT NULL,
    snapshot JSONB NOT NULL,        -- the entity's full state immediately before this change
    change_reason TEXT,
    revision_id UUID NOT NULL REFERENCES content_revision(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
)
```

**Flow**: a curator or AI pipeline proposes a change → `content_revision`
row created at `draft` (never touches the live `Skill`/`Role`/edge
table). Submitted → `in_review`. Approved (`cikg.content.approve`) →
two things happen atomically: (1) the live entity row is updated (or
created, if `entity_id` was null) with `proposed_data`, keeping its id
stable; (2) a `content_history` snapshot of the *prior* state is
written, so nothing is ever silently overwritten without a recoverable
record. Edges never need repointing, because the id they reference
never changes — only what that id's row *contains* changes, and every
past version of what it contained is preserved.

This is exactly the "supersedes, doesn't delete" language from
`cikg-content-governance.md`'s curation workflow — `content_history` is
what "superseded, not deleted" concretely means.

## Confidence Score

`content_revision.confidence` (0.0-1.0) reflects how much a given piece
of content should be trusted, set differently by source:

| Source | Default confidence | Rationale |
|---|---|---|
| `curated` | 1.0 (adjustable by the approving curator, rarely lowered) | A human with `cikg.content.approve` reviewed and vouched for it |
| `ai_suggested` | Whatever the generating pipeline reports as its own estimate, or a conservative fixed default (e.g. 0.5) if the model doesn't expose one | Never auto-trusted regardless of the number — see `cikg-content-governance.md`'s hard rule that `ai_suggested` content always requires human approval no matter how high its confidence reads |
| `bulk_import` | Set per import source (e.g. a recognized standards taxonomy import might default to 0.9; a scraped/unverified source lower) | Configured once per source, not per row, at import-batch setup |

**Confidence is not the same as approval status.** A `curated`,
`approved` row with confidence 1.0 and an `ai_suggested`, still-`draft`
row with confidence 0.9 are not remotely equivalent — only `approved`
content is ever visible to the product (`cikg-content-governance.md`).
Confidence is metadata *about* a piece of content for ranking/display
purposes (e.g. showing search results ranked partly by confidence, or
letting an AI agent weight grounding sources), not a substitute for the
review gate.

### Confidence Decay

Not universal — most reference content (a `Skill`'s definition, a
`Role`'s requirements) doesn't meaningfully go stale just from the
passage of time. **Time-sensitive content types opt into decay
explicitly.** The one clear case in this pass is Skill Market
Intelligence (`cikg-market-intelligence.md`), whose entire value is
recency:

```
effective_confidence = base_confidence × decay_factor(age, half_life)
decay_factor(age, half_life) = 0.5 ^ (age / half_life)
```

A market snapshot's `half_life` is set per data type at ingestion
(e.g. salary data might have a 180-day half-life; a fast-moving demand
signal might have 30 days) — `cikg-market-intelligence.md` defines the
concrete values; this document defines the shared decay function every
time-sensitive content type reuses rather than inventing its own.

This is a distinct number from `SkillEvidence`'s qualitative
Claimed/Referenced/Corroborated ladder (`cikg-skill-evidence.md`) —
that model deliberately avoids a fake-precision numeric score for
personal evidence; this one uses a real numeric score because a model's
reported probability or a decay function's output is a genuinely
different, and genuinely more precise, kind of number than "how many
independent things back up this person's claim."

## Conflict Resolution

Two proposals can legitimately disagree about the same `entity_id`
(two competing `content_revision` rows) — for example an AI batch
suggests a `Role → Skill` edge is `preferred` while a curator separately
proposes `required`. Resolution order, evaluated in this sequence:

1. **`curated` always outranks `ai_suggested`/`bulk_import`,
   regardless of confidence score.** A human's judgment is never
   silently overridden by a model's numeric confidence being higher —
   this is a hard rule, not a tunable weight, specifically to avoid the
   failure mode of a bug or prompt change quietly eroding trust in
   curated content.
2. **Two `ai_suggested` proposals disagreeing**: if one's confidence
   clearly exceeds the other by a meaningful margin (a threshold set in
   review tooling config, not hardcoded here), the higher one is
   surfaced as the recommended resolution *for a human to confirm* —
   never auto-applied. If the two are close, both are shown side by
   side in the review queue with no system-suggested winner, since a
   small confidence gap between two model outputs isn't a reliable
   signal either way.
3. **Two `curated` proposals disagreeing** (two curators independently
   propose conflicting edits): always routed to human review — whoever
   holds `cikg.content.approve` picks a winner; the other is marked
   `rejected` with a review note explaining the conflict, preserved in
   `content_history`'s trail rather than silently discarded.

## Deprecation Doesn't Delete

`cikg.content.deprecate` (`cikg-content-governance.md`) sets
`content_status = 'deprecated'` on an entity — this excludes it from
active read paths (search, gap analysis, AI grounding) but:

- The row and its full `content_history` remain intact.
- Edges referencing it are **not** cascade-deleted — they're flagged
  for curator review (a `needs_review` marker triggered by the
  deprecation), since silently dropping relationships tied to a
  deprecated node could quietly break dependent content (e.g. a
  `CareerPath` step) without anyone noticing.
- Anything outside CIKG that soft-links to it (a `skill_alias`
  resolution, a `SkillEvidence.skill_id`, `cikg-skill-evidence.md`)
  keeps working for historical display — someone's evidence from years
  ago referencing a since-deprecated `Skill` id should still render
  correctly in their history, not vanish.

## Related Documents

- `docs/architecture/cikg-content-governance.md` — the workflow this implements
- `docs/architecture/cikg-market-intelligence.md` — the primary user of confidence decay
- `docs/architecture/cikg-skill-evidence.md` — the separate, qualitative evidence-strength model
