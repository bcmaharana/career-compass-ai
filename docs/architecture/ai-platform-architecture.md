# AI Platform Architecture — Career Compass AI

## Principle

AI is a governed platform capability, invoked by application services, never called directly from routers and never given direct database access. Every invocation is traceable to a specific prompt version and model version.

## Staged Rollout

| Phase | Capability |
|---|---|
| Phase 1 (this doc's Phase-0 foundation belongs here) | LLM service abstraction — provider interface, prompt registry, model registry, invocation logging. No RAG, no agents. |
| Phase 2 | Retrieval-augmented generation — embeddings + retrieval modules become live |
| Phase 3 | Agent orchestration — multi-step reasoning built on top of the same LLM service, not a replacement for it |
| Phase 4 | Advanced autonomous workflows |

Phase 0 (repository/backend foundation) created the **interface
contracts and folder structure** for the above —
`ai_platform/llm_service/`, `ai_platform/prompts/`, `ai_platform/models/`,
`ai_platform/governance/` — with a stub in-memory implementation
sufficient for tests. No RAG, no agents.

**Phase 4 status: real wiring is live.** `app/adapters/ai_providers/anthropic_provider.py`
implements `LLMProviderInterface` against the Anthropic Messages API.
`app/ai_platform/llm_service/service.py`'s `LLMService` is the concrete
orchestrator application services call — it resolves the active
approved prompt and active model from Postgres-backed registries
(`app/adapters/db/repositories/ai_platform.py`, tables `prompt_versions`
/ `model_versions`, seeded by `scripts/seed_platform_defaults.py`),
renders the template, calls the provider, and logs every invocation to
`ai_invocations` (tenant-owned, RLS-enforced). The AI Career Coach
footer chat (`app/application/chat/chat_service.py`) is the first real
caller — its "career_coach_chat" prompt renders recent conversation
history plus the latest message; a provider failure (missing API key,
rate limit, network error) degrades to an apologetic in-chat message
rather than a 500, since the conversation itself is still persisted
either way. `LLMRequest` carries a `model_name` field (the literal
provider model string, e.g. `"claude-sonnet-5"`) resolved from the
active `ModelVersion` by `LLMService` — this was added in Phase 4 since
the Phase 0 interface only had opaque registry IDs, which the provider
adapter cannot call a model with directly.

## Component Responsibilities

- **`llm_service/`** — the single entry point application services call. Hides which provider/model is active behind one method signature.
- **`providers/` (adapters)** — one adapter per provider (Anthropic first), each implementing the same `LLMProviderInterface`. Swapping providers is a configuration change.
- **`prompts/`** — prompt registry. Prompts are versioned rows (`PromptVersion`), not inline strings in code. A prompt change is a new version, reviewed and approved before it's marked active — never an in-place edit of an approved prompt.
- **`models/`** — model registry. Tracks which provider/model/version is active, its cost, and its status (`active`/`sunset`).
- **`governance/`** — invocation logging (prompt version, model version, token usage, latency) and the hook point for future evaluation/bias-check batch jobs.

## Why the Interface Exists Before the Implementation

Defining `LLMProviderInterface` in Phase 0 — before any real provider is wired in Phase 4 — means every application service written between now and then already codes against the eventual real contract. There's no "temporary" AI-calling code to rip out later.

## Human Review & Confidence

Every AI-generated recommendation (from Phase 4 onward) carries a `confidence_score` and `reasoning_metadata`, and tenants can require human sign-off before a recommendation reaches an end user (`Recommendation.status = pending_review`). This is a data-model decision made now (see `docs/adr/ADR-004-ai-governance-strategy.md`) even though the feature using it doesn't exist until later.
