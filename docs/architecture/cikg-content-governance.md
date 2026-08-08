# CIKG — Content Governance Model

Second-pass document. CIKG's entire value depends on its content being
trustworthy — a knowledge graph with confidently-wrong relationships is
worse than no graph at all, since it actively misleads gap analysis, AI
generation, and search rather than just being absent. This document
defines who can change what, how AI-suggested content earns its way
into the trusted graph, and how tenant-specific extensions coexist with
the global catalog.

## Content Lifecycle — Reusing an Already-Proven Pattern

Rather than invent a new workflow, CIKG content reuses the exact
`draft → in_review → approved → deprecated` status lifecycle already
proven in this codebase for `PromptVersion`
(`app/ai_platform/prompts/registry.py`): "a prompt change is a new
version with `status="draft"`, reviewed and promoted to `status="approved"`
before it can be resolved as active — never an in-place edit of an
approved version." CIKG nodes and edges follow the identical rule:

```
content_status: 'draft' | 'in_review' | 'approved' | 'deprecated'
```

applied uniformly to every `Skill`, `Role`, `Industry`, `Technology`,
`Certification`, `Company`, `CareerPath`, `InterviewQuestion`,
`LearningResource`, `SkillCategory`, and every edge type. Only
`approved` content is visible to search, gap analysis, AI grounding, or
any other read path outside the governance/curation tooling itself —
`draft` and `in_review` rows exist but are invisible to the product.
Editing an `approved` row doesn't mutate it in place; it creates a new
`draft` version (see `cikg-versioning-confidence.md` for exactly how
that's tracked) that goes through the same review gate before replacing
what's live.

## Roles and Permissions

Extends the existing RBAC system (`app/domain/identity/authorization.py`,
`require_permission`) with a new permission set, no new mechanism:

| Permission | Grants |
|---|---|
| `cikg.content.create` | Create/edit `draft` content |
| `cikg.content.review` | Move `draft` → `in_review`, leave review comments |
| `cikg.content.approve` | Move `in_review` → `approved` or reject back to `draft` |
| `cikg.content.deprecate` | Move `approved` → `deprecated`, resolve conflicting edges (`cikg-versioning-confidence.md`) |
| `cikg.content.admin` | All of the above, plus manage `CareerLevel`/`CareerTrack` reference scales and approve tenant-private extension requests |

These are **platform-level roles**, not per-tenant ones — the same
platform-role-vs-tenant-role split `roles` (with `tenant_id IS NULL`)
already establishes for reference data (`docs/architecture/multi-tenancy-design.md`).
A platform curator's `cikg.content.*` permissions have nothing to do
with any tenant's own `organization_admin`/etc. roles.

## AI-Suggested Content — Never Auto-Promoted

Given the "every industry, every role" scope, hand-curating the entire
catalog isn't realistic — AI-assisted content generation is expected to
originate a large share of it (see `cikg-mvp-roadmap.md` for sequencing).
The hard rule, stated explicitly because it's the one most tempting to
quietly relax under content-volume pressure:

**AI-suggested content always enters at `draft` with
`source_attribution = 'ai_suggested'` and a confidence score
(`cikg-versioning-confidence.md`). Nothing moves `draft` → `approved`
without a human holding `cikg.content.approve` acting on it.** No
confidence threshold, no "auto-approve above 0.95" shortcut — a
model that's wrong 1% of the time still means real wrong facts entering
a graph AI agents and gap analysis treat as ground truth, and there's
no way to distinguish which 1% from inside the system after the fact.

**Batch review, not one-by-one, for volume.** An `import_batch_id`
(nullable UUID) groups many `draft` rows created by a single AI
generation run or bulk import together, so a reviewer can review and
approve/reject an entire coherent batch (e.g. "200 AI-suggested Skills
under Healthcare → Clinical Practice, generated 2026-08-01") as one
unit with spot-checking, rather than clicking through 200 individual
approvals. This is what makes AI-assisted population practically
reviewable at the scope this platform needs, without abandoning the
human-approval rule above.

## Global Content vs. Tenant-Private Extensions

`multi-tenancy-design.md` already anticipates exactly this shape for
platform catalogs: *"Platform-wide `JobOpportunity`/`LearningPath`
catalog entries are exempt from tenant scoping — tenant-specific ones
still carry `tenant_id`."* CIKG follows the identical rule rather than
inventing a new one:

- **Global content** (the default, and the overwhelming majority of
  rows): `tenant_id IS NULL`, no RLS, visible to every tenant. This is
  everything covered so far in this document.
- **Tenant-private extensions** (opt-in, per enterprise tenant): a row
  with `tenant_id` set — e.g. a company's proprietary internal
  certification, or an internal-only competency taxonomy layered on top
  of the global catalog. These rows **do** get standard RLS treatment
  (`FORCE ROW LEVEL SECURITY`, `current_setting('app.tenant_id', true)`
  — the exact policy template in `multi-tenancy-design.md`), unlike
  every global row around them. This is a genuine fork within CIKG's
  otherwise-uniform "reference data, no RLS" default, and needs to stay
  a clearly-marked exception in migration comments (the same discipline
  `multi-tenancy-design.md` already calls for) so a future contributor
  doesn't assume every CIKG table is RLS-exempt.
- A tenant-private `Skill` (for example) can still participate in edges
  to global nodes (e.g. a private "Acme Internal Certification Level 3"
  `Certification` node `validates` a global `Skill`) — tenant privacy
  applies to the *node's visibility*, not to whether it can reference
  global content.
- Tenant-private extensions require `cikg.content.admin` to approve
  the *request* to create a private namespace for a tenant (an
  organizational decision, not a routine content edit), but day-to-day
  content within that namespace is managed by whatever role the tenant
  grants its own admins — detailed in the second-pass security document
  once this foundational set is approved.

## Edge Governance

Everything above governs *nodes*. Edges go through the identical
`content_revision`/approval workflow (an edge proposal is just another
`entity_type` in that table — `entity_type = 'edge:prerequisite_of'`,
`proposed_data` holding `source_id`/`target_id`/metadata), but edges
carry a risk nodes don't: **structural invalidity that isn't visible
just by reading the proposal**. A single `prerequisite_of` edge always
looks reasonable in isolation; the problem only appears when it
combines with existing approved edges to form a cycle. Node review
doesn't need this kind of check; edge review does.

### Constraint Rules by Edge Category

| Category | Edge types | Rule | Enforced |
|---|---|---|---|
| **Symmetric** | `related_to`, `synonym_of` | Stored once per unordered pair (canonical ordering: lower `id` as `source_id`) to prevent a duplicate reverse row; self-loops (a node related to itself) rejected | At proposal creation — cheap, no traversal needed |
| **Directed, DAG-required** | `prerequisite_of`, `specializes`, `category_parent` | Approving this edge must not create a cycle — A can't (even transitively) be a prerequisite/specialization/ancestor of itself | At **approval** time (see below) — requires traversing existing approved edges |
| **Directed, cross-type** | `requires`, `requires_competency`, `validates`, `supports`, `emphasizes`, `values`, `uses_technology`, `evaluates`, `asked_by`, `teaches`, `requires_technology`, `requires_certification` | No cycle is structurally possible (the edge connects two different node types with no reverse edge of the same type) — only standard duplicate-edge prevention (`UNIQUE (source_id, target_id, edge_type)`) | At proposal creation |
| **Ordered** | `next_role` | `sequence_position` unique per `CareerPath`; no `Role` repeated within one path; a `CareerLevel.ordinal` **decrease** between consecutive steps is flagged for reviewer attention, not auto-rejected — lateral or unconventional moves are real, just uncommon enough to deserve a second look (`cikg-career-levels.md`) | At approval time |

### Why Cycle Checks Happen at Approval, Not at Draft Creation

A `draft` edge proposal is inert — it isn't part of the live graph yet,
so two different curators can independently draft `prerequisite_of`
edges that would conflict without either draft being wrong *on its
own*. The cycle check runs when a proposal is about to become
`approved` and join the live graph: a recursive traversal from the
proposed edge's target back toward its source, over only
*already-approved* edges of that same type. If the traversal reaches
the source, approval is rejected with an explanation (which existing
approved path creates the cycle), and the conflict is resolved like any
other content conflict (`cikg-versioning-confidence.md`'s conflict
resolution) — never silently dropped or silently allowed.

### Elevated Scrutiny for `synonym_of`

Every other edge type, once approved, is additive — removing it later
if wrong doesn't retroactively corrupt anything else. `synonym_of` is
different: once two skills are treated as interchangeable by search,
gap analysis, and AI grounding, their evidence, aliases, and
relationships effectively pool together in every downstream reasoning
step. An incorrect synonym (e.g. conflating "PM" as Product Management
when a curator meant Project Management in a specific context) has a
wider blast radius than an incorrect `related_to` edge. `synonym_of`
therefore keeps the same governance mechanism (no new permission tier)
but AI-suggested `synonym_of` proposals are never assigned a high
default confidence regardless of the model's own reported score, and
review tooling should surface them with a visible "merging two skills —
review carefully" warning rather than presenting them identically to a
routine `related_to` suggestion.

## Curation Workflow Example

1. A curator (or AI pipeline) creates `draft` `Skill` "Suturing" under
   Healthcare → Clinical Practice → Surgical Skills, with a
   `prerequisite_of` edge to "Minor Surgical Procedures."
2. Curator submits for review (`draft` → `in_review`).
3. A second person with `cikg.content.review`/`cikg.content.approve`
   checks the content — for an AI-suggested batch, this is where
   spot-checking against the `import_batch_id` grouping happens.
4. Approved → `approved`, now live everywhere. Rejected → back to
   `draft` with a review comment for revision.
5. Months later, a curator finds "Suturing" should really be described
   differently — this creates a **new draft version** (not an in-place
   edit of the approved row), which goes through steps 2-4 again before
   replacing what's live. The old approved version is superseded, not
   deleted (`cikg-versioning-confidence.md`).

## Related Documents

- `docs/adr/ADR-006-career-intelligence-knowledge-graph.md`
- `docs/architecture/cikg-versioning-confidence.md` — the version/confidence mechanics this workflow produces
- `docs/architecture/multi-tenancy-design.md` — the RLS/reference-data precedent this follows
- `docs/architecture/cikg-mvp-roadmap.md` — how content population is sequenced
