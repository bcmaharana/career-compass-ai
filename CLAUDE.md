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
after working through several rounds of environment issues. PowerShell
scripts at the repo root handle the common flows:

- **`start-dev.ps1`** — run after every machine/Docker restart. Brings
  up Postgres/Redis/MinIO/backend, applies migrations, seeds platform
  defaults, launches the frontend dev server in a new window.
- **`stop-dev.ps1`** — the reverse: `docker compose down` on the dev
  stack (named volumes, so data survives), kills the frontend dev
  server on port 5173, and stops the host Ollama process — but only if
  `compass-backend-prod` isn't currently running, since prod's backend
  also reaches Ollama via this same host
  (`OLLAMA_BASE_URL=http://host.docker.internal:11434`) and killing it
  out from under a live prod would break local-model AI chat there.
- **`start-prod.ps1`** / **`stop-prod.ps1`** — the same start/stop
  pair for the production stack (`docker-compose.prod.yml`:
  `compass-*-prod`, reachable via the Cloudflare Tunnel). `stop-prod.ps1`
  requires typed `yes` confirmation (or `-Force` to skip it) since it
  takes the live app offline for real users — `down` still preserves
  the named prod volumes, so real data survives the cycle. Both
  verified live end-to-end, including a real round trip against the
  public `scaledbrain.com` URL (2026-08-11).
- **`sync-dependencies.ps1`** — run whenever `pyproject.toml` or
  `package.json` gains a new dependency. Rebuilds the backend Docker
  image, syncs the native venv (for editor/ruff/mypy support), runs
  `npm install`.

