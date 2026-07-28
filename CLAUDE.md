# Career Compass AI — Project Context for Claude Code

This file is read automatically at the start of every Claude Code session.
It exists so context isn't lost between sessions — the "why," the
gotchas, and the conventions that aren't obvious from the code alone.
**Read `docs/architecture/`, `docs/adr/`, and `docs/runbooks/` for full
detail** — this file is a map to those, plus the things worth knowing
before touching anything.

## What this is

Career Compass AI: an enterprise, multi-tenant, AI-native career
intelligence SaaS platform. Individuals build a living career profile;
organizations run workforce development on top of it; AI is a governed
platform capability, not a bolted-on feature. Full vision in
`docs/architecture/system-overview.md`.

## Stack

- **Backend**: Python 3.12, FastAPI (async), SQLAlchemy 2.0 (async),
  Alembic, PostgreSQL 16 (pgvector-enabled), Redis, MinIO (S3-compatible)
- **Frontend**: React 18 + TypeScript, Vite, Tailwind CSS, shadcn/ui
  conventions, TanStack Query, Zustand, React Router
- **Infra**: Docker Compose (`infra/docker-compose.yml`) — this is the
  **primary** way the user runs everything now, not native processes.
  See "Environment" below.
- **Auth**: JWT (HS256), Argon2id password hashing, sliding-session
  refresh (see below)

## Architecture — non-negotiable layering

```
API (routers)  →  Application Services  →  Domain Services  →  Repository Interfaces  →  Adapters
```

- **`app/api/`**: thin routers only. Parse input, call one application
  service, map result to a response schema. Zero business logic.
- **`app/application/`**: use-case orchestration. No FastAPI, no
  SQLAlchemy imports.
- **`app/domain/`**: pure business logic. Zero framework imports —
  plain dataclasses only. This is what's unit-tested without a database.
- **`app/adapters/`**: the *only* place SQLAlchemy models, boto3, or any
  infra SDK is imported. `app/adapters/db/models/` and
  `app/adapters/db/repositories/` are split **per domain** (identity.py,
  career_profile.py, etc.) — add a new file per domain, don't grow an
  existing one.
- **`app/core/`**: config, security primitives, logging, the
  domain-safe exception hierarchy, cross-cutting interfaces
  (`IdentityProviderInterface`, etc.).

Every new domain follows this same shape:
`domain/<name>/entities.py` (dataclasses) →
`domain/<name>/repositories.py` (Protocol ports) →
`application/<name>/*_service.py` (one service class per entity,
methods for each use case — not one-class-per-verb like Identity's
`RegisterTenantService` pattern, which is reserved for genuinely
distinct multi-step workflows) →
`adapters/db/models/<name>.py` + `adapters/db/repositories/<name>.py` →
`api/v1/<name>/schemas.py` + `router.py`.

## Multi-tenancy — Row-Level Security

Shared DB, shared schema, `tenant_id` on every tenant-owned table,
enforced by Postgres RLS — **not just application-level filtering**.
Full design in `docs/architecture/multi-tenancy-design.md`. Three things
that will bite you if forgotten (each was a real bug caught by testing,
not review):

1. **`FORCE ROW LEVEL SECURITY` is required**, not just `ENABLE` —
   otherwise the table owner (the app's own DB role) silently bypasses
   RLS entirely.
2. **Use `current_setting('app.tenant_id', true)`** (the `missing_ok=true`
   form) in every RLS policy — the plain form raises "unrecognized
   configuration parameter" for any session that's never touched the
   variable (seed scripts, admin tools, fresh pooled connections), not
   just an empty-string comparison.
3. **Use `set_config('app.tenant_id', :value, true)`**, never
   `SET LOCAL app.tenant_id = :value` — Postgres's `SET LOCAL` does not
   accept bound/parameterized values at all; it only works with a
   literal, and fails at the point psycopg tries to send it as a
   parameterized statement.
4. **Migrations that backfill data across all tenants must temporarily
   `DISABLE ROW LEVEL SECURITY`** on the affected tables, then
   re-`ENABLE`+`FORCE` it — Alembic runs with no `app.tenant_id` context
   set, so RLS silently blocks the migration's own UPDATE otherwise,
   leaving every row at whatever default was specified.

Reference-data tables (`permissions`, `roles` with `tenant_id IS NULL`)
are the deliberate exceptions — not every table gets RLS.

## Reordering pattern (used by Experience, Education, Certifications,
Career Goals, Highlights, Achievements, Recommendations)

