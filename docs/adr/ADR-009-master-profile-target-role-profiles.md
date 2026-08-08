# ADR-009: Master Profile + Target Role Profiles

## Status
Accepted

## Context
Career Profile had exactly one `CareerProfile` per user, and resume merge (`ResumeMergeService`) was unconditionally additive with real but exact-string-match dedup. Across a multi-day resume-upload testing session, this produced a real, user-facing problem: repeated uploads — some tagged to a target role, some not, some from before prompt-quality fixes landed and some after — all wrote into the same single profile with zero warning when data already existed. Because dedup only catches exact string matches, differently-worded extractions of the same underlying resume section (a reversed skill/category pair, a hallucinated certification name, a misclassified career-highlight entry) coexisted rather than replacing each other, making the profile look corrupted even though every individual write was working as designed.

Investigation (backed by direct queries against the real Postgres data, not just log inspection) traced this to two compounding gaps: no per-target-role storage at all — `Resume.target_role_id` was already captured at upload time but never consumed by merge — and no user-facing choice when a destination already had content. The user's explicit requirement: an upload should never silently blend into old data; if the destination already has data, ask **override or merge**.

## Decision
Introduce a real Master Profile / Target Role Profile split, and route resume merge through it:

- **`career_profiles` gains a nullable `target_role_id`** (FK to `target_roles.id`). `NULL` = Master Profile (today's single profile, unchanged in spirit). A real id = one of this user's up to 10 independent Target Role Profiles (`TargetRoleService.MAX_TARGET_ROLES`) — a fully separate row, not a filtered view of Master. **No child table schema changes** — `experiences`, `educations`, `certifications`, `career_highlights`, `key_achievements` already scope via `career_profile_id`, so a Target Role Profile's children are just rows pointing at that profile's own row.
- **Two partial unique indexes**, not one composite one — Postgres treats NULLs as distinct in a standard unique index, so a single `UNIQUE(tenant_id, user_id, target_role_id)` would not stop a second Master row per user. One index covers `target_role_id IS NULL`, the other `target_role_id IS NOT NULL`.
- **Career Goals and Peer Endorsements stay Master-only** — resume merge never touches either, and there's no clear use case yet for per-target-role goals/endorsements. Photo and `career_readiness_score` also stay Master-only (one professional photo, not one per role; resume merge doesn't touch either).
- **`ResumeMergeService.merge()` reads `resume.target_role_id` server-side** and routes every write there — the resume's own tag (already captured at upload) determines the destination; no new client-supplied field. Its existing per-section dedup logic is unchanged, just now scoped correctly.
- **Override vs. Merge is a frontend-orchestrated choice over two existing primitives**, not new backend merge logic: a new `GET /career-profile/summary?target_role_id=` endpoint gives real counts (not just a yes/no) for the decision; **Merge** calls the existing merge endpoint directly; **Override** calls the existing (now target-role-aware) `DELETE /career-profile?target_role_id=` first, then merge.
- **A real correctness bug was fixed while threading the new parameter**: every child service's `_get_owned_or_raise()` resolved "the profile" via `get_or_create(tenant_id, user_id)`, which always means Master. Once Target Role Profiles exist, that would have made editing/deleting/moving any item that actually lives on a Target Role Profile 404. Fixed to resolve ownership from the item's own `career_profile_id` instead — no new parameter needed there, and strictly more correct than before.
- **Frontend scope is carried via a `?role=` URL search param** on `/profile` (not component state) — shareable, survives a refresh, consistent with this app's existing route-based-switching precedent (Settings sub-nav). A `ProfileScopeContext` threads the resolved scope to each of the 6 target-role-scoped section components without prop-drilling.
- **Manual editing gets a "Copy from Master" picker**, not a sync: each Target Role Profile section's Add form can pre-fill from a Master item the user picks, editable before saving, with no link back afterward.

## Consequences
**Positive:**
- The triggering bug is directly fixed: a resume upload can no longer silently accumulate into the wrong (or an already-populated) profile without the user being told.
- Minimal schema churn — one nullable column, two partial indexes, zero child-table changes — because the design reuses `career_profile_id` as the existing scoping mechanism rather than inventing a new one.
- `_get_owned_or_raise`'s fix is a genuine correctness improvement independent of this feature, verified via a live integration test (`TestTargetRoleProfileIsolation::test_editing_an_item_on_a_target_role_profile_succeeds`) that would fail under the old resolution logic.

**Negative / accepted trade-offs:**
- Data duplication is real and intentional: two Target Role Profiles can list the same employer with differently-worded descriptions, and nothing keeps them in sync after a "Copy from Master." This matches how people actually tailor resumes per role, but it is a maintenance cost the user accepts explicitly (confirmed during design) rather than an oversight.
- Deleting a Target Role orphans its profile data (soft-deleted role, unreachable but not deleted `career_profiles` row and children) — matches this app's existing never-hard-delete philosophy, but means storage grows with abandoned target roles. No cascade-delete was built; revisit if this becomes a real cleanup problem.
- "Copy from Master" was built for the 5 list-type sections (Experience/Education/Certifications/Career Highlights/Key Achievements) but not Core Competencies, whose tag-based add flow is shared with the Skill Intelligence page and would need a shared-dialog API change to support it cleanly — deliberately deferred rather than rushed.

## Revisit Trigger
If Career Goals or Peer Endorsements ever need per-target-role variants, or if orphaned Target Role Profile data becomes a real storage/privacy concern, both would be new, explicitly-scoped follow-ups rather than silent extensions of this decision.