**If you edit any `.ps1` script: ASCII only, no em-dashes or smart
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
- **`Request.is_disconnected()` cannot be trusted to detect a client
  abort in this dev setup.** Verified live (2026-08-04, Resume
  Intelligence's cancel-button investigation): Starlette's
  implementation is a non-blocking peek at whatever the ASGI server has
  already pushed onto the receive queue, not an active socket probe —
  and through Docker Desktop's Windows networking, that disconnect
  message reliably never arrived for either a forced `curl --max-time`
  timeout or a .NET `HttpClient` cancellation token; a long-running
  handler kept running to completion regardless of the client having
  genuinely given up minutes earlier. Don't build a "cancel a
  long-running request" feature around this pattern without testing it
  live against this actual dev stack first — it may well work fine
  behind a real reverse-proxy production deployment, but has been
  confirmed not to here.
- **Prod runs on this laptop, and closing the lid used to take the
  site down.** Verified live (2026-08-15): this machine only supports
  Modern Standby (`powercfg /a` → `Standby (S0 Low Power Idle) Network
  Connected`, no S1/S2/S3), so a lid close is a real suspend, not just
  a screen-off. Docker's WSL2 networking and the Cloudflare Tunnel's
  long-lived connection don't reliably survive that suspend/resume
  cycle — Event Viewer showed the old `Cloudflared` Windows Service
  crash-looping 1,118 times in ~2 minutes around a lid-close/reopen on
  2026-08-11. The tunnel now actually runs via a Scheduled Task
  (`CloudflaredTunnel`, `cloudflared.exe tunnel run career-compass`),
  whose only trigger was "at logon" — re-opening the lid and unlocking
  isn't a fresh logon, so if the tunnel process died during a
  sleep/resume cycle nothing brought it back until a real sign-out/
  reboot. Fixed with two changes, both confirmed to survive a real lid
  close/reopen afterward: (1) lid-close action on AC power set to "Do
  nothing" (`powercfg /setacvalueindex SCHEME_CURRENT SUB_BUTTONS
  LIDACTION 0`, only applies while plugged in — leave the laptop
  plugged in for prod to stay up) so the suspend never happens in the
  first place; (2) a 5-minute repeating watchdog trigger added to
  `CloudflaredTunnel` alongside its existing logon trigger — safe
  because the task's `MultipleInstancesPolicy` is `IgnoreNew`, so it
  only actually restarts cloudflared if the previous instance already
  died. The old, now-unused `Cloudflared` Windows Service was disabled
  (`Set-Service -Name Cloudflared -StartupType Disabled`) to stop it
  confusing future debugging — the Scheduled Task is what's real.

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
- **Left Nav vs Right Nav split**: Left Nav (`AppShell.tsx`) is a fixed
  set of top-level items regardless of route — 4 through Phase 4.5,
  5 as of the Phase 5 redesign (Resume Intelligence was added as an
  explicit, one-off carve-out to this rule, not a reversal of it; see
  that phase's status entry for why). Right Nav
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
- **Never call `.mutate()` synchronously inside a bare mount `useEffect`
  for a "fire once automatically" page** (e.g. an emailed-link landing
  page like `VerifyEmailPage.tsx`). Verified live (2026-08-10): React
  18 StrictMode's dev-only double effect invocation (mount → cleanup →
  remount, all synchronous within the same commit) tears down and
  rebuilds `useMutation`'s internal subscription *while* that first
  `mutate()` call's async request is still in flight. The request
  genuinely completes — confirmed via a real network response arriving
  with the correct body — but its `onSuccess`/`onError`/`onSettled`
  never fire and the component never re-renders, so the UI hangs on its
  loading state forever. This is dev-only (StrictMode's double-invoke
  is stripped in production builds) but this app's frontend is always
  run via `npm run dev`, so it's a real, reproducible bug in the
  environment that matters here, not a false alarm. Fix: defer the
  `mutate()` call a tick past the synchronous double-invoke window
  (`setTimeout(fn, 0)` inside the effect, cleared on cleanup) so it only
  ever fires once StrictMode's synthetic first pass has already been
  torn down and the second, stable pass's subscription is the one still
  standing — see `VerifyEmailPage.tsx`'s `useEffect` for the exact
  pattern (the `hasSubmitted` single-use-token guard now lives inside
  the deferred callback, not the effect body, so StrictMode's cancelled
  first pass never marks it submitted). Root-caused by instrumenting the
  mutation's raw promise directly (bypassing react-query) to prove the
  network layer wasn't at fault, then bisecting by toggling
  `<React.StrictMode>` off in `main.tsx` to confirm it was the actual
  variable — not by reasoning about React Query internals from source.

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
- **Phase 4** — AI Platform real wiring — done. Real Anthropic adapter
  (`app/adapters/ai_providers/anthropic_provider.py`, `anthropic` Python
  SDK) implements `LLMProviderInterface`. `LLMService`
  (`app/ai_platform/llm_service/service.py`) is the concrete
  orchestrator — resolves the active approved prompt and active model
  from two new Postgres tables (`prompt_versions`, `model_versions` —
  reference data, no RLS, same shape as `permissions`/`roles`), renders
  the template, calls the provider, and logs every invocation to a
  third new table (`ai_invocations` — tenant-owned, RLS-enforced like
  every other domain table) for the governance audit trail ADR-004
  requires. `scripts/seed_platform_defaults.py` now also seeds the
  `career_coach_chat` approved `PromptVersion` and an active
  `ModelVersion` row (defaults to `claude-sonnet-5`, overridable via
  `AI_DEFAULT_MODEL` — but per ADR-004, switching models afterward is a
  DB update to that row, not a redeploy). The footer AI Chat
  (`app/application/chat/chat_service.py`) is the first real caller: it
  renders recent conversation history plus the latest message into the
  prompt template and calls `LLMService.generate()` — a provider
  failure (no API key configured, rate limit, network error) degrades
  to an apologetic in-chat message rather than a 500, since the
  conversation itself is persisted either way. One interface change
  from the Phase 0 scaffold: `LLMRequest` gained a `model_name` field —
  the Phase 0 shape only carried opaque registry IDs
  (`prompt_version_id`/`model_version_id`), and the provider adapter
  needs the literal model string (e.g. `"claude-sonnet-5"`) to actually
  call the API; `LLMService` resolves it from the active `ModelVersion`
  before building the request. **User-facing model selection** (added
  same day, post-wiring): Settings > AI Model
  (`frontend/src/features/settings/SettingsAIModelPage.tsx`) lets each
  user pick which catalog model powers their own chats, from
  `GET /api/v1/ai-platform/models` / `PATCH /api/v1/ai-platform/model-preference`
  (`app/application/ai_platform/model_preference_service.py`). This
  drove two more schema/design changes: `ModelVersion.is_default`
  (exactly one "active" row is the platform default among possibly
  several selectable ones — `model_versions` is now seeded with 3:
  Opus 5 / Sonnet 5 (default) / Haiku 4.5) and `User.preferred_model_version_id`
  (nullable FK, `null` = "use the platform default"). `LLMService`'s
  constructor changed from a single `provider` to
  `providers: Mapping[str, LLMProviderInterface]` keyed by
  `ModelVersion.provider` — resolving a model whose provider has no
  registered adapter raises `ProviderNotConfiguredError` rather than
  silently using the wrong provider. **Second provider wired same day:
  Ollama** (`app/adapters/ai_providers/ollama_provider.py`), for local,
  free inference against models already installed on the user's
  machine — `qwen2.5:7b` and `qwen2.5:3b` are seeded into
  `model_versions` (`cost_per_1k_tokens=0`, genuinely free, unlike the
  Anthropic rows' illustrative figures). No official Ollama SDK exists,
  so the adapter is a plain `httpx` POST to `/api/chat` (same pattern as
  `app/adapters/quotes/zen_quotes_provider.py`), mapping Ollama's
  `prompt_eval_count`/`eval_count`/`num_predict` to the
  input/output-tokens/max-tokens shape every other provider uses. The
  shared `AIProviderError` moved out of `anthropic_provider.py` into
  its own `app/adapters/ai_providers/errors.py` so the two adapters
  don't depend on each other. **Docker networking gotcha**: Ollama runs
  on the host, not in `docker-compose.yml`, so the backend container
  reaches it via `OLLAMA_BASE_URL=http://host.docker.internal:11434`
  (Docker Desktop's host-loopback DNS name) — plain `localhost` from
  inside the container would resolve to the container itself, the same
  class of bug as `DATABASE_URL`/`OBJECT_STORAGE_ENDPOINT` above.
  Verified live: real chat replies from both `qwen2.5:3b` and
  `qwen2.5:7b` through the full pipeline (model-preference switch,
  multi-turn conversation history reaching the local model, and a real
  `ai_invocations` row with actual token counts/latency) — not just
  unit-tested with fakes.
- **AI Career Coach page** (post-Phase 4, `/coach`) — done. A dedicated
  full-page view onto the exact same conversation the footer's
  persistent chat bar sends into (same `chat-store`/conversation_id,
  same `POST /api/v1/chat/messages`) — not a second conversation or
  endpoint. The send logic was pulled out of `AppFooter.tsx` into
  `frontend/src/hooks/useChatComposer.ts` so both the footer input and
  the Coach page's suggested-prompt chips
  (`frontend/src/features/coach/suggested-prompts.ts`) drive the same
  flow. Suggested prompts are built from the person's real profile data
  (target roles, gap-analysis missing skills) with the actual role/skill
  names woven directly into the prompt text — the chat backend only ever
  receives conversation history plus the literal message, so this is
  the only grounding mechanism, not a backend prompt change.
  `AppShell.tsx` suppresses the generic compact `ChatThread` specifically
  on `/coach` (CoachPage renders its own richer, labeled thread) to avoid
  rendering the same messages twice.
- **Phone login (Firebase Phone Auth)** — done, verified live end-to-end
  with a real Firebase project (`career-compass-ai-c749f`) and a real
  phone/test number, repeated successfully multiple times in a row.
  Deliberately **not** a second `IdentityProviderInterface`
  implementation — Firebase only proves phone ownership (it has no
  notion of tenants/users); matching that verified number to a Career
  Compass user and minting our own JWT still goes through
  `InternalJWTProvider.authenticate_with_phone`
  (`app/adapters/identity_providers/internal_jwt.py`), the phone-login
  counterpart to `authenticate_with_credentials`. The frontend talks to
  Firebase directly (`signInWithPhoneNumber`/`confirmationResult.confirm`,
  see `frontend/src/lib/firebase.ts` +
  `frontend/src/features/auth/PhoneLoginForm.tsx`) and only ever hands
  the backend the resulting ID token
  (`POST /api/v1/identity/login/phone`) — the OTP code itself never
  reaches this backend, and neither does an SMS provider credential of
  our own to manage; Firebase owns sending the code, reCAPTCHA-backed
  abuse protection, and code expiry/retry limits entirely. New
  `User.phone_number_e164` column (unique per tenant, nullable) is
  computed server-side via `phonenumbers` whenever
  `phone_number`+`country` are saved together
  (`UpdateUserProfileService`) — this is the only field phone login
  looks up against, separate from the free-text `phone_number` display
  field, since Firebase's verified claim is always E.164 and the
  free-text field is deliberately unvalidated (see its own comment).
  Both `get_authenticate_user_service` and `AuthenticateUserService`
  treat a missing/misconfigured Firebase adapter as "phone login not
  configured" (`PHONE_LOGIN_NOT_CONFIGURED`) rather than raising — email/
  password login is completely unaffected either way regardless of
  Firebase's setup state, verified live.

  Real setup on console.firebase.google.com, not just code: Web app
  config (apiKey/appId → `frontend/.env.local`'s `VITE_FIREBASE_*`) and
  a service-account key (Project Settings → Service Accounts → Generate
  new private key → `backend/secrets/firebase-service-account.json`,
  gitignored, bind-mounted read-only into the backend container —
  `FIREBASE_SERVICE_ACCOUNT_FILE` in `.env`). Firebase's own **Phone
  numbers for testing** feature (Authentication → Sign-in method →
  Phone → "Phone numbers for testing") is genuinely useful for local dev
  going forward — a fixed number+code pair (e.g. `+16505553434` /
  `123456`) skips real SMS and billing, so it's usable in a browser
  without most of the gotchas below. `phase4@test.com` already has
  `+1 650-555-3434` saved as its phone number for exactly this.
  **Correction, 2026-08-11: it does not skip reCAPTCHA** — confirmed
  live that a fresh test number still hit a genuine visible reCAPTCHA
  challenge when driven by an automated Playwright session (see the
  "Phone login for Personal accounts" status entry further down).
  reCAPTCHA verification is a client-side precondition that runs before
  Firebase's backend ever checks whether the number is a registered
  test number — the test-number feature only short-circuits the real
  SMS send/billing *after* a valid reCAPTCHA response already exists.
  An origin with a degraded reCAPTCHA risk score (heavy same-day
  automated testing, in particular) gets challenged regardless of which
  number is used; a real human on an ordinary browsing pattern
  generally isn't affected.

  **Five real gotchas hit getting this working live, all fixed** (none
  of these show up in code review — only actually running the flow
  surfaced them):
  1. Firebase's `getAuth()` throws synchronously (`auth/invalid-api-key`)
     for an empty/invalid config, and since ES module top-level code
     always runs on import regardless of which LoginPage tab is active,
     doing this eagerly in `lib/firebase.ts` crashed the *entire* app —
     including the unrelated email/password path — the moment
     `PhoneLoginForm` was merely imported, before Firebase credentials
     were ever configured. Fixed by making `getFirebaseAuth()` a lazy,
     memoized function called only from inside `PhoneLoginForm`'s submit
     handlers, with a `FirebaseNotConfiguredError` surfaced as a plain
     inline message instead of a blank white screen.
  2. **SMS region policy** (Authentication → Settings → SMS region
     policy) blocks phone verification by country until explicitly
     allowed — surfaced as `auth/operation-not-allowed`, unrelated to
     billing or code.
  3. Phone Auth requires the **Blaze** billing plan, not the free Spark
     plan — `auth/billing-not-enabled` even with zero actual usage. A
     freshly-added billing account can also sit in a manual-review hold
     specifically for SMS-capable APIs.
  4. **Never recreate the `RecaptchaVerifier` on a failed retry** —
     `PhoneLoginForm.tsx` originally called `.clear()` and rebuilt it
     after every error, which threw "reCAPTCHA has already been
     rendered in this element" on the next attempt: the underlying
     `grecaptcha` widget is tied to its container DOM node and can't be
     re-rendered into that same node, even after `.clear()`. Fixed by
     creating the verifier once (lazily, on first use) and reusing it
     for the component's whole lifetime — invisible verifiers are
     designed to be reused across multiple `signInWithPhoneNumber` calls
     anyway, so there was never a need to recreate one per attempt.
  5. **Docker Desktop/WSL2 clock drift** (~1 second, worse right after
     the host wakes from sleep) intermittently failed real token
     verification with `InvalidIdTokenError: Token used too early` —
     `verify_id_token`'s default zero clock-skew tolerance rejected a
     token Firebase had only just issued. Fixed with
     `clock_skew_seconds=10`. Also dropped `check_revoked=True` from the
     same call — it added an extra round-trip that failed intermittently
     for a just-issued token (likely Firebase-side propagation lag on
     `tokensValidAfterTime`), and this app never calls Firebase's
     `revoke_refresh_tokens()` itself, so there's no legitimate
     "revoked elsewhere" case to guard against here anyway. Both changes
     are in `app/adapters/identity_providers/firebase_phone.py`.
- **Phase 4.5.1 — CIKG Core Graph Foundation** (2026-07-29, `app/domain/career_intelligence/`)
  — done, verified live. The narrowest slice of the 17-doc CIKG
  architecture (see project memory's `cikg_architecture` entry for the
  full approval history): `Skill`, `SkillCategory`, `Competency`,
  `CikgRole` (a job-role node — named `CikgRole`/`cikg_roles`, not
  `Role`/`roles`, since that name is already the RBAC role table) +
  the `member_of` (`skill_competency_memberships`), `requires`
  (`role_required_skills`), and `related_to` (`related_skills`) edges,
  the category hierarchy (`category_parents`,
  `skill_category_memberships`), and `skill_aliases` (ADR-006 §3's
  free-text-to-canonical soft link). All global reference data — no
  `tenant_id`, no RLS, same shape as `prompt_versions`/`model_versions`.
  Governance is deliberately minimal per the roadmap: `content_status`
  CHECK-constrained to `('draft', 'approved')` only, single-approver
  (no `in_review`), enforced by five new `cikg.content.*` permissions
  (`create`/`review`/`approve`/`deprecate`/`admin`) and a new
  `cikg_curator` role granted create+review+approve —
  `ContentGovernanceService` is the one-class-per-verb create-draft/
  approve workflow every node and edge type shares.
  **Scope decision made at the start of this build**: the roadmap
  (`cikg-mvp-roadmap.md`) defers `prerequisite_of`/`specializes`/
  `synonym_of` to MVP 2B (they need the cycle-detection-at-approval
  workflow that ships then), but the seed-data spec
  (`cikg-mvp1-seed-data.md`) actually uses `prerequisite_of`/
  `specializes` throughout its worked examples — a real inconsistency
  between two "approved" docs. Resolved, per explicit user direction,
  by following the roadmap strictly: every `prerequisite_of`/
  `specializes` edge in the source spec was dropped from the seed
  script (`scripts/seed_cikg_mvp1.py`), seeding only `related_to`.
  Healthcare's seed content has zero `related_to` edges of its own
  (all its ontology edges in the spec are `prerequisite_of`/
  `specializes`), so it only meets MVP 1's "at least one ontology edge
  per domain" exit criterion via the spec's own cross-domain edge (Risk
  Analysis <-> Clinical Risk Assessment) — verified live, not assumed.
  **`SkillCategory.name` is deliberately not globally unique** (caught
  during seeding, not design review) — the seed spec itself reuses
  "Regulatory" as a category name under both Healthcare's Health
  Information & Compliance and Finance's Risk & Compliance; disambiguation
  is by hierarchy position (`category_parents`), not name, so
  `SkillCategoryRepository` has no `get_by_name`.
  **A real async/ORM bug caught by testing the API live, not by
  review**: every `approve()` repository method originally did
  `session.flush()` then mapped the model straight to a domain
  dataclass — `updated_at`'s `onupdate=func.now()` marks that column
  expired after an UPDATE, and accessing it outside an awaited ORM call
  raised `MissingGreenlet`. `create()` methods never hit this (Postgres
  RETURNING populates server-generated columns in the same round trip
  on INSERT), only `approve()`'s UPDATE path did. Fixed by adding
  `await session.refresh(model)` after `flush()`, matching the same
  pattern career_profile.py's `update()` methods already established —
  caught by actually calling the API end-to-end with a real JWT and a
  temporarily-granted `cikg_curator` role (reverted immediately after),
  not by reasoning about the code.
  Seed content: 97 skills / 49 categories / 13 roles / 17 `related_to`
  edges / 7 `skill_alias` examples across the 5 seed domains
  (`scripts/seed_cikg_mvp1.py`, idempotent — verified via a clean
  re-run producing zero new rows). MVP 1's exit criterion (a `Skill` in
  every domain with a populated hierarchy path, at least one ontology
  edge, and at least one `skill_alias` resolving a real test user's
  existing free-text `core_competencies` entry) was verified against
  the real Postgres database and through `SkillAliasResolutionService`
  called directly against real data — `name-qa@example.com`'s existing
  `"Python"` competency resolves to canonical `Skill` "Python
  Programming". A minimal read/write REST API exists at
  `/api/v1/career-intelligence/*` (23 endpoints) — reads need only an
  authenticated identity, writes are gated by `cikg.content.create`/
  `cikg.content.approve`, verified live including a correct 403 for a
  user without those permissions.
- **CIKG MVP 2A — Search Foundation** (2026-07-29) — done, verified
  live. Hybrid search over the MVP 1 graph per
  `cikg-semantic-search.md`: `content_embeddings` (pgvector
  `vector(768)` + HNSW index, polymorphic across
  `Skill`/`CikgRole`/`Competency` — the only CIKG node types with real
  free text; `SkillCategory` is excluded, already browsable via
  `GET /categories`) and `embedding_models` (mirrors `model_versions`'
  reference-data shape), plus a generated `search_vector` `tsvector` +
  GIN index directly on `skills`/`cikg_roles`/`competencies` — the
  first tsvector/GIN usage in this codebase. Embedding provider is
  Ollama-only (`app/adapters/ai_providers/ollama_embedding_provider.py`,
  mirroring `ollama_provider.py`'s exact shape;
  `app/ai_platform/embeddings/` was an empty Phase-0-reserved slot,
  now filled) — `nomic-embed-text` (768-dim), no paid provider wired,
  per the roadmap's explicit MVP 2A scope. `SearchService`
  (`app/application/career_intelligence/search_service.py`) implements
  cikg-semantic-search.md's exact worked-example algorithm: resolve the
  query to a canonical `Skill` (reuses `SkillAliasResolutionService`),
  traverse its approved `related_to` edges (graph — ranks highest,
  score 2.0 flat, always above the ~0-1 range of fulltext/vector
  scores), then full-text (`ts_rank`) and vector (pgvector cosine KNN)
  as supplementary signals, `category_id`/`role_id` as a hard
  post-filter (skills only), all weighted by a live-computed
  `knowledge_quality_score` (deliberately simple per MVP 2A scope —
  `relationship_count` only; source-authorship/usage/freshness/conflict
  factors are explicitly deferred, per cikg-semantic-search.md, to when
  their inputs actually exist). **`knowledge_quality_score` is computed
  live per query, not via a background job** — a deliberate MVP 2A
  scope decision (confirmed with the user before building): this
  codebase has no job scheduler, and at ~110 embeddable nodes a live
  computation is cheap; revisit only if content volume or query latency
  later demands a real batch job. `EmbeddingIndexingService`
  (`scripts/embed_cikg_content.py`) is idempotent — re-embeds only
  content whose text changed since its last embed (sha256 hash
  comparison), verified live via a clean re-run producing zero new
  embeddings. **Vector similarity's actual value verified live**, not
  assumed: `q=handling customer objections` (zero keyword overlap with
  any skill) correctly top-ranks "Objection Handling" purely via
  `matched_via: ["vector"]`; `q=Data Analysis` top-ranks its
  `related_to` neighbors ("Python Programming",
  "SQL & Relational Database Querying") via `matched_via: ["graph"]`,
  above the plain full-text self-match, over real Ollama-generated
  embeddings (not mocked). One real bug caught building this, not by
  review: `SkillAliasResolutionService.resolve()` only ever checked the
  `skill_alias` table, never a skill's own canonical name — so a query
  exactly matching a real `Skill.name` (not registered as its own
  alias) silently failed to resolve and skipped the graph-traversal
  step entirely. Fixed (exact-name match now tried first), regression
  test added. New endpoint: `GET /api/v1/career-intelligence/search`
  (any authenticated user, read-only) — 24 career-intelligence
  endpoints total now.
- **CIKG MVP 2B — Governance Expansion** (2026-07-29) — done, verified
  live. **The write path was fully rewritten, not extended**: per the
  user's explicit choice (`cikg-api-boundaries.md`'s "no CIKG resource
  is ever writable directly — every change is `POST /revisions`"),
  MVP 1's `ContentGovernanceService` and its ~19 direct
  `create_draft_*`/`.../approve` endpoints are gone entirely, replaced
  by `ContentRevisionService` (`app/application/career_intelligence/content_revision_service.py`)
  and 7 generic endpoints under `/api/v1/career-intelligence/revisions`
  (propose/submit/approve/reject/mark-rejected/list/batch-approve) — 16
  career-intelligence endpoints total now (read endpoints unchanged).
  New tables: `content_revisions` (the `draft`→`in_review`→`approved`/
  `rejected` staging area — nothing touches a live row until an
  `in_review` revision is approved) and `content_history` (append-only
  prior-state snapshots, written automatically when an approved
  revision edits an already-live entity). **Consequence**:
  `content_status` on every governed node/edge table was narrowed from
  `('draft', 'approved')` to `('approved', 'deprecated')` — `draft`/
  `in_review` now live exclusively on `content_revisions.status`,
  verified via a defensive zero-draft-rows check built into the
  migration itself before narrowing the constraint. Three new
  Skill↔Skill edge types unlocked by the DAG cycle-detection this slice
  delivers: `prerequisite_of`/`specializes` (directed,
  cycle-checked at approval via
  `app/domain/career_intelligence/graph_validation.py`'s plain BFS —
  the first graph-traversal logic in this codebase, no recursive SQL
  CTE) and `synonym_of` (symmetric, same canonical-ordering/self-loop
  rule as `related_to`, no cycle check). The 13
  `prerequisite_of`/3 `specializes` edges MVP 1 deliberately dropped
  (see that phase's status entry) were re-added via
  `scripts/reseed_cikg_prerequisite_specializes.py`, transcribed
  directly from `cikg-mvp1-seed-data.md`. **The literal MVP 2B exit
  criterion verified live**: proposing the reverse of an
  already-approved `prerequisite_of` edge (an AI-suggested edge,
  `confidence=0.8`) is correctly blocked at `approve()` with
  `EDGE_APPROVAL_WOULD_CREATE_CYCLE`, and the revision stays `in_review`
  untouched rather than being silently dropped — real HTTP round trip,
  not a unit test with fakes. Batch approval
  (`import_batch_id`) and edit-with-history (proposing a new
  description for an already-approved `Skill`, confirming
  `content_history` captured the *prior* description) were also
  verified live. **A real bug caught by that live batch-approve test,
  not by review**: `search_vector` (MVP 2A's generated tsvector column)
  had no `Computed()` marker on the ORM model, so any fresh INSERT
  through the ORM (any brand-new node approved via a revision) failed
  with `psycopg.errors.GeneratedAlways` — MVP 2A's own seed data never
  hit this because it predated the column's existence, so no new
  ORM-level INSERT had exercised this path until MVP 2B's
  revision-approval flow did. Fixed by adding `Computed(...)` (matching
  the migration's actual generation expression) to all three affected
  models. **Known, documented limitation**: `batch_approve` isolates
  `ValidationError`-style failures (the cycle check, which runs in
  Python before any DB write) so one blocked edge doesn't block the
  rest of a batch, but a genuine DB-level constraint violation would
  abort the whole batch's shared transaction — accepted as out of scope
  for this slice since the literal exit criterion never exercises that
  path (see `content_revision_service.py`'s docstring). Full
  `in_review`/multi-reviewer workflow beyond single-approver,
  automatic conflict *detection* (vs. the `reject`/`mark_rejected`
  primitives this slice exposes for a human to resolve one), and a real
  AI-suggestion *generation* pipeline remain explicitly deferred past
  MVP 2B, per the roadmap's own "Also Deferred Past MVP" list.
- **Phase 5 — Resume Intelligence** (2026-08-04) — done, verified live.
  New `app/domain/resume_intelligence/` domain: upload a PDF/DOCX resume
  → parse it → use an LLM to extract structured data → the user reviews
  and accepts/rejects individual items before anything is written into
  the *existing* Career Profile (Experience/Education/Certifications/
  headline/summary/core_competencies) — deliberately no parallel resume
  data model of its own. Parsing is synchronous within the upload
  request (no job queue in this codebase, same call already made for
  CIKG's `knowledge_quality_score`): `pdfplumber`/`python-docx` extract
  raw text (`app/adapters/parsing/resume_text_extractor.py`, run via
  `asyncio.to_thread` — CPU-bound sync libraries, same pattern as boto3
  calls elsewhere), then `LLMService.generate(use_case="resume_extraction")`
  (reusing Phase 4's AI Platform as-is — a new seeded `PromptVersion`,
  no other AI Platform changes) returns JSON that's normalized (missing
  fields defaulted, individual malformed list items dropped rather than
  failing the whole resume) and stored on a new `resumes` table
  (tenant-owned, RLS enabled+forced, single `ResumeRepository` — a
  resume row is write-once, no `update()`/`move()`). A failure at any
  step (text extraction, the LLM call, malformed JSON back) is caught
  and persisted as `status="failed"` with an `error_message` rather than
  raising — verified live both ways: a missing `ANTHROPIC_API_KEY`
  correctly degrades to a `failed` row, and switching the test user's
  model preference to a local Ollama model (`qwen2.5:7b`, already seeded
  from Phase 4) correctly produces a real `parsed` extraction end to end.
  **Real security decision made mid-build, not assumed**: the existing
  `S3ObjectStorageRepository`/`ObjectStorageRepository` (profile photos)
  makes its bucket bucket-wide public-read by design — wrong for
  resumes, which carry real PII. Extended the same adapter class with a
  second, private bucket (`OBJECT_STORAGE_RESUMES_BUCKET`) and three new
  methods (`upload_private`/`get_presigned_url`/`delete_private`,
  ported behind a new `PrivateObjectStorageRepository` Protocol in
  `app/domain/resume_intelligence/storage.py`) rather than reusing the
  public path as-is — verified live: an anonymous `curl` against a
  resume's object URL gets `403`, against the same-shaped photo URL
  gets `404` (reachable, just not found) — confirming the resumes
  bucket is genuinely private and the photos bucket genuinely isn't.
  `ResumeMergeService` (`app/application/resume_intelligence/`) takes
  the user's per-item accept/reject decisions and calls the *existing*
  `ExperienceService.add()`/`EducationService.add()`/
  `CertificationService.add()`/`CareerProfileService.update()` exactly
  as every other caller does — no duplicated profile-mutation logic.
  Skill merging dedups case-insensitively against current
  `core_competencies`, same rule `TargetRole.add_required_skill` already
  established. Verified live end-to-end via real HTTP calls with real
  JWTs across two tenants (not just unit tests): upload → real-Ollama
  extraction → `GET /latest` correctly 404s for a different tenant
  (cross-tenant isolation through the real RLS-backed path, not a raw
  superuser SQL check, which would have bypassed RLS meaninglessly) →
  `POST /merge` with a subset of indices/skills → confirmed via
  `GET /career-profile/*` that only the accepted items were written.
  18 new unit tests (fake in-memory repositories, real
  `ExperienceService`/`EducationService`/`CertificationService`/
  `CareerProfileService` wired against them — the same DI shape
  `app/api/dependencies.py` uses against real repositories) cover both
  services including the failure/degradation paths. Frontend: new
  `/profile/resume` page (`frontend/src/features/resume-intelligence/`,
  unlisted route — Left Nav stays the fixed 4 items — reached via an
  "Import from Resume" button on the Career Profile page), upload UI
  mirroring `ProfileHeader.tsx`'s hidden-file-input pattern, and a
  genuinely new review-screen UI (no accept/reject-list precedent
  existed anywhere in this app before — Gap Analysis is read-only, My
  Skills is single-select-and-add) built from existing primitives
  (`Card`, `Badge`, `ConfirmDialog`). Selection state for the review
  checkboxes is initialized fresh per resume via a `key={resume.id}`
  remount rather than a `useEffect` re-sync — deliberately sidesteps the
  reactive-re-sync bug class CLAUDE.md already documents elsewhere,
  since a `key` change unmounts/remounts instead of clobbering
  in-progress (de)selections on an unrelated background refetch. After
  a successful merge the resume is also discarded (`DELETE`) so
  revisiting `/profile/resume` doesn't re-offer already-merged items for
  a second, duplicating merge. Verified live in a real headless browser
  (Playwright, driven directly — no `chromium-cli` available on this
  Windows host): logged in, navigated via the app's own client-side
  router (a hard `page.goto` to an internal route loses the session,
  since the access token is deliberately kept in-memory only — see
  `auth-store.ts` — not a bug, just a test-script gotcha worth noting),
  uploaded a real PDF, watched the review screen populate from a real
  Ollama extraction, deselected one experience entry, merged, and
  confirmed on the real (expanded) Career Profile page that the
  accepted entry appears and the deselected one does not.
- **Phase 5 redesign — Resume Intelligence becomes a history, not a
  slot** (2026-08-04, same day, prompted directly by the user after
  live-testing Phase 5 with their own real resume) — done, verified
  live. Two of the day's own design choices above were reversed by
  explicit user direction once the single-resume shape proved wrong in
  practice: **(1) Resume Intelligence is now a 5th permanent Left Nav
  item** (`/resumes`, `nav-items.ts`) — a deliberate, explicit
  departure from the "Left Nav is always the same 4 items" convention
  documented under "Frontend conventions" above, which still holds for
  every *other* nav decision, this is a one-off carve-out, not a
  reversal of the rule. The old unlisted `/profile/resume` route and
  its "Import from Resume" button on the Career Profile page are gone.
  **(2) Resumes are now real history, not a superseded single row**: a
  person keeps multiple resume versions, optionally each tagged to a
  different `TargetRole` (new nullable `Resume.target_role_id` FK,
  migration `b7e4c8a91f3d`). `ResumeRepository` changed from
  `get_latest_for_user`/`soft_delete_all_for_user` to
  `list_for_user`/`get_by_id` — an upload no longer discards any prior
  resume, and a merge no longer auto-discards the just-merged resume
  either (both were deliberate Phase-5-day behaviors that only made
  sense under the single-slot model). **Delete removes only the resume
  record** — already-merged Career Profile data is never touched or
  rolled back by deleting the resume that produced it, confirmed
  explicitly with the user rather than assumed. New `GET
  /resume-intelligence` (list, lightweight `ResumeSummary` shape) and
  `GET /resume-intelligence/{id}` (single, full detail) replace the old
  `GET /resume-intelligence/latest`. `ResumeIntelligencePage.tsx`
  replaced `ResumeImportPage.tsx`: a history list (target-role tag per
  row where linked) plus an upload card with a target-role `<Select>`,
  and the same review/merge UI as before now reached per-resume rather
  than for a single implicit latest one.
  This redesign session was also the second live-debugging pass on the
  Phase 5 extraction pipeline itself, using the user's own real
  resume — a real DOCX bug (`document.paragraphs` never sees table
  content at all; `_extract_docx` rewritten to walk
  `document.element.body.iterchildren()` in document order via
  `_iter_block_items()`, matching `w:p`/`w:tbl` tags) turned out to be
  the likely root cause of several earlier "section went missing"
  reports, since every prior real-resume test happened to be a Word
  file. A second, distinct root cause for missing/incomplete sections
  under token pressure: the LLM was writing full-paragraph
  `description` fields and running out of its response token budget
  before reaching every section — reordering the JSON schema key order
  only shifted *which* section got sacrificed, not a real fix; the
  actual fix was an explicit prompt instruction to keep every
  description to one concise sentence, verified live to produce
  complete extractions across all categories. Also fixed live this
  session: an experience item with an unparseable/missing start date
  no longer aborts the *entire* merge (skips just that item, reports it
  in `skipped_experience_titles`); Education vs. Certification
  miscategorization (employers and professional-membership bodies were
  landing in Education) fixed via explicit prompt field guidance;
  "Present"/"Current" roles were incorrectly nulling `start_date` along
  with `end_date`; Executive Summary was being nulled whenever its
  wording overlapped the headline, since no prompt guidance
  distinguished the two fields at all. The prompt template
  (`RESUME_EXTRACTION_PROMPT_TEMPLATE` in `seed_platform_defaults.py`)
  went through 9 live-seeded versions across the full Phase 5 + redesign
  session addressing these findings one at a time, each verified
  against the user's actual resume, not synthetic test data.
- **Career Profile bulk clear + resume upload cancel** (2026-08-04,
  post-Phase-5-redesign) — done, verified live. Two independent
  additions requested together: (1) a page-level "Clear Career Profile"
  button on `CareerProfilePage.tsx` that wipes the *entire* profile —
  photo, headline, summary, core competencies, and every entry across
  all 7 list-domains (Experience/Education/Certifications/Career
  Highlights/Key Achievements/Career Goals/Peer Endorsements) — plus a
  "Clear" button on each of the 8 `SECTION_DEFS` section cards that
  clears only that section, both gated behind `ConfirmDialog` per the
  standing confirm-before-delete convention; (2) a Cancel button on the
  Resume Intelligence upload flow. **Backend**: every domain repository
  gained a bulk `soft_delete_all_for_profile`/`soft_delete_all_for_user`
  (single `UPDATE ... WHERE ... deleted_at IS NULL` statement, not a
  per-item loop) and its application service gained a matching
  `clear_all()`; `CareerProfileService` gained `delete_photo()` (best-
  effort — the storage key is reconstructed from `photo_url`'s file
  extension since the key itself was never persisted separately, and a
  storage-side failure is caught and swallowed rather than blocking the
  DB-side clear, since the DB field is the source of truth for "does
  this profile have a photo," not the object's actual presence in the
  bucket). A new orchestrating `ClearCareerProfileService`
  (`app/application/career_profile/clear_profile_service.py`) fans out
  to all 7 domain services plus `CareerProfileService`, mirroring
  `ResumeMergeService`'s own reuse-existing-services pattern just in the
  write-nothing-but-delete direction. New endpoints all follow the
  existing per-item `DELETE .../{id}` shape but with **no id** —
  `DELETE /career-profile` (whole profile), `DELETE
  /career-profile/photo`, and `DELETE /career-profile/{experiences,
  educations, certifications, highlights, achievements, endorsements}`
  plus `DELETE /career-goals` (its own prefix, matching that domain's
  existing routing). Core Competencies has no dedicated clear endpoint —
  its frontend "Clear" button reuses the existing `PATCH /career-profile`
  with `core_competencies: []`, since that field already lives on
  `CareerProfileService.update()`. Verified live via direct HTTP calls
  (not just unit tests): whole-profile clear correctly reset every
  field/domain and left a different user's profile untouched; a real
  photo was uploaded then deleted, confirmed via an anonymous fetch
  against the object URL going from `200` to `404` — the S3 object is
  genuinely gone, not just unlinked from the profile row. New unit
  tests (`CareerProfileService.delete_photo`, including a simulated
  storage failure) and integration tests (`TestClearSection`,
  `TestClearWholeProfile` in `test_career_profile_flow.py`, real
  Postgres, cross-user isolation checked for both) — 243 backend tests
  passing. **Frontend**: `ConfirmDialog` gained optional
  `confirmLabel`/`confirmPendingLabel` props (default unchanged:
  "Delete"/"Deleting...") so the same component reads "Clear"/
  "Clearing..." for these actions without a second dialog component.
  **Resume upload cancel**: `apiClient.uploadFile` and `useUploadResume`
  both gained a threaded-through optional `AbortSignal`; `UploadCard`
  creates a fresh `AbortController` per upload attempt (stored in a
  ref) and shows a Cancel button only while `isPending`, clicking it
  aborts the in-flight `fetch`. **Real architectural limit, documented
  not hidden**: since resume extraction runs synchronously inside the
  backend request (no job queue exists in this codebase — same
  constraint noted throughout Phase 5), cancelling only abandons this
  browser tab's wait for the response; the server keeps running the
  extraction to completion and still writes a `resumes` row when it
  finishes, which simply appears in history like any other upload
  rather than opening automatically — there is no server-side
  cancellation path to hook into without adding a job queue, which is
  out of scope for this change. Verified live in a real headless
  browser (Playwright): added a competency, cleared just that section,
  confirmed it disappeared without touching an unrelated section;
  opened (and correctly canceled, to avoid destroying the live test
  tenant's data further) the whole-profile confirm dialog; and, using
  Playwright route interception to artificially delay the upload
  response (the dummy file otherwise failed extraction too fast to
  leave a real cancel window), confirmed the Cancel button appears
  during upload, clicking it shows "Upload canceled." instead of a
  scary error, and the upload control re-enables afterward — zero
  console errors throughout.
- **Same-day follow-up, from real user testing of the above** (2026-08-04)
  — done, verified live. Three issues reported after using the new
  clear/cancel features for real: (1) adding a new item to a collapsed
  section left it collapsed — the Add button lives in the section
  header and is reachable even while collapsed, but nothing then opened
  the section to show what was just added. Fixed in all 7 dialog-based
  sections (Core Competencies isn't affected — its add input only
  renders once already expanded) by expanding on a successful **add**
  specifically, not an edit, since `editingId` already distinguishes
  the two in every section's shared submit handler. (2) One real
  upload produced **three** `failed` entries in Resume History instead
  of one, and entries showed only a date, no time, making the
  duplicates impossible to tell apart. Root-caused live, not assumed:
  the just-shipped Cancel button aborts the *browser's* wait, but
  extraction keeps running server-side regardless (no job queue exists
  to actually stop it) — the UI going back to "ready" immediately after
  Cancel invited exactly this: cancel, retry, cancel, retry, with 2-3
  independent ~10-minute Ollama calls silently in flight at once, each
  eventually writing its own `failed` row. **First attempted a real
  fix**: `upload_resume` (`app/api/v1/resume_intelligence/router.py`)
  raced the extraction against `Request.is_disconnected()` polling (the
  documented Starlette pattern — task-cancel on client disconnect, so
  cancellation unwinds the coroutine before it ever reaches
  `resumes.create()`, no row written at all for a genuinely cancelled
  attempt). **Verified live that this does NOT work in this specific
  dev setup**: two separate real disconnect tests (a forced curl
  timeout, and a .NET `HttpClient` cancellation token) both still
  produced a `resumes` row once Ollama eventually replied minutes
  later — `Request.is_disconnected()` only reports a disconnect that
  the ASGI server already pushed onto the receive queue
  (`starlette/requests.py`'s implementation is a non-blocking peek, not
  an active probe), and that message reliably never arrived through
  Docker Desktop's Windows networking for these test clients. The
  router code is kept anyway (spec-correct, harmless, may well work
  behind a normal reverse proxy in a real deployment) but is **not**
  relied on to solve the dev-environment bug. The actual fix that
  matters here is honest UI messaging: `UploadCard`'s post-cancel state
  (`ResumeIntelligencePage.tsx`) no longer implies a clean stop —  a
  persistent (not auto-dismissing) note explains the previous attempt
  may still finish in the background and appear later, so a user
  cancelling and retrying does so with accurate expectations instead of
  the UI's own "ready to go" appearance being what caused the
  duplicate-attempt pattern in the first place. (3) Resume History now
  shows date **and time** (`formatDisplayDateTime`, new in
  `lib/date-format.ts`, local timezone) instead of date-only
  (`formatDisplayDate`) — directly requested, and specifically useful
  for telling near-simultaneous duplicate entries apart, which is
  exactly the scenario issue (2) produces when it does still happen.
  243 backend tests still passing; all three fixes verified live
  (Playwright for the auto-expand fix — confirmed a collapsed section
  reliably opens and shows the new item after Add; direct HTTP/curl and
  PowerShell `HttpClient` for the disconnect-race investigation itself).
- **Email verification + real "delete my account"** (2026-08-10) — done,
  verified live in dev; prod rebuild/redeploy not yet done. Signup is
  now two-phase for both Personal and Enterprise: nothing is written to
  `tenants`/`organizations`/`users` until an emailed link is clicked.
  New RLS-exempt `pending_signups` table (same reasoning as
  `password_reset_tokens` — must be resolvable before any tenant
  exists) holds a hashed password + opaque hashed token (reusing the
  password-reset feature's "raw token emailed, only its sha256 hash
  stored" pattern). `RequestPersonalSignupService`/
  `RequestOrganizationSignupService` (`app/application/identity/`)
  validate and email the link; `VerifySignupService` looks it up,
  creates the real account via a new `RegisterTenantService.execute_with_hashed_password()`
  (the existing `execute()` is now a thin wrapper around it, so the
  already-hashed pending-signup password isn't hashed twice), and
  auto-logs the person in via a newly-extracted
  `InternalJWTProvider.claims_for_user()` (previously duplicated inline
  in both the credentials and phone login paths). `/tenants` itself is
  deliberately untouched — it stays the low-level immediate-creation
  primitive ~30 existing integration tests already use for setup.
  Account deletion (`DELETE /api/v1/identity/me`) is immediate and
  real — no LinkedIn-style grace period, an explicit choice made
  because this codebase has no background job scheduler to support a
  delayed purge. Deletes the whole tenant (every tenant today has
  exactly one user, no invite feature yet) via explicit ORM-level
  deletes in dependency order in `SqlAlchemyAccountDeletionRepository`
  (`app/adapters/db/account_deletion.py`), not `ON DELETE CASCADE` —
  confirmed live via `information_schema` that no FK in this schema has
  cascade behavior, and adding it broadly was judged riskier than one
  explicit, order-verified deletion service for this codebase's
  maturity; a forgotten future tenant-owned table fails loudly (FK
  violation) rather than silently orphaning data. This also required
  narrowing the `audit_events_immutable` trigger from
  `BEFORE UPDATE OR DELETE` to `BEFORE UPDATE` only — every tenant has
  audit rows from its own creation, so deletion was flatly impossible
  under the original trigger; history still can't be *rewritten*, only
  a deleted tenant's own trail can now be removed along with the rest
  of its data. **One real bug found and fixed live, not by review**:
  `VerifyEmailPage.tsx` initially hung forever on "Verifying..." for a
  genuinely-failing verification (confirmed the backend correctly
  returned 401 in ~25ms) — see the new Frontend-conventions entry above
  ("Never call `.mutate()` synchronously inside a bare mount
  `useEffect`...") for the full root-cause and fix; StrictMode's
  dev-only double effect invocation was silently orphaning the
  mutation's subscription before its async response arrived. A second,
  minor issue from the same verification pass: `ResendEmailProvider`
  was relaying Resend's raw HTTP error text (e.g. sandbox-domain
  rejection wording) straight into the signup form's UI — fixed by
  logging the raw detail server-side only (`logger.warning`) and
  raising a generic user-facing message instead. Both fixes verified
  live: a headed-Playwright repro of the stuck-spinner bug (single
  network call, StrictMode on) now correctly shows the error state and
  redirect-on-success both work; a real Resend sandbox rejection
  (`@example.com` recipient) now surfaces "Failed to send the email.
  Please try again shortly." instead of the raw client-error string,
  while the full detail still lands in the container's structured logs.
  The full delete-account flow was verified end-to-end through the
  actual UI (Playwright: verify a seeded pending signup → land on
  `/dashboard` → click through to Settings > Account → type `DELETE` →
  confirm) — real `204`, redirected to `/`, and a direct Postgres check
  confirmed both the `users` and `tenants` rows were genuinely gone
  afterward, not soft-deleted. 361 backend tests passing throughout.
- **Phone login for Personal accounts** (2026-08-11) — done, deployed
  and verified live in both dev and prod. Firebase phone login
  previously only worked for Enterprise, since it resolved the tenant
  via a caller-supplied Organization subdomain before looking up the
  phone number within that tenant. Personal accounts have no subdomain
  field, and — unlike email, which Personal login handles via
  `derive_personal_subdomain(email)` recomputing the same deterministic
  hash at both signup and login with no DB lookup — a phone number
  can't use that trick: it isn't known at signup time at all (only
  added later via Settings > Profile), so there's no fixed value to
  hash into a subdomain up front. Solved with a small, deliberately
  narrow cross-tenant lookup: new `personal_phone_logins` table
  (`phone_number_e164` as primary key, `tenant_id`/`user_id` FKs, no
  RLS — same "must be resolvable before any tenant context exists"
  reasoning as `password_reset_tokens`), populated only for
  Personal-tenant users (`is_personal_subdomain()`, new helper next to
  `derive_personal_subdomain`) — Enterprise phone numbers are
  deliberately never written here, since the same E.164 number can
  legitimately exist under two different Enterprise tenants today
  (`users.phone_number_e164` is unique per `(tenant_id,
  phone_number_e164)`, not globally). `UpdateUserProfileService` writes
  through it (upsert on save, delete on clear/change, `ConflictError`
  if another Personal account already claims the number — a real
  identity conflict, not the same "just don't enable phone login yet"
  leniency `_to_e164`'s own unparseable-number case gets);
  `AuthenticateUserService.execute_phone`'s `subdomain` became optional
  and reads through it when blank, verifying the Firebase ID token
  *before* resolving the tenant now (Personal needs the phone number in
  hand before it can look anything up, unlike Enterprise which already
  has the subdomain). Account deletion
  (`SqlAlchemyAccountDeletionRepository`) got `PersonalPhoneLoginModel`
  added to its existing tenant-scoped delete loop, verified live (both
  dev and prod) that deleting a Personal account with a registered
  phone number leaves no orphaned row and no FK violation. Frontend:
  `PhoneLoginForm`'s Organization field is now conditional
  (`showOrganizationField` prop) rather than always-required, and
  `LoginPage`'s Email/Phone method toggle — previously gated to
  Enterprise only — now renders for both account types. 13 new backend
  tests (units for both services' new branches, integration tests for
  the real end-to-end phone-login-with-no-subdomain flow and the
  delete-cleanup case) — 374 backend tests passing, mypy clean
  (including a pre-existing, unrelated mypy false-positive in
  `account_deletion.py` fixed in passing — two separate `for model in
  (...)` loops reusing the same loop-variable name confused mypy's type
  narrowing across iterations; renamed one to `direct_model`).
  **A real, unrelated Resend config gap surfaced during this work**:
  dev's `backend/.env` still had `RESEND_FROM_EMAIL=onboarding@resend.dev`
  (Resend's shared sandbox sender, which only allows sending to the
  Resend account owner's own address) even after prod's copy had
  already been fixed to a verified `noreply@scaledbrain.com` sender
  during the previous feature's live verification — dev just hadn't
  needed a real signup email sent to a non-owner address since. Fixed
  in dev too, and confirmed via a real `200 OK` from Resend's API
  (previously a `403`). **Also surfaced: `docker compose up -d
  --force-recreate` resets a container to whatever was baked into the
  image at its last real `build`, silently discarding every file ever
  added via a one-off `docker cp` since then** — not just the most
  recent one. Dev's backend container had accumulated two migrations
  this way without ever being rebuilt; recreating it for the `.env`
  change above lost both at once (`alembic current` failed outright,
  `KeyError` on a revision the loaded history no longer referenced)
  until `docker compose build backend` (a real rebuild) was run.
  **A multi-round live debugging session chasing an apparent
  Personal-vs-Enterprise phone-login discrepancy in dev turned out to
  be a false lead, not a code bug**: the user got `auth/invalid-app-credential`
  from Firebase specifically on the Personal + Phone path while
  Enterprise + Phone succeeded, against the same real phone number.
  Ruled out, in order, with direct evidence at each step: a tainted
  reCAPTCHA risk score from an earlier automated Playwright verification
  attempt (a fresh incognito window reproduced the identical failure,
  ruling this out); an interaction-count-based reCAPTCHA risk theory
  (clicking around the page before retrying didn't change the outcome);
  a stale-widget-carryover theory from removing `LoginPage`'s old
  `if (option === "personal") setMethod("email")` reset (ruled out once
  the user confirmed every Personal attempt was a genuinely fresh page
  reload, which already guarantees a brand-new widget regardless). A
  full re-read of the current `PhoneLoginForm.tsx`/`lib/firebase.ts`
  end to end confirmed neither file's Firebase/reCAPTCHA call chain
  differs at all based on account type. The real explanation surfaced
  on its own moments later: Firebase returned the explicit
  `auth/too-many-requests` on a subsequent attempt against the same
  real number — its own abuse-rate-limiter, tripped by the sheer volume
  of automated-plus-manual attempts against one real number in a single
  session (the same class of finding as
  `feedback_subagent_browser_verification.md`'s existing "don't keep
  hammering the same test number" guidance, now confirmed to
  eventually surface as an explicit, unambiguous error rather than
  staying silently mysterious). No code change resulted from this
  investigation — the Firebase/reCAPTCHA client code was correct
  throughout, exactly as the unit/integration/DB-level live tests
  already indicated.
- **Terms of Service + Privacy Policy, required at signup** (2026-08-11)
  — done, deployed and verified live in both dev and prod. The app had
  no legal documents and nothing gated account creation on agreeing to
  any — a required consent checkbox now blocks both Personal and
  Enterprise signup until checked. **Explicitly communicated to the
  user and worth restating here**: this is solid, standard-form legal
  content accurately describing what the app actually does, not a
  substitute for real legal review — drafted by Claude, not a lawyer.
  Real consent is recorded, not just a client-side checkbox that proves
  nothing later: `PendingSignup` (`app/domain/identity/entities.py`)
  gained required `agreed_to_terms_at`/`terms_version`, stamped by
  `RequestPersonalSignupService`/`RequestOrganizationSignupService` at
  the moment the signup form is actually submitted (not passed in from
  the router — computed the same place `created_at`/`expires_at`
  already are). `VerifySignupService` carries both through to
  `RegisterTenantService.execute_with_hashed_password` (gained two new
  optional params, defaulting to `None` so the existing `/tenants`
  low-level test-setup primitive is untouched), which sets them on the
  created `User` (nullable there — existing accounts from before this
  shipped are honestly left unset, not backfilled with fabricated
  consent). `CURRENT_TERMS_VERSION` is a plain version-string constant
  in a new `app/domain/identity/legal_terms.py`, not a full
  versioning/re-consent system — enough for this scope, easy to bump
  later. `PersonalSignupRequest`/`OrganizationSignupRequest` gained a
  required `agreed_to_terms: bool` field with a validator rejecting
  `False` with a clear message rather than FastAPI's generic 422
  wording. New public routes `/terms` and `/privacy`
  (`frontend/src/features/legal/`, plain hand-styled content pages —
  no typography plugin installed — sharing a small `LegalPageLayout`),
  linked from a checkbox on `SignupPage.tsx` that disables the submit
  button until checked, for both forms. One real bug caught building
  the live-verification script itself, not by review: querying the
  RLS-protected `users` table via a raw, unscoped test session failed
  with `invalid input syntax for type uuid: ""` — `current_setting(
  'app.tenant_id', true)` returns an empty string rather than NULL in
  that context, and casting `''::uuid` errors; fixed by binding
  `set_tenant_context()` first, the same pattern every other
  tenant-scoped raw query in the test suite already uses. A second,
  unrelated flaky-test finding surfaced during this same live-test run
  (not fixed, out of scope for this feature): `_unique_test_phone_number()`
  in `test_identity_flow.py` only has 100 possible values (555-0100
  through 555-0199), which is a real, if rare, collision risk as the
  phone-login test suite grows — worth widening if it recurs. 375
  backend tests passing (2 new: reject-without-agreeing at both the
  schema-validator and full-request-integration level), mypy clean.
  Verified live via headed Playwright in dev (submit button genuinely
  disabled until checked, real signup request reaches the backend and
  creates a `pending_signups` row with a real `agreed_to_terms_at`
  timestamp once checked, the Terms link opens a real rendered page in
  a new tab) and via direct HTTP + Postgres checks against
  `scaledbrain.com` in prod (schema present, `agreed_to_terms: false`
  rejected with the custom message, `agreed_to_terms: true` creates a
  real `pending_signups` row with consent recorded).
- **support@scaledbrain.com email + welcome email + Platform Admin**
  (2026-08-13) — done, deployed and verified live in both dev and prod.
  Three related pieces of work from the same session. **(1)**
  `support@scaledbrain.com` now forwards to a real inbox via Cloudflare
  Email Routing (MX/SPF records auto-added by Cloudflare, destination
  address verified) — pure DNS/dashboard config, no code or repo
  changes. The one real gotcha: a freshly-forwarded message reliably
  lands in the destination's Spam folder on the first send (forwarded
  mail's envelope doesn't SPF/DKIM-align with the original sender), not
  a misconfiguration — fixed client-side with "Not spam" once, or a
  permanent Gmail filter rule. **(2)** A new post-verification welcome
  email (`"Welcome to Career Compass AI!"`, sent from a distinct
  `welcome@scaledbrain.com` identity, separate from `noreply@`'s
  verification/reset emails) fires at the end of `VerifySignupService.execute`
  — best-effort (a provider outage logs and continues, doesn't block the
  login that verification already earned). `EmailMessage` gained an
  optional `from_email` override so one `ResendEmailProvider` instance
  can send from multiple verified identities on the same domain without
  a second provider instance; `RequestPersonalSignupService`/
  `RequestOrganizationSignupService`/`RequestPasswordResetService` all
  now take an explicit `from_email` too, sourced the same way (see
  Platform Admin below), not just `VerifySignupService`. **(3) Platform
  Admin** — the first genuinely cross-tenant admin concept in this app,
  prompted by wanting `resend_from_email`/`resend_welcome_from_email` to
  be editable from a real UI instead of only via `.env` + a redeploy,
  then explicitly generalized on request into: a reusable
  `platform_settings` key/value store, and a real grant/revoke system
  so more than one person (potentially in different tenants entirely)
  can hold platform-admin access at different permission levels.
  Deliberately does **not** reuse the existing tenant-scoped RBAC engine
  (`require_permission`/`has_permission`/`roles`/`user_roles`) — that
  engine's role resolution is inherently scoped to the caller's own
  tenant via RLS, which is the wrong shape for "is this specific
  (tenant_id, user_id) a platform admin, regardless of which tenant
  they belong to." Instead follows the established
  "purpose-built table with no RLS at all" precedent
  (`personal_phone_logins`, `password_reset_tokens`) with two new
  global tables: `platform_admins` (tenant_id/user_id/email/full_name
  snapshot/`permission_codes` JSON list/granted_at/granted_by_user_id,
  unique per (tenant_id, user_id)) and `platform_settings` (key/value/
  description/updated_at/updated_by_user_id, unique per key) — neither
  gets `ENABLE`/`FORCE ROW LEVEL SECURITY`, same as `model_versions`/
  `prompt_versions`. Three permission codes
  (`app/domain/platform_admin/permissions.py` — a plain constant tuple,
  not a DB reference table, since there are only three and they never
  vary per tenant): `platform.settings.view`, `platform.settings.edit`,
  `platform.admins.manage`. New `require_platform_permission(code)`
  dependency (`app/api/dependencies.py`) is the cross-tenant sibling of
  `require_permission` — checks the caller's own grant directly by
  `(tenant_id, user_id)` from their JWT, no RLS-scoped role resolution
  involved. `PlatformAdminService.grant()` resolves a target account by
  email using the *exact* same subdomain-resolution login already uses
  (`derive_personal_subdomain(email)` for a bare email, an explicit
  subdomain for Enterprise) — binds tenant context just long enough to
  look the target user up, then writes to the RLS-exempt
  `platform_admins` table. A defensive check
  (`count_with_permission(PLATFORM_ADMINS_MANAGE) <= 1`) blocks
  revoking or downgrading the last remaining holder of
  `platform.admins.manage`, so the system can never end up with no one
  able to grant access back. 7 new endpoints under
  `/api/v1/platform-admin/*` (`GET /me` needs no permission — any
  authenticated user can ask "am I an admin," returning empty
  `permission_codes` if not; the rest are gated per-code).
  `resend_from_email`/`resend_welcome_from_email` are now resolved from
  `platform_settings` at request time (via `get_resend_from_email`/
  `get_resend_welcome_from_email` in dependencies.py, constructing a
  repository directly rather than through the later-defined
  `get_platform_settings_repository` — `Depends()` default arguments
  are resolved at function-*definition* time, so referencing a
  not-yet-defined function there would raise `NameError` at import),
  falling back to the static env value if no admin has ever edited it —
  `scripts/seed_platform_defaults.py` seeds the initial row from
  today's env value exactly once, never overwriting a real admin edit
  on reseed. New `PLATFORM_ADMIN_BOOTSTRAP_ACCOUNTS` env var (comma-
  separated `subdomain:email` or bare `email` entries) bootstraps the
  very first platform admin(s) at seed time — necessary because with
  zero admins granted, nobody could ever reach the admin page to grant
  the first one; idempotent, and silently skips (logs, doesn't error)
  any account that doesn't exist yet in that environment. Frontend: new
  Settings > Platform Admin page
  (`frontend/src/features/settings/SettingsPlatformAdminPage.tsx`,
  `/settings/platform-admin`) — a Settings key/value editor and an
  Admins list/grant/revoke panel, each section gated on the caller's
  own `permission_codes` (read via a new `usePlatformAdminMe()` hook
  hitting `GET /platform-admin/me`, not stored in the JWT/auth-store —
  deliberately always resolved fresh per load, not cached at login
  time, so a revoked admin's nav access disappears on their next
  navigation rather than surviving until next login). `nav-items.ts`
  gained a `STANDARD_SETTINGS_NAV_ITEMS` export (the existing three,
  minus Platform Admin) so `AccountPanelContent.tsx` can render the
  full list only for a caller with at least one `platform.*`
  permission, while `SETTINGS_NAV_ITEMS` itself still includes Platform
  Admin so `matchNavItem` resolves the right page title for someone who
  *does* have access.
  **Four real bugs caught building and live-verifying this, not by
  review**: (1) `docker compose -f infra/docker-compose.yml up -d`
  (single explicit `-f`, run from the repo root rather than `cd infra
  && docker compose up`) silently drops `docker-compose.override.yml`
  — which is what actually supplies `--reload` to the dev backend's
  uvicorn command — since Compose only auto-includes the override file
  when *no* `-f` flag is given at all. Recreating the container this
  way for an `.env` pickup (a legitimate, previously-documented need)
  quietly strips hot-reload for every code change afterward until the
  container is recreated correctly (`cd infra && docker compose up -d`,
  no explicit `-f`, matching `start-dev.ps1`'s own invocation) — a code
  fix can silently keep failing to take effect with zero error, which
  is exactly what happened mid-session here. (2) The `resend_send_failed`
  warning log only ever recorded `str(exc)` for an `httpx.HTTPStatusError`
  — which is a generic `"Client error '403 Forbidden' for url ...'"`
  message, **not** Resend's actual response body, despite an existing
  code comment claiming otherwise. This hid the real diagnosis of a
  welcome-email send failing with 403 for several debugging rounds (it
  turned out to be sending from the *wrong* address — the new
  `resend_welcome_from_email` setting wasn't reaching the container at
  all, for the exact `docker compose up` reason above — Resend's actual
  error, `"You can only send testing emails to your own email
  address..."`, immediately would have named the real sender in use).
  Fixed in `resend_provider.py` by catching `HTTPStatusError`
  specifically and logging `exc.response.text` — worth keeping this
  fix regardless of the specific bug that surfaced it. (3) Deleting an
  account that held a `platform_admins` grant (as either owner or
  granter) raised a raw `ForeignKeyViolation` 500 —
  `SqlAlchemyAccountDeletionRepository.delete_tenant` didn't know about
  either new table. Fixed: `PlatformAdminModel` added to the existing
  ordered direct-children delete loop (before `UserModel`);
  `platform_settings.updated_by_user_id` (nullable) is set to `NULL`
  for the deleted tenant's users rather than deleting the setting row
  itself, since a real platform-wide config value shouldn't vanish just
  because whoever last edited it also deleted their account.
  `platform_admins.granted_by_user_id` (NOT NULL) granting *someone
  else's* still-existing admin row is accepted as a known, undhandled
  edge case — same shape and same reasoning as the pre-existing
  `content_revisions.reviewed_by` gap this file's own docstring already
  documented — not expected to come up at this app's admin-count scale.
  New regression test:
  `TestDeleteAccount::test_delete_removes_platform_admin_grant`. (4)
  Deploying the frontend to prod for the first time since the previous
  session's "animated two-phase background wave" commit landed revealed
  that commit had shipped with 5 real TypeScript errors in
  `LandingPage.tsx` (`noUncheckedIndexedAccess` flagging
  `FLOCK_ROW_COUNTS[row]` as possibly-`undefined`, plus two genuinely
  dead constants left over from an earlier version of the animation) —
  invisible via `npm run dev` (Vite's dev server doesn't block on
  `tsc`), but a hard failure for `npm run build`, meaning prod's
  frontend image had been unbuildable since that commit without anyone
  noticing until this session's deploy. Fixed (a non-null assertion
  where the loop bound already guarantees the index is in range; the
  two dead constants deleted) — unrelated to Platform Admin itself, but
  found and fixed in the course of shipping it.
  Verified live end-to-end in dev via a real headless-Chromium
  Playwright run driving the actual UI (not just API calls): logged in
  as a real platform admin, edited `resend_from_email` and confirmed
  "Saved," reverted it, granted a second real account
  `platform.settings.view` through the real grant form, confirmed it
  appeared in the Admins list, revoked it through the real UI with its
  `ConfirmDialog`, and confirmed via direct Postgres queries that both
  the setting's final value and the post-revoke admin list matched
  exactly what the UI showed. (Caught one test-script-only gotcha along
  the way, already documented elsewhere in this file for Resume
  Intelligence but re-confirmed here: a hard `page.goto()` to an
  internal route wipes the in-memory access token, since
  `auth-store.ts` never persists it — client-side navigation only.)
  Also verified live: a full real personal-account signup +
  verification (via a real mailinator inbox, not a mock) showing both
  the verification email from `noreply@scaledbrain.com` and the new
  welcome email from `welcome@scaledbrain.com` arriving in the same
  inbox. 377 backend tests passing (277 unit + 100 integration, 1 new
  regression test), mypy clean across all 189 backend source files.
  Deployed to prod: migration `a3f8c1d92b47` applied, seed script run
  (bootstrapped `bcmaharana@gmail.com`'s existing Personal account as a
  full platform admin — the `scaledbrain` Enterprise tenant doesn't
  exist in prod yet, so that half of
  `PLATFORM_ADMIN_BOOTSTRAP_ACCOUNTS` correctly no-ops there for now),
  both backend and frontend images rebuilt and redeployed, health
  checked end-to-end.
- **Platform Admin follow-ups + Career Profile > Download Resume**
  (2026-08-13, same day) — done, deployed and verified live in both dev
  and prod. Three Platform Admin refinements requested after the first
  round of real usage, then a large new feature. **(1)** System Status
  moved from the Dashboard to Settings > Platform Admin, laid out
  side-by-side with Platform Settings (`SettingsPlatformAdminPage.tsx`:
  `grid lg:grid-cols-2` — Platform Settings + Platform Admins stacked in
  the left column, System Status alone on the right, so the second
  card's height never pushes the left column's own internal spacing
  around — an earlier version nested System Status *inside* the shared
  grid row itself, which left a large, confusing gap between Platform
  Settings and Platform Admins whenever System Status was the taller of
  the two). **(2)** Real gap found live: a grant with only
  `platform.settings.edit` (no `platform.settings.view`) hit "You don't
  have access to this page," since edit access didn't imply view
  access anywhere. Fixed by making `require_platform_permission` variadic
  with OR semantics (`app/api/dependencies.py`) — `GET
  /platform-admin/settings` now accepts either code — and mirroring the
  same OR logic in the frontend's own gate. **(3)** The permission
  checkbox list (pick any combination of the three codes) was replaced
  with a proper radio group of three ordered access levels — View, Edit
  (implies View), Manage (implies both, full access) — since the three
  codes were never really independent in practice; `LEVEL_CODES` in
  `SettingsPlatformAdminPage.tsx` is the one place that maps a level to
  its underlying code set, used identically by the grant form and each
  existing admin's row.
  **Download Resume**: from the Career Profile page (Master or any
  Target Role Profile — these are already fully independent profiles
  in this app, per Phase 2's design, so "download this specific
  profile's resume" needed no new tailoring/generation-from-Master
  logic, just rendering whichever profile is currently open), a new
  action bar (`ResumeDownloadBar.tsx`) generates a formatted `.docx` or
  `.pdf` resume, downloads it immediately, and saves it as *the*
  current resume for that profile — regenerating a format replaces the
  previous file for that format (never accumulates a history), the
  same model `CareerProfile.photo_url` already established. Three new
  nullable columns on `career_profiles`
  (`resume_docx_key`/`resume_pdf_key`/`resume_generated_at`, migration
  `c7e2f9a04d18`) back a persistent "View Word / View PDF" link shown
  on the profile page from then on. New `app/adapters/documents/`
  package: `resume_docx_builder.py` (python-docx — already a
  dependency, used today only for *reading* uploaded resumes; its
  `Document` API is bidirectional so no new dependency was needed to
  write one) and `resume_pdf_builder.py` (new dependency: `reportlab`,
  chosen over `weasyprint` specifically to avoid adding Pango/cairo/
  gdk-pixbuf system packages to the Docker image — reportlab is pure
  Python). Both builders share `resume_data.py`'s `ResumeData` bundle
  and mirror the exact "a description line starting with '• ' is a
  real bullet, everything else is a plain paragraph line" convention
  already used by the Career Profile page's own UI and the resume
  -extraction prompt, so a generated resume's bullet/paragraph shape
  matches what the person already sees on their profile. New
  `ResumeExportService` (`app/application/career_profile/`) gathers the
  profile + every child section + the owning `User` (for the name/
  contact header — `CareerProfile` itself has no name/email/phone,
  those live on `User`), builds the requested format, uploads it to the
  same private resumes bucket Resume Intelligence already established,
  and updates the profile's key fields. Storage keys, not URLs, are
  what's persisted — `GET`/`PATCH /career-profile` and the new `POST
  .../resume-export` all resolve a *fresh* presigned URL on every
  response (1 hour TTL, deliberately longer than
  resume_intelligence's own 300s single-use default, since this one is
  meant to sit on the page as a clickable link, not be used once
  immediately after upload) rather than ever storing a presigned URL,
  which would silently go stale. `PrivateObjectStorageRepository`
  (`app/domain/resume_intelligence/storage.py` — already documented as
  a deliberately generic, cross-domain-reusable port) gained an
  optional `download_filename` param on `get_presigned_url`, setting
  `ResponseContentDisposition` so opening the link downloads with a
  real name ("Jordan Rivera - Staff Engineer - Resume.docx") instead of
  the raw storage key/UUID.
  **A real bug caught live, not by review**: the very first generated
  download URL pointed at `http://minio:9000/...` — the backend's
  *internal* Docker endpoint, unreachable from any browser, silently
  broken despite a 200 response and a correctly-shaped URL. Root cause:
  boto3's presigned-URL signing bakes the request's `Host` into the
  SigV4 signature itself, and the existing single S3 client was
  constructed with `endpoint_url=OBJECT_STORAGE_ENDPOINT` (the
  internal address) for every operation, presigning included — the
  long-documented `OBJECT_STORAGE_ENDPOINT` vs `OBJECT_STORAGE_PUBLIC_URL`
  gotcha elsewhere in this file turned out to apply to presigned URLs
  too, not just the public-bucket `upload()` path that gotcha was
  originally written about. Fixed with a *second* boto3 client in
  `S3ObjectStorageRepository`, identical except constructed with
  `endpoint_url=OBJECT_STORAGE_PUBLIC_URL`, used only by
  `get_presigned_url()` — confirmed live afterward with a real `curl`
  against the returned URL showing `200`, the correct
  `Content-Disposition` header, and the correct file bytes.
  Also hit again this session: the now-twice-documented `docker compose
  -f infra/docker-compose.yml up` (explicit `-f`, run from the repo
  root) silently drops `docker-compose.override.yml`'s `--reload` —
  this cost a fresh migration file that had to be re-`docker cp`'d in
  after a container recreate wiped it. Both the migration and code are
  now baked into a real rebuilt dev image (`docker compose build backend`
  from `infra/`, not just `up`) specifically to stop relying on `docker
  cp` surviving future recreates.
  7 new unit tests for `ResumeExportService` (fake repositories +
  fake storage, real document builders — no database, no real object
  storage, matching this test suite's own established boundary: no
  existing test anywhere hits real MinIO, including Resume
  Intelligence's own upload-and-parse flow). 383 backend tests passing
  (1 pre-existing, documented flaky failure — the phone-number-collision
  test noted earlier in this file — confirmed unrelated by rerunning in
  isolation), mypy clean across all 194 backend source files. Verified
  live end-to-end via real headless-Chromium Playwright runs: generated
  both formats from a real Master profile, confirmed the persistent
  "View Word"/"View PDF" links survive a fresh client-side navigation
  (a real `GET /career-profile`, not just the mutation's cached
  response), and separately confirmed a Target Role Profile's generated
  resume gets its own independent file (own storage key, own filename
  including the role name) without touching the Master profile's.
  Deployed to prod: migration `c7e2f9a04d18` applied, backend +
  frontend images rebuilt, health checked end-to-end.
- **Resume-inclusion toggles + 3 new profile fields** (2026-08-14,
  same session as Download Resume) — done, verified live in dev; prod
  migration/rebuild not yet done. Two features requested together:
  (1) a per-section and per-item "include this in a generated resume?"
  toggle across the whole Career Profile page; (2) three new Settings >
  Profile fields — Visa Status (dropdown), LinkedIn Profile URL, Other
  Professional URL.

  **Toggle data model**: `include_in_resume BOOLEAN NOT NULL DEFAULT
  true` added to all 7 per-item orderable entities (Experience,
  Education, Certification, CareerGoal, CareerHighlight, KeyAchievement,
  PeerEndorsement) plus `CoreCompetency.include_in_resume` (inside the
  existing `core_competencies` JSON blob — no new column). Whole-section
  toggles live in a new `career_profiles.resume_section_toggles JSON
  NULL` column, keyed by the same section keys
  `CareerProfilePage.tsx`'s `SECTION_DEFS`/`section_order` already use —
  a missing key (including a profile that's never touched this at all)
  means "on," so no existing profile's resume output changes until
  someone actually flips a toggle. Migration `d8f3a5c17b62`. Every
  entity's `update()` endpoint/service/repository gained an
  `include_in_resume` param (reusing the existing per-item update flow
  rather than adding 8 new toggle-specific endpoints, matching how
  `CoreCompetenciesSection.tsx`/`CareerProfilePage.tsx` already resend
  unchanged fields alongside a real change); `create()`/`add()` paths
  were deliberately left untouched — new items rely on the entity's own
  Python-level `default=True`.

  **Two sections newly join resume generation**: Career Goals and
  Recommendations (Peer Endorsements) were never part of a generated
  resume before this (see the Download Resume entry above, which
  explicitly scoped them out) — added as real renderable sections in
  both `resume_docx_builder.py`/`resume_pdf_builder.py`
  (`_render_career_goals`/`_render_recommendations`, the latter using
  DOCX's built-in "Intense Quote" style / a custom indented reportlab
  style for the testimonial text) and `DEFAULT_RESUME_SECTION_ORDER`/
  `resolve_resume_section_order` in `resume_data.py`. `ResumeData`
  gained `career_goals`/`recommendations` fields;
  `ResumeExportService._gather()` now also fetches
  `CareerGoalRepository`/`PeerEndorsementRepository` (career_goals via
  `list_for_user`, since that entity is `user_id`-scoped not
  `career_profile_id`-scoped — shared across Master and every Target
  Role Profile, unlike everything else this service gathers) and
  filters every list two ways before handing it to the builders: drop
  items with `include_in_resume=False`, and drop the *entire* list if
  `resume_section_toggles` has that section's key set to `false`
  (`ResumeExportService._section_enabled`) — a section-off wins over
  any individual item's own toggle. Core Competencies gets the same
  treatment via a `dataclasses.replace()`'d profile view
  (`resume_profile`) passed to the builders, keeping the *actual*
  persisted profile (with its full, unfiltered `core_competencies`)
  intact for the `resume_docx_key`/`resume_pdf_key` update at the end
  of `generate()`.

  **Frontend**: new hand-rolled `Switch` component
  (`components/ui/switch.tsx`, no Radix — matches this app's existing
  minimal-dependency convention) plus a `ResumeIncludeToggle` wrapper
  (`features/career-profile/ResumeIncludeToggle.tsx`) used identically
  at both the section level (`SectionOrderProps` gained
  `resumeIncluded`/`onToggleResumeIncluded`/`resumeToggleDisabled`,
  computed once in `CareerProfilePage.tsx` and threaded through every
  `SECTION_DEFS` entry) and the per-item level (every one of the 7
  entity section components, plus each Core Competency chip — gated
  behind that section's existing `isEditMode` for the chips specifically,
  since chips are dense and already gate their pencil/X icons the same
  way; the 7 full-card sections show their per-item switch always,
  not edit-mode-gated, since toggling inclusion isn't itself an edit
  action). Placement and behavior were refined twice from live
  feedback during the build: the switch moved to be the *first* control
  in every action row (before Add/Edit/Clear), the redundant "Resume"
  text label next to it was dropped (the switch reads clearly enough on
  its own once it's first), it's vertically centered (`self-center`)
  against its taller sibling buttons, and its hover title reads "Toggle
  off to exclude this from the resume" / "Toggle on to include this in
  the resume" depending on current state. Settings > Profile's 3 new
  fields follow the existing form's exact pattern — Visa Status is a
  `<Select>` sourced from a new plain curated list
  (`lib/visa-status-options.ts`, the standard US work-authorization
  values, not `Intl.DisplayNames`-backed like country/language since
  there's no such registry for this), LinkedIn/Other Professional URL
  are plain `<Input type="url">` with no format validation (same
  permissive treatment as `credential_url` elsewhere in this app).
  `openapi-typescript`'s generated types made every request schema's
  `include_in_resume` field non-optional (a known
  has-a-default-so-it's-"required" behavior, not a bug in the OpenAPI
  spec itself, which correctly omits it from `required`) — every
  existing add/update call site across 9 components had to start
  explicitly sending it, which surfaced two more real spots doing the
  same field-preservation dance: `CoreCompetenciesSection.tsx` and
  `MySkillsSection.tsx`'s (skill-intelligence page) edit-dialog submits
  now look up and preserve the item's existing `include_in_resume`
  rather than silently resetting it to `true` on every edit.

  **A real, pre-existing concurrency bug was caught live while testing
  this feature, not by review**: a brand-new user's first Career Profile
  page visit fires roughly eight parallel section-list GET requests
  (experiences, educations, certifications, highlights, achievements,
  goals, target-roles, endorsements), each independently calling
  `CareerProfileService.get_or_create` — since none of them see an
  existing profile yet, more than one can race to `INSERT` the Master
  profile row, and the loser hit a raw, unhandled
  `psycopg.errors.UniqueViolation` on
  `uq_career_profiles_master_per_user` (or `..._target_role_per_user`
  for a Target Role Profile), surfacing as a genuine 500 to the browser
  — reproduced repeatedly via headless-Playwright runs against a fresh
  account, not a one-off fluke. This class of bug almost certainly
  predates this session's changes (nothing about the toggle feature
  touches `get_or_create`'s concurrency shape) but had never previously
  been exercised by any test or live-verification pass that happened to
  hit this exact "brand new user's very first page load" timing. Fixed
  in `SqlAlchemyCareerProfileRepository.create()`
  (`app/adapters/db/repositories/career_profile.py`): the `INSERT` now
  runs inside a SAVEPOINT (`session.begin_nested()`), and a caught
  `IntegrityError` matching `uq_career_profiles` is translated to a
  domain `ConflictError` — deliberately *not* a plain
  `await self._session.rollback()`, which would also discard the RLS
  tenant-context GUC (`set_config('app.tenant_id', ..., true)`, set
  once per request in `get_tenant_scoped_session` and transaction-local
  like `SET LOCAL`) and silently break RLS for every later query in the
  same request; a savepoint rollback undoes only the failed `INSERT`.
  `CareerProfileService.get_or_create()` catches that `ConflictError`
  and re-fetches via `get_by_user_id` to return the concurrent winner's
  row instead of raising. Regression test added
  (`TestGetOrCreateRaceRecovery` in `test_career_profile_service.py`,
  a fake repository that raises `ConflictError` on its first `create()`
  call after seeding the "winner"'s row directly, mirroring what a real
  losing request would see). Verified live afterward: 4 consecutive
  fresh-account Playwright runs against the real dev stack, zero
  console errors, zero 5xx responses (the same repro that had
  intermittently failed roughly half the time before the fix).

  **Also requested live, after the toggle feature was otherwise done**:
  the resume header's contact line (previously just `email | phone`)
  now also shows location (`city, state`), Visa Status, and LinkedIn URL
  with its `https://`/`https://www.` scheme+host prefix stripped (a
  bare `linkedin.com/in/name` reads cleaner in a resume header) — new
  shared `contact_line_parts()`/`_strip_url_scheme()` helpers in
  `resume_data.py`, used identically by both builders so the two
  formats' headers can't drift apart. 6 new unit tests
  (`TestContactLineParts`), verified live via a real generated DOCX
  (`admin@... | +1 415 555 0100 | San Francisco, CA | H-1B |
  linkedin.com/in/admintestuser`).

  418 backend tests passing (1 pre-existing, documented flaky failure —
  the same phone-number-collision test noted earlier in this file —
  confirmed unrelated by rerunning in isolation), mypy clean across all
  195 backend source files, frontend `typecheck`/`lint` both clean.
  Verified live end-to-end in dev via real headless-Playwright runs
  (fresh account → toggle a per-item switch off → toggle a whole
  section off → confirm both survive a brand-new login session, i.e.
  real Postgres persistence, not just client cache → save the 3 new
  Settings > Profile fields → confirm those persist the same way) and
  directly via HTTP (Settings > Profile round trip, resume generation
  respecting both toggle levels together). Deployed to prod later the
  same day (see the next entry), which is what finally applied
  `d8f3a5c17b62` there.
- **Account-recovery investigation + Platform Admin/Dashboard/Skill
  Intelligence fixes** (2026-08-14) — done, deployed and verified live
  in both dev and prod. A long single session, starting from a real
  incident: the user reported all profile data missing for both
  `bcmaharana@hotmail.com` and `bcmaharana@gmail.com` in prod.
  Root-caused via direct DB queries plus the real audit-event login
  trail (not guessed): `derive_personal_subdomain(email)`'s hash-based
  scheme (introduced by the Email-verification commit, `cde9183`,
  20:09 on 2026-08-10) was never backfilled onto the hotmail Personal
  tenant, which had been created *before* that commit under a literal
  `subdomain="personal"` — from that point on, Personal login for that
  email computed a completely different subdomain and could never
  resolve to it again, even though the tenant (and its real, actively-
  used profile data — 13 real logins, a real password reset, an hour
  of real profile editing on 2026-08-10) was still sitting untouched in
  the database. Fixed with a one-row `UPDATE tenants SET subdomain =
  ...` to the correct hash value — confirmed live afterward (user
  logged in and saw their real data). A second sub-investigation
  (whether a since-downloaded resume implied data had "moved" from one
  account to another) turned out to be dev/prod confusion, not a bug:
  extracting the actual `.docx` file's text and cross-referencing
  `resume_generated_at` timestamps against both databases showed the
  file came from a long-standing **dev** account (`scaledbrain`
  subdomain, since 2026-07-19) entirely unrelated to prod's empty
  same-named Enterprise account — the two are separate databases that
  happen to share a subdomain string. No code changes resulted from
  either investigation; both were pure data/forensics work using direct
  `psql` queries, real login-audit timestamps, and (for the resume
  file) `System.IO.Compression` to unzip and read `document.xml`
  directly.

  From there, four real follow-on fixes, each triggered by the user
  actually using the app and noticing something wrong — the standing
  pattern for this whole session, not a coincidence:

  1. **Platform Admin: same-email grants were indistinguishable.**
     Granting both a Personal and an Enterprise account under the same
     email (a direct consequence of the recovery above) showed two
     identical-looking rows in the Admins list. Fixed by snapshotting
     `subdomain` on `platform_admins` (migration `e1f4b8d67a52`, same
     "avoid a cross-tenant lookup" reasoning as the existing email/
     full_name snapshot) and labeling each row "Personal account" or
     "Enterprise · `<subdomain>`". While there: noticed the *existing*
     `full_name` snapshot goes stale forever once set (only refreshed
     when the grant itself is re-saved) — `UpdateUserProfileService`
     now refreshes any existing grant's `full_name` after every profile
     save, plus a one-time backfill for the rows that were already
     stale in both dev and prod.
  2. **Dashboard rebuilt.** The two Phase-0 placeholder cards (a raw
     health-check ping, a "signed in as" debug readout) had zero
     product value once System Status and the Right Nav identity box
     existed — user flagged this directly. Replaced with three real
     cards built entirely from data already fetched elsewhere (Career
     Profile summary, Gap Analysis, Resume Intelligence history) — no
     new backend endpoints — one row per profile (Master + each Target
     Role Profile), refined through several rounds of live feedback:
     a completeness percentage instead of a headline preview, per-role
     missing-skill counts instead of individual skill badges (renamed
     "Skill Gaps" → "Skill Intelligence" to match the actual page
     name), last-uploaded/last-downloaded resume per profile (renamed
     "Resumes" → "Resume Intelligence"), cards stacked vertically per
     explicit request. `useHealthCheck`/`health.ts` deleted as fully
     orphaned once nothing called it anymore.
  3. **Core Competencies/My Skills: comma-separated multi-add.** The
     existing Add dialog only ever created one competency per
     submission; typing `Python, SQL, AWS` created one literally named
     that. Now splits on comma, applied identically to both pages since
     they edit the same field — new `buildCompetenciesFromAddInput` in
     `lib/group-by-category.ts`. A blank category on a bulk add now
     defaults to the literal `"Unknown"` category (real, renamable) —
     the "Fully matched/N uncategorized" Dashboard messaging below
     exists specifically because this real user data has a lot of
     `"Unknown"`-tagged skills now.
  4. **Career Profile: state/DOM leaking across Master ↔ Target Role
     switch — two bugs, the second a regression from fixing the
     first.** Switching profiles is a client-side `?role=` search-param
     change, not a navigation, so no section component ever unmounted
     on switch. First report: leaving Core Competencies in edit mode on
     a Target Role Profile and switching to Master showed Master's Core
     Competencies already in edit mode — every scope-dependent
     component (`ProfileHeader`, `ExecutiveSummarySection`,
     `ResumeDownloadBar`, every reorderable section) now keys off scope
     to force a real remount, same pattern Resume Intelligence's review
     screen already uses. **That fix's first pass introduced a second,
     worse bug**: giving three sibling elements (`ResumeDownloadBar`,
     `ProfileHeader`, `ExecutiveSummarySection`) the exact same literal
     key broke React's reconciliation between them — reported live as
     the profile photo/header visibly duplicating and accumulating with
     every target-role click. Reproduced both bugs and confirmed the
     real fix (each sibling keyed uniquely) via an actual headless-
     browser session against a throwaway dev account — React's own
     "two children with the same key" console warning, and a photo-
     header count climbing 1→2→3→4→5 across clicks, both gone
     afterward.
  5. **Gap Analysis silently ignored target-role-specific
     competencies.** `GapAnalysisService` only ever read the Master
     Profile's `core_competencies` for every role's gap computation,
     never that specific role's own (Core Competencies became a
     genuinely per-profile field after Target Role Profiles were made
     fully independent, but this service was never updated to match).
     Reported live against the user's real data: "Senior Scrum
     Master/Team Coach" had ~38 required skills nearly all satisfied by
     competencies added directly to *that* target role's own profile,
     but showed almost all of them as missing, since Master's unrelated
     competency list barely overlapped. Fixed by unioning Master's
     competencies with the specific target role's own when computing
     "owned" skills — backward compatible, a role nobody's tailored
     stays Master-only. Verified live via a direct (read-only,
     non-destructive) API call against the real account this was
     reported on: the role now shows zero missing skills.

  Every fix in this session was verified live before being called
  done, not just reasoned about — direct `psql` queries against both
  the dev and prod databases throughout, and, for every frontend
  change, real headless-Chromium Playwright sessions driving the
  actual app (including two throwaway dev accounts created via the
  low-level `/tenants` primitive specifically for reproduction, each
  deleted via the real self-service `DELETE /identity/me` afterward —
  never left lying around). One reusable technique worth keeping: to
  verify a fix against a specific real user's account without ever
  touching their password, mint a short-lived JWT locally (dev's
  `JWT_SECRET_KEY` is a known placeholder) matching `IdentityClaims`'
  shape and call the real API directly — read-only, nothing persisted,
  no credential ever touched. 406 backend tests passing, mypy clean,
  frontend `typecheck`/`lint` clean throughout. `start-prod.ps1` also
  gained a wait-for-frontend-to-accept-connections step this session
  (separate, smaller fix, same day) so the Cloudflare Tunnel has less
  of a gap to log connection-refused errors into after a machine/Docker
  restart.
- **Not yet started**: Phase 6 onward through Phase 9 (Phase 4.5.2+ —
  CIKG MVP 3/4/5 — also not started; see
  `docs/architecture/cikg-mvp-roadmap.md`). Domain list in
  `docs/architecture/system-overview.md`; that doc doesn't enumerate a
  numbered phase-by-phase roadmap the way this section does — the phase
  numbers (1 Identity, 2 Career Profile, 3 Skill Intelligence, 4 AI
  Platform real wiring, 4.5 CIKG Foundation, 5 Resume Intelligence, 6
  Opportunity Intelligence, 7 Learning Intelligence, 8 AI Career Coach) are tracked
  here and in project memory only.

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