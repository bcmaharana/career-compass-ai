"""AI Platform: governed AI capability, invoked by application services.

See docs/architecture/ai-platform-architecture.md for the staged rollout
plan. Phase 0 establishes interfaces and folder structure only:

- llm_service/   Phase 1: provider-agnostic entry point (interface only for now)
- prompts/       prompt registry structure
- models/        model registry structure
- governance/    invocation logging structure
- embeddings/    Phase 2 (RAG) — empty until then
- retrieval/     Phase 2 (RAG) — empty until then
- agents/        Phase 3 — empty until then
- evaluations/   Phase 3+ — empty until then

No real provider call is wired until Phase 4.
"""
