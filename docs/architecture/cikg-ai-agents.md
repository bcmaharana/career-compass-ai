# CIKG — AI Agent Architecture

Second-pass document. The existing AI Platform (`docs/architecture/ai-platform-architecture.md`,
ADR-004) already provides provider abstraction (`LLMService`,
`Anthropic`/`Ollama` adapters), versioned prompts (`PromptRegistry`),
model selection (`ModelRegistry`), and invocation governance
(`InvocationLogger` → `ai_invocations`). Agents are a **new
orchestration layer on top of that**, not a replacement for any of it —
every agent call still goes through `LLMService.generate()` under the
hood for each individual model call it makes.

## What Makes Something an "Agent" Here, Not Just Another Chat Prompt

The existing footer/Coach chat (`ChatService`) is a single-turn
prompt-in, text-out call per message — no tool use, no multi-step
reasoning. An **agent**, in this architecture, is specifically:

1. A versioned system prompt (a new `PromptRegistry` `use_case`, same
   mechanism `career_coach_chat` already uses — no new prompt-storage
   concept needed).
2. A **defined, narrow tool/capability set** it may call — never
   unrestricted database or filesystem access.
3. An orchestration loop: the model proposes a tool call → the backend
   executes it (subject to the permission rules below) → the result is
   fed back to the model → repeat until it produces a final answer or a
   step limit is reached. Simple agents (generate one resume bullet
   from a given evidence row) may resolve in a single LLM call with no
   tool use at all; this loop only engages when the task genuinely
   needs it (e.g. "research this company and tailor my resume" needs
   several grounded lookups before it can write anything).

This maps naturally onto the tool-use pattern Anthropic's API already
supports, which the existing `AnthropicProvider` is already talking to
— extending it with tool-call support is additive to that adapter, not
a new integration.

## Hard Rule: No Elevated Privilege, Ever

An agent acting "on behalf of" a user is bound by **exactly the same
tenant-scoped RLS and permission checks a direct API call from that
user would hit** — never a service-account bypass, never a
cross-tenant read for "better context." Every tool an agent can call is
implemented as a call into an existing (or new, but equally
permission-checked) application service — `get_tenant_scoped_session`
and `require_permission` (`app/api/dependencies.py`) apply identically
whether the caller is a human request or an agent's tool call. This is
the same discipline `multi-tenancy-design.md` already establishes for
every other code path in this system; agents don't get an exception.

## Agent Catalog

| Agent | Purpose | Reads | Writes |
|---|---|---|---|
| **Resume Agent** | Generate/tailor resume bullets and summaries | `SkillEvidence` (`cikg-skill-evidence.md`), `CareerProfile`/`Experience`, target `Role.requires` edges, `Skill.ats_keywords` | Draft `ResumeBullet` rows (future Resume Intelligence domain) — never auto-published; user reviews/edits before anything is finalized |
| **Interview Agent** | Generate prep questions and STAR-story scaffolds | `InterviewQuestion` bank (`evaluates` edges to target `Skill`s), `SkillEvidence`, target `Role`/`Company` | Draft prep-session content (future Interview Intelligence domain) |
| **Career Coach Agent** | Conversational guidance (extends the existing footer/Coach chat) | `CareerPath`, `Role`, `Skill` gap analysis (existing `GapAnalysisService` + CIKG enrichment), semantic search (`cikg-semantic-search.md`) | Nothing beyond the existing `ChatMessage` persistence — read-heavy by design |
| **ATS Optimization Agent** | Score/suggest edits so a resume matches a target role's requirements | Resume content, target `Role.requires` edges, `Skill.ats_keywords` | Suggested edits (draft, not applied) |
| **Learning Agent** | Recommend learning resources for a skill gap | Gap analysis output, `LearningResource.teaches` edges | Nothing — pure recommendation |
| **Company Research Agent** | Surface company-specific context (culture, tech stack, interview patterns) | `Company` node (curated CIKG data) **plus external web content** — the one agent whose grounding isn't entirely curated CIKG data | Nothing directly; may propose a `draft` `Company` content_revision (`cikg-content-governance.md`) if it finds a durable fact worth adding to the catalog, subject to the same human-approval gate as any other AI-suggested content |

The Company Research Agent is called out separately because it's the
one place this architecture intentionally reaches outside the curated
graph. External web content it retrieves is **never presented with the
same trust level as curated `Company` data** — cited and attributed as
external/unverified in the UI, distinct from approved CIKG content,
consistent with `cikg-versioning-confidence.md`'s principle that
different sources carry genuinely different confidence, made visible
rather than blended away.

## Grounding: Agents Read the Same Graph Search Does

No agent gets a bespoke retrieval mechanism — every agent's "read CIKG"
capability is implemented as calls into the same semantic-search layer
(`cikg-semantic-search.md`) every other consumer (product search, gap
analysis enrichment) uses. This keeps grounding consistent: an agent
citing "this skill is related to that one" is drawing on the identical
curated/versioned/confidence-scored graph a human browsing search
results would see, not a separate, divergent retrieval path.

## Governance: Every Agent Action Is Traceable

Extends the existing `ai_invocations` governance table (ADR-004)
rather than adding a parallel logging mechanism:

```
agent_session (
    id UUID PRIMARY KEY,
    tenant_id UUID NOT NULL,
    user_id UUID NOT NULL,
    agent_type TEXT NOT NULL,     -- 'resume' | 'interview' | 'career_coach' | 'ats' | 'learning' | 'company_research'
    status TEXT NOT NULL,         -- in_progress | completed | failed
    started_at, completed_at
)
```

`ai_invocations` gains a nullable `agent_session_id` — every individual
`LLMService.generate()` call an agent makes during its tool-use loop is
still logged exactly as it is today (prompt version, model version,
tokens, latency), now optionally grouped under the session that
produced it. A multi-step agent run is fully reconstructable after the
fact: which prompt/model made each decision, what tools were called
with what arguments, and what the final output was — the same
explainability standard ADR-004 already requires
(`confidence_score`/`reasoning_metadata`/`source_data_ref` per output)
extends naturally to agent-produced content, since each piece of
generated output can cite the specific `SkillEvidence`/`Skill`/`Role`
rows it was grounded in as its `source_data_ref`.

## Human-in-the-Loop, By Default

Every agent in the catalog above either produces read-only output
(Career Coach, Learning) or **drafts that require explicit user
confirmation before anything is finalized** (Resume, Interview, ATS).
No agent auto-publishes a resume, auto-sends anything, or auto-applies
a content change to the CIKG catalog — the Company Research Agent's
one write path (proposing a `Company` content_revision) goes through
the exact same human-approval gate as any other AI-suggested content.
This mirrors the platform's existing tenant configuration option
("tenants can require human review before an AI output reaches an end
user" — `CLAUDE.md`'s AI Platform section) generalized to every agent,
not just the original single-prompt chat.

## Related Documents

- `docs/architecture/ai-platform-architecture.md`, `docs/adr/ADR-004-ai-governance-strategy.md` — the foundation this extends
- `docs/architecture/cikg-semantic-search.md` — shared grounding/retrieval layer
- `docs/architecture/cikg-skill-evidence.md` — grounding source for generated resume/interview content
- `docs/architecture/cikg-versioning-confidence.md` — why external (Company Research) content is flagged distinctly
