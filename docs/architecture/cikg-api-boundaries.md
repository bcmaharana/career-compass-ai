# CIKG — API and Service Boundaries

Second-pass addendum. Not a full endpoint-by-endpoint specification
(each MVP slice designs its own request/response schemas as it's
built, the same granularity every other domain in this codebase
already follows) — this defines the resource hierarchy, which module
owns which endpoints, the read/write permission boundary, and how
existing endpoints stay backward compatible as CIKG attaches to them.

## New Domain Module

Following the existing layering convention
(`docs/architecture/backend-architecture.md`) exactly — no new pattern:

```
app/domain/career_intelligence/
    entities.py       # Skill, SkillCategory, Role, Competency, Industry,
                       # Technology, Certification, Company, CareerPath,
                       # InterviewQuestion, LearningResource, CareerLevel,
                       # CareerTrack — plain dataclasses
    repositories.py    # Protocol interfaces per entity + edge repositories
app/application/career_intelligence/
    skill_service.py, role_service.py, ...      # read-oriented, per-entity
    search_service.py                            # cikg-semantic-search.md
    content_governance_service.py                 # the revision/approval workflow —
                                                    # one-class-per-verb shape (RegisterTenantService's
                                                    # pattern), since review/approve/reject/deprecate
                                                    # is a genuinely distinct multi-step workflow,
                                                    # not "one service per entity"
app/adapters/db/models/career_intelligence.py
app/adapters/db/repositories/career_intelligence.py
app/api/v1/career_intelligence/
    schemas.py, router.py
```

`SkillEvidence` (`cikg-skill-evidence.md`) is **not** in this module —
it's tenant-owned personal data and belongs under
`app/domain/career_profile/`, alongside `Experience`/`Certification`/
`PeerEndorsement`, the entities it links to. This mirrors the
conceptual boundary `cikg-ddd.md` already draws: CIKG owns reference
data only, never personal data, even personal data that references it.

## Resource Hierarchy

All under `/api/v1/career-intelligence/`, matching the source spec's
requested shape (`/skills`, `/roles`, `/competencies`, ...) and this
codebase's existing `/api/v1/<domain>/` convention:

| Resource | Read access | Write access |
|---|---|---|
| `/skills`, `/skills/{id}`, `/skills/{id}/related` | Any authenticated user | Via `/revisions` only (below) |
| `/roles`, `/roles/{id}` | Any authenticated user | Via `/revisions` only |
| `/competencies`, `/industries`, `/technologies`, `/certifications`, `/companies`, `/career-paths` | Any authenticated user | Via `/revisions` only |
| `/categories` (SkillCategory hierarchy browse) | Any authenticated user | Via `/revisions` only |
| `/career-levels`, `/career-tracks` (`cikg-career-levels.md`) | Any authenticated user | `cikg.content.admin` only (a managed reference scale, not routine content) |
| `/search` (`cikg-semantic-search.md`) | Any authenticated user | — (read-only endpoint) |
| `/revisions` (`cikg-versioning-confidence.md`'s `content_revision`) | `cikg.content.review`+ (curators see the queue) | `cikg.content.create` to propose, `cikg.content.review` to move to `in_review`, `cikg.content.approve` to approve/reject |
| `/observability/*` (`cikg-observability.md` metrics) | `cikg.content.*` (any curator role) | — (read-only reporting) |

No CIKG resource is ever writable directly (`PATCH /skills/{id}` does
not exist) — every change is `POST /revisions`, enforcing that nothing
bypasses the governance workflow (`cikg-content-governance.md`) through
a shortcut endpoint. This is a deliberate constraint on the API surface
itself, not just a convention curators are expected to follow.

`SkillEvidence` endpoints live under the existing career-profile
namespace, not here: `POST/GET/DELETE /api/v1/career-profile/skill-evidence`
— self-service, tenant-scoped, no `cikg.content.*` permission involved,
following the same ownership pattern every other Career Profile
sub-resource already uses.

Agent endpoints (`cikg-ai-agents.md`) are a separate future namespace —
`/api/v1/agents/{agent_type}/...` — outside this document's scope
beyond noting the boundary: agents call *into* `career_intelligence`'s
read services and `career_profile`'s services (including
`SkillEvidence`) as internal application-service calls, never by
hitting these HTTP endpoints themselves (an agent runs inside the same
backend process; there's no reason for it to make an HTTP round-trip to
its own API).

## Backward-Compatible Attachment to Existing Endpoints

ADR-006 §3 is explicit that `CareerProfile.core_competencies` and
`TargetRole.required_skills` don't change shape. Where the optional
`skill_alias` resolution needs to surface (e.g. showing a user "this
matches a skill in our catalog" or enabling gap-analysis enrichment),
it's an **additive, nullable field alongside the existing one**, never
a replacement:

```jsonc
// CareerProfileResponse — existing field unchanged, one field added
{
  "core_competencies": ["Python", "Stakeholder Management"],   // unchanged
  "core_competencies_resolved": [                              // new, optional
    {"text": "Python", "skill_id": "…-uuid…"},
    {"text": "Stakeholder Management", "skill_id": null}       // no match yet — fine
  ]
}
```

This is the same additive-field, tolerant-fallback discipline
`CLAUDE.md` already documents for `IdentityClaims` (new JWT claims
added via `.get()` with a fallback so old tokens don't break) applied
to response schemas instead of tokens: existing frontend code that
doesn't know about `core_competencies_resolved` keeps working
unmodified, and `npm run generate:api-types` picks up the new optional
field the same way it already does for any additive schema change.

## Versioning Strategy

No new versioning scheme — CIKG endpoints live in the existing
`/api/v1/` namespace like every other domain, and this codebase has
never needed a `v2` because schema evolution so far has been additive
(new optional fields, new endpoints) rather than breaking. CIKG follows
the same discipline: a genuinely breaking change to a CIKG resource
shape would be the trigger for a `v2` of *that resource specifically*,
not a platform-wide version bump — consistent with how this monolith's
modules are already independently versionable in principle (ADR-001).

## GraphQL Readiness

The source spec asks that the API "be designed so future GraphQL
support can be added without breaking." The resource-per-node-type REST
design above already satisfies this structurally: each REST resource
maps to a natural GraphQL type (`Skill`, `Role`, ...), and each edge
table maps to a natural resolver (`Skill.relatedSkills`,
`Role.requiredSkills`) without needing to redesign the underlying
`career_intelligence` application services — a GraphQL layer, if ever
added, would be a new API-layer adapter calling the same application
services the REST routers call today, per the existing layering
principle that application services never know which API shape is
calling them.

## Related Documents

- `docs/architecture/cikg-content-governance.md` — why writes only ever go through `/revisions`
- `docs/architecture/cikg-skill-evidence.md` — why evidence endpoints live outside this module
- `docs/architecture/backend-architecture.md` — the layering convention this follows
- `CLAUDE.md` — the additive-field/`.get()`-fallback discipline this reuses for response schemas
