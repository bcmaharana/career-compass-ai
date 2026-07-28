# ADR-004: AI Governance as a Foundational Platform Capability

## Status
Accepted

## Context
AI-generated content (recommendations, coaching responses) carries product, legal, and trust risk if it's ungoverned: prompts changed without review, no record of which model produced a given output, no way to explain a recommendation after the fact, and no mechanism for a tenant to require human sign-off before AI output reaches an end user. Retrofitting governance after AI features ship is materially harder than building it in from the start.

## Decision
Treat the AI Platform as a first-class module from Phase 0 (interfaces and folder structure only) through Phase 4 (real provider wiring), with these non-negotiable properties from the first real AI call onward:

- Prompts are versioned rows (`PromptVersion`) with an approval workflow — never inline strings edited in place.
- Models are tracked in a registry (`ModelVersion`) with explicit status, so switching or retiring a model is a data change, not a code change.
- Every invocation is logged with prompt version, model version, token usage, and latency.
- AI-generated recommendations carry `confidence_score`, `reasoning_metadata`, and a `source_data_ref` — enough to reconstruct "why" after the fact.
- Tenants can require human review before an AI-generated recommendation reaches an end user (`Recommendation.status = pending_review`), configurable via feature flag.

## Consequences
**Positive:**
- No AI feature ships without an audit trail from day one.
- Swapping providers/models is a governed, reversible operation, not a code deploy.
- Explainability data exists before anyone asks a hard question about a specific recommendation.

**Negative / accepted trade-offs:**
- Slightly more upfront schema and plumbing work before the first AI feature ships (Phase 4), versus wiring a provider directly into a feature and adding governance later.
- Evaluation/bias-check tooling starts as a scaffold with basic checks, not a mature evaluation suite — accepted as a Phase 4+ iteration, not a Phase 0 blocker.

## Revisit Trigger
Expand the evaluations module beyond basic checks once the first AI features (Phase 5 onward) have enough real usage data to make evaluation meaningful.
