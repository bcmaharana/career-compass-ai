# ADR-006: Career Intelligence Knowledge Graph as Additive Reference Data

## Status
Proposed — foundational architecture only (this ADR plus
`docs/architecture/cikg-overview.md`, `cikg-ddd.md`, and
`cikg-knowledge-graph-model.md`). Not yet implemented; per the
requesting spec, implementation does not begin until this foundational
set is reviewed and approved. The remaining requested artifacts (ERD,
physical schema, API design, search strategy, AI/RAG architecture,
security/multi-tenancy detail, extensibility strategy, roadmap) follow
in a second pass once this is accepted.

## Context

A new specification ("Career Compass AI – Career Intelligence Knowledge
Graph") asks for a much larger, profession-agnostic career intelligence
model: Skills, Competencies, Roles, Industries, Technologies,
Certifications, Companies, Resume Intelligence, Interview Intelligence,
Learning, and Career Paths, all connected as a graph — plus AI features
(RAG, agents) and semantic search built on top of it.

This directly resembles what ADR-005 removed: Phase 3 originally shipped
Skill Intelligence as a full catalog-backed domain (global
`Skill`/`SkillCategory`, `RoleTag`/`SkillRoleTag` many-to-many role
matching, `UserSkill` with proficiency levels, `TargetRoleSkill` catalog
links), then stripped all of it down to plain free-text lists
(`CareerProfile.core_competencies`, `TargetRole.required_skills`) after
four iterative rounds, because the catalog was more structure than that
*specific, personal, per-user* feature needed.

The new spec is not asking for the same thing at the same scope,
though. It's asking for a **shared reference catalog** — canonical
knowledge about what skills exist, what roles require them, which
certifications validate them — used *across* tenants and users, to
power search, gap analysis grounding, and AI generation. That's a
different kind of data than "what skills does this one person say they
have," which is what ADR-005's free-text fields hold. Conflating the
two is what would make this a reversal; keeping them as clearly
distinct concerns does not.

## Decision

Build the Career Intelligence Knowledge Graph (CIKG) as a **new,
additive bounded context** — reference data, not tenant-owned data,
architecturally identical in kind to `PromptVersion`/`ModelVersion`
(`app/ai_platform/`) and platform `permissions`/`roles`
(`tenant_id IS NULL`, no RLS; see `docs/architecture/multi-tenancy-design.md`
§"What's Exempt from Tenant Scoping"). Concretely:

1. **ADR-005's free-text model is untouched.** `CareerProfile.core_competencies`
   and `TargetRole.required_skills` keep their exact current shape,
   ownership, API, and UX. No migration, no forced re-entry, no new
   validation on those fields. This ADR does not supersede ADR-005 —
   ADR-005's reasoning (a personal skill list doesn't need categories,
   proficiency, or role-tag bookkeeping) still holds for that feature.
2. **CIKG entities live in a new domain module**, `app/domain/career_intelligence/`,
   following the same layered pattern as every other domain (API →
   Application → Domain → Repository → Adapter; see
   `docs/architecture/backend-architecture.md`). Its entities (`Skill`,
   `Competency`, `Role`, `Industry`, `Technology`, `Certification`,
   `Company`, and later Interview/Learning/CareerPath entities) are
   global, versioned, curated reference data — not created ad hoc by
   end users through the product UI. `Skill` as a name is free to reuse:
   ADR-005 deleted the old catalog `Skill` class entirely, so there's no
   collision.
3. **Connection between v1 and v2 is optional and non-blocking, never a
   hard foreign key.** A free-text entry (e.g. `"Python"` in someone's
   `core_competencies`) may *resolve* to a canonical `Skill` node via a
   separate alias/matching table (`skill_alias`, detailed in
   `cikg-knowledge-graph-model.md`) — used for fuzzy-match suggestions,
   semantic search, and AI grounding wherever a match exists. No save
   path is ever blocked on a match existing. This is the one design
   choice that determines whether this stays additive or quietly turns
   into ADR-005's catalog again by the back door — it must remain
   optional by construction, not by convention or code-review vigilance.
4. **New product capabilities from the spec (Resume Intelligence,
   Interview Intelligence, Learning Intelligence, Career Paths,
   Portfolio, Personal Branding, LinkedIn Optimization, Executive
   Coaching) become their own bounded contexts** that *consume* CIKG as
   reference data, the same relationship Career Profile already has to
   nothing today but Skill Intelligence's gap analysis will gain to
   CIKG: read the graph, don't own rows in it.
5. **Modeled relationally in PostgreSQL now, graph-shaped by
   construction** — thin entities plus explicit edge tables (adjacency
   lists), not deeply nested/embedded structures — specifically so a
   future Neo4j (or other graph DB) migration is a data-export/import
   exercise, not a redesign. Detailed in `cikg-knowledge-graph-model.md`.

## Consequences

**Positive:**
- Zero risk to the working, user-validated free-text Skill Intelligence
  feature — it doesn't change at all.
- Reuses an existing, proven architectural pattern (global reference
  data alongside tenant-owned data) rather than inventing a new one.
- The optional-linking design means CIKG can be built and populated
  incrementally (even sparsely seeded) without ever being a blocker for
  existing features — a `Skill` with no matching free-text entries
  anywhere is just an unused catalog row, not a broken state.
- Every new capability in the spec (Resume/Interview/Learning/Career
  Path Intelligence) gets a consistent, already-familiar pattern to
  follow.

**Negative / accepted trade-offs:**
- Two concepts that both involve the word "skill" now exist in the
  system (a person's free-text competency string vs. a canonical
  `Skill` graph node) — mitigated by strict naming and module boundaries
  (`career_profile.core_competencies` vs. `career_intelligence.Skill`),
  but this requires discipline in code review and docs going forward,
  the same way ADR-001's module boundaries require discipline rather
  than a network boundary enforcing them.
- The catalog carries real curation cost — someone (a person or an AI
  pipeline) has to populate and maintain thousands of Skill/Role/
  Certification/Industry entities and their relationships for the
  "profession-agnostic, every industry" scope in the source spec to
  actually be true, not just structurally possible. This ADR does not
  solve that; it's a content operations question the roadmap document
  (final deliverable) needs to address explicitly.
- Soft/optional linking means the graph's value to existing features is
  only as good as the matching quality (fuzzy-match/alias resolution) —
  an unlinked "Python" entry gets none of the graph's benefit until
  matched. This is an accepted, deliberate trade-off (see Decision
  point 3) — the alternative (mandatory linking) is exactly what ADR-005
  rejected.

## Revisit Trigger

If, after this is built, product direction genuinely requires *forcing*
every personal skill entry through the canonical catalog (e.g. for
strict cross-tenant analytics or compliance reasons), that is a new,
explicitly-scoped decision — not a quiet tightening of this one's
"optional" linking rule.
