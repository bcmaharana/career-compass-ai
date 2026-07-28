# Career Compass AI — UI Enhancement Brief

For Claude Code. Read `CLAUDE.md` at the repo root first for full project
context (architecture, conventions, environment setup, current status).
This brief covers a round of UI/UX refinement requested before starting
Phase 3 (Skill Intelligence) — all items below are frontend-only unless
noted.

---

## Part 1 — Global App Shell (every page)

### 1.1 Four fixed regions around one scrollable center

Extend the current app shell (`frontend/src/components/layout/AppShell.tsx`,
which already has a fixed/sticky Left Nav) to add three more fixed
regions:

- **Header** (top)
- **Footer** (bottom)
- **Right Nav** (right side)

All four — Left Nav, Header, Footer, Right Nav — stay fixed in place at
all times, exactly like the existing Left Nav behavior. **None of them
ever hide or scroll**, regardless of scroll position. Only the center
content area (where `<Outlet />` renders) scrolls.

Content inside Header, Footer, and Right Nav is contextual — it changes
based on the current route / whichever Left Nav item is selected.

### 1.2 Footer: AI Chat

The fixed Footer contains a persistent AI Chat input box, present on
every page.

- When the user asks a question, the response is **appended to the
  center panel** (below whatever page content is already there), and
  the panel **auto-scrolls down** to reveal the new exchange — the same
  behavior as this chat interface itself (new messages push the view
  down, older content is still there above if you scroll up).
- The underlying page content is never replaced by the chat — it's
  scrolled past, not removed.
- **Navigating to a different Left Nav item clears the chat thread**
  from the center panel view (which then shows the newly-selected
  page's own content) — but the conversation itself is **persisted to
  the database** and retrievable later. Retention period for stored
  chats is not yet decided — build the persistence, leave retention
  policy as a follow-up decision (e.g., a config value, not hardcoded
  forever-storage or auto-delete).
- **Scope for this round: UI/layout shell only.** Wire up the input,
  the message list, the auto-scroll behavior, and the database
  persistence — but the actual AI response can be a placeholder/echo
  for now. Real AI reasoning depends on the AI Platform being wired to
  a live provider, which is later work (see `docs/architecture/ai-platform-architecture.md`
  and `docs/adr/ADR-004-ai-governance-strategy.md` — roughly Phase 4/8
  territory in the original roadmap).

### 1.3 Header: page name, purpose, quote of the day

After login, the fixed Header shows, per page:

1. Page name (e.g., "Career Profile," "Dashboard")
2. A short page purpose/description line
3. A small "quote of the day" — noticeably smaller font than the page
   name/purpose

Quote source: an **external quotes API** for now (pick a free/simple
one — e.g., something like quotable.io or similar), with a known future
plan to replace it with a custom/owned quote source. Don't hardcode
tightly to the specific API in a way that makes swapping it later
painful — a small adapter/service function is enough.

### 1.4 Right Nav: standard content + per-page lower section

Right Nav top section, present on every page:

1. Logged-in user's name + small profile icon
2. Current date
3. Current time
4. Below that: a Settings link/icon

A divider line separates that from a **lower section whose content
varies by page**. For most pages, this lower section's design is
**deferred to a later stage** — build the structural placeholder
(the divider + an empty/contextual slot), but only the Career Profile
page (see Part 2.5 below) has its lower-section content specified in
this round.

---

## Part 2 — Career Profile Page Specifically

(`frontend/src/features/career-profile/` — `CareerProfilePage.tsx` and
its section components: `ProfileHeader.tsx`, `ExperienceSection.tsx`,
`EducationSection.tsx`, `CertificationSection.tsx`,
`CareerGoalsSection.tsx`, `CareerHighlightsSection.tsx`,
`KeyAchievementsSection.tsx`, `PeerEndorsementsSection.tsx`.)

### 2.1 Collapsible sections

Every section on this page becomes collapsible via a hide/show icon —
Profile Header, Experience, Education, Certifications, Career Goals,
Highlights, Achievements, Recommendations all get this treatment
consistently.

### 2.2 Alternating card background colors

Within any section that renders multiple cards/items (Experience list,
Education list, etc.), alternate cards use **two alternating light
background shades** instead of the current all-white. Pick two subtle,
close-in-value light shades (not two starkly different colors) so it
reads as gentle zebra striping, not a jarring pattern.

### 2.3 Date styling — bold, light blue

Date ranges are currently displayed light gray, normal font weight
(via `frontend/src/lib/date-format.ts`'s `dd-mmm-yyyy` formatting, used
across every section that shows a date). Change to: **bold**, **same
font size** (don't change size, only weight/color), **light blue**
color. Apply this consistently everywhere a date is shown across every
section — Experience, Education, Certifications, Career Goals,
Highlights, Achievements — not just Professional Experience.

### 2.4 Sticky profile photo/headline, page-level

The profile picture + headline text at the top of `ProfileHeader.tsx`
currently scrolls away with the rest of the page. Make this portion
**stay pinned/visible at all times** at the top of the center panel —
this is a second, page-level sticky element, distinct from the global
fixed Header from Part 1.1 (both are fixed simultaneously: global
Header at the very top, then this pinned photo/headline area just below
it, within the Career Profile page specifically).

A divider line separates this pinned area from the rest of the page.
Everything from **Executive Summary onward** (Core Competencies,
Experience, Education, Certifications, Career Goals, Highlights,
Achievements, Recommendations) scrolls normally beneath that divider.

### 2.5 Right Nav lower section: target roles widget

For the Career Profile page specifically, the Right Nav's lower/
contextual section (from Part 1.4) becomes: a widget where the user
enters **up to 5** current/future target roles they're preparing for.

**Future scope, explicitly not this round**: items across the center
panel's sections (Experience, Education, Certifications, Highlights,
Achievements, etc.) will eventually be taggable against these target
roles, so the system can generate role-specific output later (e.g., a
tailored view/export for a specific target role). Don't build the
tagging system now — just the up-to-5-roles entry widget. If it's easy
to shape the data model so tagging can be added later without a
rewrite, that's worth doing; don't over-engineer it otherwise.

---

## Open / deferred items (for visibility, not action this round)

- AI Chat: real AI backend wiring — later (Phase 4/8 territory)
- AI Chat: conversation retention period — undecided, needs a policy
  decision later
- Right Nav lower section design for pages other than Career Profile —
  deferred
- Role-tagging of Career Profile items against target roles — future
  scope, not this round
- Quote of the day: external API now, custom/owned source later
