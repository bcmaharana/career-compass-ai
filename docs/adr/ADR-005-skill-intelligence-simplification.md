# ADR-005: Simplify Skill Intelligence to Plain Free Text

## Status
Accepted

## Context
Phase 3 shipped Skill Intelligence as a full catalog-backed domain, mirroring Career Profile's layering: global `SkillCategory`/`Skill` reference data, `RoleTag`/`SkillRoleTag` many-to-many role matching, tenant-owned `UserSkill` rows with 4-level proficiency and manual reordering, and `TargetRoleSkill` link rows attaching catalog skills to a `TargetRole` as "required." `GapAnalysisService` blended two computations: target-role-driven gaps (required catalog skills the user doesn't own) and catalog-category-driven "core gaps" (core skills missing in categories the user already has at least one skill in).

On review after four iterative rounds, the user decided this was more structure than the feature needed. My Skills was meant to just mirror Career Profile's existing Core Competencies (a plain string list) rather than be its own catalog-backed inventory, and Target Role Skill Requirements didn't need categories, proficiency, or role-tag matching either — just a free-text list per role, the same shape.

## Decision
Remove the catalog/proficiency/category model entirely:

- Drop `Skill`, `SkillCategory`, `RoleTag`, `SkillRoleTag`, `UserSkill`, `TargetRoleSkill` (domain entities, repositories, DB tables, migrations, seed script, unit tests) and the application services built on them (`SkillCatalogService`, `UserSkillService`, `TargetRoleSkillService`).
- **My Skills** is not a new entity — it *is* `CareerProfile.core_competencies`, the same field Career Profile's Core Competencies card already edits. The Skill Intelligence page's My Skills card is a second view/editor over that same field (immediate-commit add/remove, rather than Core Competencies' batch Edit/Save), so the two are trivially always in sync — there is no sync mechanism because there's only one copy of the data.
- **Target Role Skill Requirements** becomes `TargetRole.required_skills: list[str]`, a plain JSON column living directly on `TargetRole` (`app/domain/career_profile/entities.py`), the same shape as `core_competencies`. `TargetRoleService` gained `add_required_skill`/`remove_required_skill` (case-insensitive dedup), reusing the existing `get_owned_or_raise` ownership check rather than a separate service depending cross-domain on `TargetRoleService` as before.
- **Gap Analysis** (the only piece left under `app/application/skill_intelligence/`) is pure computation with no storage of its own: for each target role, `required_skills` minus `core_competencies`, matched case-insensitively. The catalog-driven "core gaps" half is dropped entirely — there are no categories left to drive it.

## Consequences
**Positive:**
- Far less code and no schema to keep consistent across three related-but-separate entities (Skill, UserSkill, TargetRoleSkill) for what is, in practice, tag-list data.
- My Skills and Core Competencies can never drift, by construction — same field, same source of truth.
- Adding a required skill to a target role no longer requires deciding whether it's a "new catalog skill" or an "existing one," resolving categories, or role-tag bookkeeping — just a string.

**Negative / accepted trade-offs:**
- Loses whatever the catalog would have provided later: consistent skill naming across users/tenants, category-based browsing, a controlled taxonomy for future analytics or matching. If that's needed again, it would be a new, deliberately-scoped feature rather than a revival of this one.
- The catalog-driven "core gaps" gap-analysis half (skills missing in categories a user is already active in) has no replacement — Gap Analysis is now target-role-driven only.
- Four rounds of prior work (multiple migrations, ~92 passing unit tests touching the old shape) are removed rather than carried forward; this is a real reversal, not an incremental change.

## Revisit Trigger
If a future phase needs cross-tenant consistent skill naming, skill-based matching/search, or category-based browsing, that would justify reintroducing a catalog — as a new, explicitly-scoped decision, not by resurrecting this one.