Every orderable entity has a `display_order` integer column and a
`move(direction: "up"|"down")` operation. The swap logic is centralized
in `app/adapters/db/reorder.py` (`move_item`, `next_display_order`) —
every repository's `move()` delegates to it rather than reimplementing
the swap. New orderable entities should follow this same pattern, not
invent a new one.

## AI Platform (scaffolded, not yet wired to a real feature)

`app/ai_platform/` has interfaces and in-memory reference
implementations for `LLMProviderInterface`, prompt registry, model
registry, and invocation logging — built in Phase 0 specifically so
nothing gets written against a temporary shortcut before the real
Anthropic provider is wired in (Phase 4 per the original roadmap). See
`docs/architecture/ai-platform-architecture.md` and
`docs/adr/ADR-004-ai-governance-strategy.md`. Every AI-generated
recommendation is designed to carry `confidence_score`,
`reasoning_metadata`, and `source_data_ref` for explainability, and
tenants can require human review before an AI output reaches an end
user — this is a data-model decision made early, not an afterthought.

## Auth: sliding session

JWT access tokens (60 min). No refresh-token endpoint exists — instead,
`app/api/dependencies.py`'s `get_current_identity` reissues a fresh
token via an `X-Refreshed-Token` response header once the current token
is past the halfway point of its lifetime. The frontend's `apiClient`
(`frontend/src/api/client.ts`) checks for that header on every response
and silently swaps the token in. Active use keeps extending the
session; genuine idle time still expires it. See
`tests/unit/test_token_refresh.py` for the exact mechanics.

**Any field added to `IdentityClaims` must be threaded through four
places, or it silently vanishes on the next token refresh** — this has
been the actual bug three separate times (`first_name`/`last_name`,
`last_login_at`, `salutation`): `verify_access_token()` (decode with a
`.get()` fallback, since already-issued tokens predate the new claim),
`authenticate_with_credentials()` (encode on login),
`issue_access_token()`'s `extra_claims` (encode into the token), and
`_refresh_token_if_stale()` in `app/api/dependencies.py` (the
sliding-session refresh path — easiest one to forget, since nothing
fails loudly when it's missed, the claim just quietly drops out of any
token minted after the halfway-life refresh).

## Testing philosophy

- `tests/unit/`: fast, no infrastructure, fake in-memory repositories
  implementing the same Protocol as the real one. **Fakes must return
  copies on fetch, not live object references** — a fake that returns
  the same object every call caused a real, hard-to-spot test bug where
  two sequential updates appeared to collapse into one (see
  `tests/unit/test_career_profile_service.py`'s `FakeCareerProfileRepository`
  docstring for the full story).
- `tests/integration/`: real Postgres (`career_compass_test` DB),
  real HTTP calls via httpx against the actual FastAPI app — exercises
  RLS, ownership checks, and cross-tenant isolation for real, not mocked.
- Every RLS/migration claim in this codebase has been verified by
  actually inserting cross-tenant test data and checking results, not
  just by reading the SQL. Keep that standard — reason about correctness,
  then verify it against a real database before calling something fixed.
- mypy is **hybrid strict**: `--strict` everywhere except
  `app.adapters.db.*` (SQLAlchemy's declarative class typing doesn't
  play well with strict Protocols — this is a documented, narrow
  exception, not a general escape hatch). See `backend/pyproject.toml`.

## Environment — Docker is the source of truth now

The user runs the **backend via Docker Compose**, not native `uvicorn`,
after working through several rounds of environment issues. Two
PowerShell scripts at the repo root handle the common flows:

- **`start-dev.ps1`** — run after every machine/Docker restart. Brings
  up Postgres/Redis/MinIO/backend, applies migrations, seeds platform
  defaults, launches the frontend dev server in a new window.
- **`sync-dependencies.ps1`** — run whenever `pyproject.toml` or
  `package.json` gains a new dependency. Rebuilds the backend Docker
  image, syncs the native venv (for editor/ruff/mypy support), runs
  `npm install`.

**If you edit either `.ps1` script: ASCII only, no em-dashes or smart
quotes.** Windows PowerShell 5.1 misreads non-ASCII characters without a
BOM and throws confusing parse errors ("missing closing paren") that
have nothing to do with the actual code. This has happened once already.

Known environment gotchas already solved, don't reintroduce:

- **`DATABASE_URL`** inside the Docker backend container must use the
  service name (`postgres`), never `localhost` — `localhost` inside a
  container means the container itself.
- **Object storage has two different addresses**: `OBJECT_STORAGE_ENDPOINT`
  (what the *backend* uses to reach MinIO — `http://minio:9000` in
  Docker) vs `OBJECT_STORAGE_PUBLIC_URL` (what the *browser* uses to
  load an uploaded file — `http://localhost:9000`, since the browser
  never resolves Docker service names). Using one value for both breaks
  one side or the other.
