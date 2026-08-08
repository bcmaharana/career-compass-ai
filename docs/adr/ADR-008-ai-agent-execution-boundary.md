# ADR-008: AI Agent Execution Boundary

## Status
Accepted

## Context

`cikg-ai-agents.md` states that agents get "no elevated privilege,
ever" and describes the tool-call orchestration pattern, but that
document is an architecture description, not a security-boundary
decision record. The distinction matters here specifically: an LLM
inside an agent loop is not a trusted actor in the way application code
is — it can be manipulated by adversarial content it retrieves (a
malicious job posting, a crafted resume upload, an injected instruction
hidden in retrieved CIKG content) into *requesting* an action outside
its intended scope. The defense against that has to be a hard boundary
the model cannot talk its way past, not a well-behaved prompt. This ADR
records that boundary explicitly, as ADR-004 (AI Governance) already
does for provenance/explainability and ADR-003 does for authentication
— the same category of decision, not a new one this architecture
invents.

## Decision

Every agent (`cikg-ai-agents.md`'s Resume/Interview/Career Coach/ATS/
Learning/Company Research catalog, and any added later) is bound by
five rules, enforced in code, not by prompt instruction:

1. **Agents cannot directly query repositories.** An agent's tool
   implementation never imports or instantiates a repository
   (`app/adapters/db/repositories/*`) directly — only application
   service methods, the identical boundary every API router already
   respects (`docs/architecture/backend-architecture.md`'s layering).
2. **Agents cannot bypass services.** Every tool exposed to the model
   is a thin wrapper around an existing (or equivalently
   permission-checked, purpose-built) application service call — the
   same `get_tenant_scoped_session`/`require_permission` machinery a
   human-initiated API request goes through
   (`app/api/dependencies.py`). There is no "agent service account"
   with broader access than the authenticated user it's acting for.
3. **Agents cannot write CIKG reference data directly.** Any CIKG
   content an agent proposes — the Company Research Agent's one write
   path in `cikg-ai-agents.md` was the original example, generalized
   here as a rule for every agent — enters as a `draft`
   `content_revision` (`cikg-versioning-confidence.md`), subject to the
   identical human-approval gate as any curator- or pipeline-suggested
   content (`cikg-content-governance.md`). No agent output ever
   auto-applies to the live graph.
4. **Agents cannot call arbitrary tools.** Each agent type has a fixed,
   enumerated tool catalog defined in code at build time — not a
   dynamically-discovered or self-expanding set, and not a generic
   "execute this function by name" capability. A prompt-injected
   instruction asking the model to "use the delete_everything tool" or
   any tool outside the calling agent's own catalog fails at the
   dispatch layer before it can execute anything, regardless of what
   the model outputs.
5. **Every tool call is logged**, not just the final generation. Every
   individual tool invocation within an `agent_session`
   (`cikg-ai-agents.md`) — tool name, arguments, a summary of the
   result, timestamp — is recorded, extending the same `ai_invocations`
   governance trail ADR-004 already requires for every LLM call. A
   session is fully reconstructable after the fact: not just what the
   model finally said, but every intermediate action it took to get
   there.

## Consequences

**Positive:**
- The security boundary holds even under a successful prompt injection
  — the model can be tricked into *asking* for something out of scope,
  but the fixed tool catalog plus service-layer permission checks mean
  it cannot actually *get* it. This is the specific threat model this
  ADR defends against, distinct from and complementary to ADR-004's
  explainability/governance concerns.
- No new enforcement mechanism to build — every rule reuses
  infrastructure that already exists (RBAC, `content_revision`,
  `ai_invocations`) rather than inventing agent-specific security
  primitives.
- A compromised or malfunctioning agent's blast radius is bounded to
  exactly the tools its type was built with and exactly the tenant/user
  context it's running under — never broader, by construction.

**Negative / accepted trade-offs:**
- Genuinely useful emergent agent behavior — a model creatively
  chaining tools in a way its designer didn't explicitly anticipate —
  is constrained by the fixed-catalog rule. This is accepted
  deliberately: flexibility that comes from an agent having open-ended
  capability is exactly the property that makes prompt injection
  dangerous, so the platform trades some agent creativity for a hard
  security guarantee.
- Adding a new capability to an existing agent requires a code change
  (a new tool added to its catalog) rather than the agent
  self-extending — treated as a feature of this boundary, not friction
  to route around.

## Revisit Trigger

None anticipated — this is a foundational security boundary, not a
scoped/temporary decision. Any proposal to relax rule 1-4 for a
specific agent (e.g. a future capability that seems to need broader
tool access) should be evaluated as a new, explicitly-scoped exception
requiring its own review, never a quiet loosening of the default.

## Related Documents

- `docs/architecture/cikg-ai-agents.md` — the architecture this formalizes
- `docs/adr/ADR-004-ai-governance-strategy.md` — explainability/provenance, the complementary governance concern
- `docs/architecture/multi-tenancy-design.md` — the RLS/permission boundary agents inherit, not bypass
- `docs/architecture/cikg-content-governance.md` — the approval gate agent-proposed content goes through
