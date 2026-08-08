# CIKG — Skill Evidence Model

Second-pass document. Answers a question the foundational pass left
open: a free-text skill claim ("I know Python") and a canonical `Skill`
node existing in the graph are both just *assertions* — neither says
anything about whether the claim is actually substantiated. This model
adds that substantiation layer, entirely optionally.

## Where This Lives

`SkillEvidence` is **tenant-owned personal data**, not CIKG reference
data — same category as `Experience`, `Certification`, and
`PeerEndorsement` (`app/domain/career_profile/entities.py`), which is
exactly why it's the natural place for this: those entities already
exist and already are the evidence. This model doesn't introduce new
kinds of user-entered content; it adds explicit *links* from a skill
claim to content that's already there.

## The Default State Doesn't Change

Every skill in `CareerProfile.core_competencies` or
`TargetRole.required_skills` today is what this model calls
**Claimed** — asserted, no linked evidence. That stays the default and
requires nothing from anyone. Evidence is additive enrichment a user
*can* build up over time, never a requirement for a skill to exist on
their profile — the same non-blocking principle ADR-006 established for
the free-text-to-`Skill` linking layer applies here identically.

## Evidence Strength — A Qualitative Ladder, Not a Fake Precision Score

```
SkillEvidence (
    id UUID PRIMARY KEY,
    tenant_id UUID NOT NULL,
    user_id UUID NOT NULL,
    skill_claim_text TEXT NOT NULL,     -- the exact free-text string this evidence supports
    skill_id UUID REFERENCES skill(id), -- nullable — set only if skill_claim_text resolves via skill_alias
    evidence_type TEXT NOT NULL,        -- 'experience' | 'certification' | 'endorsement' | 'career_highlight' | 'key_achievement' | 'project' | 'assessment' | 'self_described'
    source_entity_id UUID,              -- nullable — points at the Experience/Certification/PeerEndorsement/etc. row, when evidence_type references an existing entity
    description TEXT,                   -- free text — used when there's no existing entity to point at (evidence_type = 'project' or 'self_described')
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
)
```

A skill's evidence *strength* is derived, not stored as a single
number — computed from how many independent, distinct-`evidence_type`
rows exist for that claim:

| Strength | Definition | Example |
|---|---|---|
| **Claimed** | Zero linked evidence rows | "Python" sits in `core_competencies` with nothing else |
| **Referenced** | Exactly one evidence row | One `Experience` row mentions using Python |
| **Corroborated** | Two or more evidence rows of **different** `evidence_type`s | An `Experience` row *and* a `Certification` *and* a `PeerEndorsement` all support "Python" |

Deliberately not a numeric confidence score (e.g. "0.83") — that would
imply a precision this data doesn't have. A qualitative three-tier
ladder is honest about what's actually knowable from self-entered
profile data, and is enough to be useful: sort/filter/highlight by
strength in gap analysis, resume generation, and AI grounding, without
pretending to a false level of certainty. (Compare
`cikg-versioning-confidence.md`, which *does* use a numeric confidence
score — but for CIKG's own curated/AI-suggested *reference* content,
where a model-output probability is a meaningfully different kind of
number than "how many personal life-events back up this claim.")

Two evidence rows of the *same* type don't upgrade Claimed→Corroborated
by themselves (e.g. two different jobs both mentioning Python is still
just "used at multiple jobs," one dimension of evidence) — the
`evidence_type` diversity requirement is what distinguishes genuinely
independent corroboration (did it, was certified in it, and someone
else vouches for it) from restating the same kind of claim twice.

## Why This Isn't a "Verification" System

Nothing here calls an external certification provider's API to confirm
a credential number, or otherwise independently verifies a claim
against a third-party source. That's a real future capability (noted
as an extensibility point below) but explicitly out of scope for this
model — `SkillEvidence` records *what the person says supports their
claim*, which is already meaningfully more substantive than a bare
string, without taking on the much larger scope of building
verification integrations per certification provider, employer, or
institution.

## How This Feeds AI Generation

The clearest payoff: an AI Resume Agent or Interview Prep Agent
(`cikg-ai-agents.md`) generating a bullet point or STAR story for
"Python" should **prefer grounding in linked evidence** (the specific
`Experience` row's actual description) over generating a plausible-
sounding but fabricated bullet from the skill name alone. This is
directly in service of ADR-004's AI governance principle
(`reasoning_metadata`/`source_data_ref` on every AI output) — a
generated bullet with a `source_data_ref` pointing at a real
`SkillEvidence` row is categorically more trustworthy than one
generated from a bare skill string, and the UI can honestly represent
that difference (e.g. "grounded in your experience at Acme Corp" vs. a
visible "unverified — review before using" flag) instead of presenting
every generated claim with equal confidence.

## Gap Analysis Enrichment

The existing `GapAnalysisService` (ADR-005 — `required_skills` minus
`core_competencies`, case-insensitive) is unchanged. Evidence adds a
second, optional dimension on top: among skills the person *does*
claim, which are well-substantiated versus merely asserted. A gap
report can now distinguish "you're missing this skill entirely" from
"you claim this skill but have no evidence backing it up — worth adding
before it goes on a resume a recruiter might scrutinize," without
changing what counts as a gap in the first place.

## Extensibility Points (Not This Pass)

- **Third-party verification**: a `verification_status` +
  `verified_by`/`verified_at` addition once/if the platform integrates
  with specific certification providers, LinkedIn, or employer
  reference checks — additive columns, not a redesign.
- **Assessment-based evidence**: `evidence_type = 'assessment'` already
  reserves the slot for a future skills-assessment feature (quiz/test
  results) to plug into the same evidence ladder without a new model.

## Related Documents

- `docs/architecture/cikg-skill-ontology.md`
- `docs/architecture/cikg-career-levels.md`
- `docs/architecture/cikg-ai-agents.md` — evidence-grounded generation
- `docs/adr/ADR-005-skill-intelligence-simplification.md` — the free-text model this enriches without changing