- **boto3's S3 client requires `region_name`** even against MinIO (which
  ignores the value) — omitting it isn't an error at client-construction
  time, only surfaces later.
- **Dockerfile build order matters**: source must be `COPY`'d before
  `pip install .` runs, or setuptools finds zero local packages to
  install (dependencies still install fine, masking the issue until
  something tries to `import app` outside of uvicorn's own
  cwd-based import resolution — e.g. running a plain script directly).
- **Photo URLs need cache-busting** on re-upload — the storage *key* is
  stable per profile (so old photos don't accumulate), but that means a
  stable URL too, which the browser's image cache won't re-fetch unless
  the URL string itself changes. A timestamp query param is appended at
  upload time.
- **API responses set `Cache-Control: no-store`**, and the frontend's
  fetch wrapper sets `cache: "no-store"` — this is a fully dynamic,
  per-tenant API; nothing it returns should ever be cached by a browser
  or intermediary.
- **`infra/docker-compose.yml` only bind-mounts `backend/app` and
  `backend/scripts`** into the backend container — `backend/alembic` is
  not mounted. A migration generated via
  `docker compose exec backend alembic revision` (or hand-edited on the
  host afterward) exists only inside the container until explicitly
  `docker cp`'d in. Running `alembic upgrade head` against a host-only
  edit silently runs the container's stale copy, stamps the revision as
  applied, and changes nothing — no error is raised. Always `docker cp`
  the finished migration file into the container before upgrading; if a
  no-op already got stamped, `alembic stamp <previous-revision>` then
  re-run `upgrade head`.

## Frontend conventions

- **No React state should reactively re-sync from a TanStack Query
  result while a user has unsaved local edits in progress.** A `useEffect`
  keyed on query data looked harmless but caused a real bug: any
  background refetch (even from an unrelated mutation elsewhere on the
  same page) silently overwrote in-progress form edits before the user
  had saved them. Local form state should be initialized once,
  explicitly, at the moment an edit UI opens (see `ProfileHeader.tsx`'s
  `openEdit()`) — never kept in sync reactively afterward.
- **Mutations should write confirmed server responses directly into the
  query cache** (`setQueryData`) rather than only `invalidateQueries` —
  invalidate-and-refetch leaves a window where stale data is still
  displayed, and (per the point above) can race against in-progress edits.
- Design tokens, typography (Sora/Inter/IBM Plex Mono), and the
  dependency list are intentionally minimal — no Radix, no heavy UI
  kit. The `Dialog` component is hand-rolled; it does **not** close on
  backdrop click (only Escape/explicit close), because a `<textarea>`'s
  native resize-handle drag can end outside the dialog bounds and
  trigger a false "outside click."
- Dates are stored/transmitted as ISO strings; displayed via
  `frontend/src/lib/date-format.ts` (`dd-mmm-yyyy`). Native
  `<input type="date">` still uses the browser's own format for editing
  — that's a platform limitation, not a bug.
- A tag-style input (see Core Competencies) must commit pending
  uncommitted text on **both** Enter/comma **and** on Save/blur — a real
  bug shipped where typing a value and clicking Save directly (without
  pressing Enter first) silently dropped it, caught only via a browser
  DevTools Network-tab capture showing the empty array actually being sent.
- **Rainbow accent design language** (replaced the earlier single plum
  accent color, applied to nearly every interactive/branded element:
  buttons, active nav states, borders, icons, gradient text): the
  literal gradient class string
  `bg-[linear-gradient(90deg,#a855f7_12.5%,#3b82f6_37.5%,#22c55e_58.33%,#fdba74_75%,#fca5a5_91.67%)]`
  is duplicated across every file that uses it, not extracted into a
  shared JS constant — Tailwind's JIT scanner needs a statically
  analyzable literal class string per file, so a template-literal
  constant silently fails to compile. An SVG stroke can't pick up a
  Tailwind background gradient via `currentColor`, so icon strokes use
  a hidden `<svg><defs><linearGradient id="rainbow-accent-gradient">`
  (one per independently-rendered React tree — `AppShell` has one,
  `LoginPage` needs its own since it renders outside `AppShell`'s route
  tree) plus `<Icon color="url(#rainbow-accent-gradient)" />`. A
  gradient *border* on a rounded element can't use CSS `border-image`
  (it ignores `border-radius`, producing square corners) — use the
  nested-div padding trick instead: an outer `rounded-lg bg-[gradient]
  p-{N}` wrapping an inner `border-0` element, where `p-{N}` sets the
  visual border width.
- **Left Nav vs Right Nav split**: Left Nav (`AppShell.tsx`) is always
  the same 4 top-level items regardless of route. Right Nav
  (`RightNav.tsx`) is the one that changes per page — plain structural
  placeholder by default, the Career Profile page's target-roles widget
  on `/profile`, or the Settings sub-nav (`SETTINGS_NAV_ITEMS` from
  `frontend/src/lib/nav-items.ts`) under `/settings/*` — with
  Settings/Sign-out pinned to its bottom box regardless of section.
  Route-to-section matching goes through `matchNavItem()`/
  `isSettingsRoute()` in that same file, not ad hoc `pathname` checks.
- **Country-aware phone formatting**: `libphonenumber-js`'s
  `AsYouType(countryCode)` reformats the phone input live, both as the
  user types and whenever the Country `<select>` changes (see
  `SettingsProfilePage.tsx`'s `formatPhoneForCountry`). It only applies
  a pattern once the digits match a plausible national format for that
  country (e.g. a GB number needs the leading trunk `0`) — an
  unrecognized sequence passes through as plain digits, which is
  expected library behavior, not a bug.
- **Structured, country-aware address fields**: `address_line1`,
  `address_line2`, `city`, `state`, `postal_code` are separate columns
  (see `User` entity), not one free-text field — the frontend chooses
  labels/layout/order based on the selected `country` (US: State + ZIP
  side by side; everywhere else: Postal code + State/Province
  (optional)), the same "backend stores atomic components, frontend
  decides country-specific presentation" split used for phone
  formatting. Country and language display names come from the
  built-in `Intl.DisplayNames` API (`frontend/src/lib/locale-options.ts`)
  rather than a bundled name list.

## Current status (as of this handoff)

- **Phase 0** — repo foundation, FastAPI skeleton, health check, testing
  harness, AI Platform interfaces: done.
- **Phase 0.2** — frontend foundation, design system, routing, typed API
  client, auth placeholder: done.
- **Phase 1** — Tenant/Organization/User/Role/Permission, RLS, JWT auth
  (`InternalJWTProvider`), RBAC (`require_permission`), audit logging,
  feature flags: done. 
- **Phase 2** — Career Profile Core, expanded well beyond the original
  scope based on user feedback: CareerProfile (headline, executive
  summary, core competencies, photo), Experience ("Professional
  Experience," with a Present-role checkbox), Education, Certifications,
  Career Goals, Career Highlights, Key Achievements, Peer Endorsements
  (self-managed testimonials) — all with full CRUD, ownership checks,
  soft delete, and manual reordering. Done and iterated through several
  rounds of real user bug reports.
- **UI enhancement round** (post-Phase 2, pre-Phase 3) — done. Global
  app shell: four always-fixed regions (Left Nav, Header, Footer, Right
  Nav) around one scrollable center panel, sized off shared `--shell-*`
  CSS variables so the fixed regions and the center panel's insets can
  never drift out of sync. Footer AI Chat: UI shell, message list,
  auto-scroll, and real DB persistence (`app/domain/chat/`) — the
  assistant reply is a placeholder echo
  (`ChatService._placeholder_reply`) until the AI Platform is wired to a
  live provider (Phase 4/8 territory). Header: per-route page
  name/purpose (`frontend/src/lib/nav-items.ts`) plus a quote of the day
  from an external API behind a small backend adapter
  (`app/adapters/quotes/`), swappable later without touching the
  frontend. Right Nav: user identity/date/time/Settings, plus a
  Career-Profile-specific target-roles widget — its own entity with a
  stable id (`TargetRole` in `app/domain/career_profile/`), not a plain
  string list, specifically so future tagging of profile items against
  a role won't need a rewrite. Career Profile page: every section
  collapsible, alternating card backgrounds computed from each section's
  *current* render position (not hardcoded — sections are now
  user-reorderable, with the order persisted via
  `CareerProfile.section_order`), bold/italic/colored dates everywhere,
  Core Competencies and Executive Summary split out into their own
  cards, the photo/headline strip now a page-level sticky element with
  Executive Summary onward scrolling normally beneath it, and
  confirm-before-delete (`ConfirmDialog`) on every delete action.
- **Phase 3** — Skill Intelligence, since simplified to plain free text
  (see ADR-005). Originally shipped as a full catalog-backed domain
  (global `Skill`/`SkillCategory`, `RoleTag`/`SkillRoleTag` many-to-many
  role matching, `UserSkill` with proficiency levels, `TargetRoleSkill`
  catalog links, a blended target-role + catalog-category gap analysis)
  across four iterative rounds — then, on explicit user review, that
  entire catalog/proficiency/category model was removed as more than the
  feature needed. Current shape: **My Skills** is not a separate entity
  at all — it's the exact same field as Career Profile's Core
  Competencies (`CareerProfile.core_competencies`, a plain
  `list[str]`), just a second card/view on the `/skills` page with its
  own immediate-commit add/remove UX (Core Competencies keeps its
  original Edit/Save batch UX; both read/write the same field, so
  they're trivially always in sync). **Target Role Skill Requirements**
  is `TargetRole.required_skills: list[str]` — a plain JSON column
  living directly on `TargetRole` (`app/domain/career_profile/entities.py`),
  with add/remove methods on `TargetRoleService`
  (`add_required_skill`/`remove_required_skill`, case-insensitive
  dedup) reusing the existing `get_owned_or_raise` ownership check —
  no separate link table, no rename (nothing shared left to rename).
  **Gap Analysis** (`app/application/skill_intelligence/gap_analysis_service.py`,
  the only file left in the `skill_intelligence` app layer) is pure
  computation with no storage of its own: for each of the user's target
  roles, `required_skills` minus `core_competencies`, matched
  case-insensitively — the catalog-driven "core gaps" half was dropped
  entirely along with categories. Page layout at `/skills`
  (`frontend/src/features/skill-intelligence/`) is unchanged: three
  fixed sections (My Skills, Target Role Skill Requirements, Gap
  Analysis). The "+Add" affordance on Target Role Skill Requirements
  moved to a top-right button (was a bottom-left text link). Every
  delete action in this domain (and going forward, every domain)
  confirms first via `ConfirmDialog` — a standing default, not decided
  per-feature.
- **UI redesign round 2 + Settings + Profile enrichment** (post-Phase 3)
  — done. Nav/visual overhaul: the single plum accent color was replaced
  by the rainbow gradient design language described under "Frontend
  conventions" above, applied to buttons, active nav states, borders,
  and icons throughout; Left Nav is now always the same 4 items on
  every route, with Right Nav owning per-page context (target-roles
  widget, Settings sub-nav) plus Settings/Sign-out pinned to its bottom
  box. A real **Settings > Profile** self-service page
  (`frontend/src/features/settings/SettingsProfilePage.tsx`,
  `PATCH /api/v1/identity/me`,
  `app/application/identity/update_user_profile.py`) replaced what had
  been placeholder/hardcoded name data — this is also why `User` gained
  proper separate `first_name`/`last_name` fields (previously only a
  blended `full_name`/`display_name` existed) and a real `last_login_at`
  column (captures the *previous* login, read before the new login
  overwrites it, so "Last logged in" never drifts to "now"). The Right
  Nav identity box shows a time-of-day greeting plus the user's name in
  formal salutation order — "Salutation Lastname, Firstname" (e.g.
  "Mr. Smith, John") — deliberately not the blended `full_name`, which
  reads "Salutation Firstname Lastname". The Settings > Profile form was
  then extended with `phone_number`, `country`, `language`, and a
  structured (not single-field) `address` — see "Frontend conventions"
  for the country-aware formatting/layout details. Every field added
  here also had to be threaded through the JWT claims propagation
  points described under "Auth: sliding session" above, since the Right
  Nav reads identity from the in-memory auth store (populated at login/
  profile-save), not a live `/me` call on every render.
- **Not yet started**: Phase 4 (AI Platform real wiring) onward through
  Phase 9. Domain list in `docs/architecture/system-overview.md`; that
  doc doesn't enumerate a numbered phase-by-phase roadmap the way this
  section does — the phase numbers (1 Identity, 2 Career Profile,
  3 Skill Intelligence, 4 AI Platform real wiring, 5 Resume
  Intelligence, 6 Opportunity Intelligence, 7 Learning Intelligence,
  8 AI Career Coach) are tracked here and in project memory only.

## Working conventions this user expects

- Complete, real code — no pseudo-code, no placeholders.
- Claims of "this works" should be backed by actually running it
  (migrations against a real DB, live HTTP calls, real test runs) —
  this user has caught multiple real bugs specifically *because*
  changes were verified live rather than just reasoned about. Keep
  doing that.
- Update `docs/adr/` when a real architectural decision changes;
  update `docs/architecture/` when a design detail changes; don't let
  these drift from what's actually implemented.
- The user is on Windows, using Docker Desktop + Docker Compose for the
  backend and native `npm run dev` for the frontend. Assume that
  environment unless told otherwise.