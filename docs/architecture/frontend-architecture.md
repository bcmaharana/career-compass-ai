# Frontend Architecture — Career Compass AI

> Current status: the React application is implemented as feature modules under `frontend/src/features/`, with authenticated editing flows and public read-only pages. The initial Phase 0.2 scaffold description is obsolete.

## Stack

- **React 18 + TypeScript** — component model and type safety
- **Vite** — dev server and build tooling
- **Tailwind CSS** — utility-first styling
- **shadcn/ui** — accessible, unstyled-by-default component primitives customized to the Career Compass design system, rather than a heavy pre-styled component framework
- **React Router** — routing
- **TanStack Query** — server state (caching, refetching, mutations) — matched to the backend's REST/OpenAPI shape
- **Zustand** — local/client UI state (e.g., sidebar collapsed, active tenant context) — deliberately separate from server state to avoid the two caches fighting each other

## Directory Shape

```
frontend/src/
├── components/     # design-system primitives (Button, Card, Input, etc. — shadcn-based)
├── features/       # one folder per business domain, mirrors backend modules
│   ├── career-profile/
│   ├── interview-prep/
│   ├── diagram/
│   ├── public-sharing/
│   ├── skill-intelligence/
│   ├── opportunity-intelligence/
│   ├── learning-intelligence/
│   └── coach/
├── routes/         # route definitions, layout shells
├── stores/         # Zustand stores
├── api/            # generated client from backend OpenAPI schema + TanStack Query hooks
└── styles/         # Tailwind config, design tokens
```

## Rich-text and diagram content

Career Compass AI's diagram editor lives in
`features/diagram/DiagramCanvas.tsx` and is lazy-loaded through
`LazyDiagramCanvas.tsx`. It is a product feature, not currently part of
the separately published `@bcmaharana/ui-kit`. The editor represents a
diagram as structured versioned data (shapes, manual lines, and
connectors), rather than storing generated SVG or HTML. It is integrated
into Interview Prep, Career Profile showcase editing, and public
read-only sharing views. Manual line endpoints can snap to a shape
outline and persist an anchor, so attached endpoints follow a shape when
it moves, resizes, or rotates. Backend payload validation for this data
lives in `backend/app/api/v1/diagram_schemas.py`. The scene uses a wider
1600-unit coordinate space, scales to the available viewport, and derives
height from its contents. Manually drawn lines become orthogonal when
their endpoints sit at different vertical positions. Shape labels retain
plain text for accessibility plus sanitized rich-text HTML for inline
formatting; the server applies the shared rich-text sanitizer before it
accepts the diagram payload.

The shared `@bcmaharana/ui-kit` rich-text toolbar supports removing an
active list and stores per-item bullet marker styles on `<li>` elements.
Career Compass AI's server sanitizer must allow the `style` attribute on
`li` as well as on the list container, or square and hollow-circle markers
are lost when the content is saved.

Read-only rich-text fields use the shared `RichTextDisplay`, which keeps
explicit links and converts bare HTTP(S) URLs in text into safe, clickable
links. Diagram shape labels are rendered on a separate canvas overlay, so
that path applies the same URL conversion and enables link pointer events
only in read-only diagrams; editor overlays remain non-interactive.

The shape text editor opens in a fixed page-level overlay rather than
inside the clipped canvas. It stays positioned by the edited shape and
repositions on scroll and viewport resize, moving above the shape when
there is not enough room below it.

The diagram canvas frame is shown only in edit mode. Read-only article and
showcase views render the diagram without an editor border.
Read-only diagrams fit the available viewport width by default and keep the
1600-unit scene's aspect ratio, so the complete drawing is visible without
horizontal scrolling at the default zoom. Zoom controls provide 50%–200%
scaling for inspecting labels and details; zoomed scenes scroll horizontally
inside the viewport. Mobile users see the whole diagram first and can zoom
when they need more text detail.
Inline pixel/point font sizes in shape rich text are scaled with the scene
too, so formatted words do not remain at desktop size and get clipped inside
their smaller mobile shapes.

Public article and showcase pages use the available mobile width with 8px
outer gutters; on desktop, their main content is centered at 90% viewport
width. Public content cards reduce their default 24px horizontal inset to
12px on phones and 16px at wider breakpoints, preventing page and card
padding from compounding into a narrow reading area.

In the diagram editor, dragging on empty canvas space draws a marquee
that selects shapes, manual lines/arrows, and attached connectors whose
rendered bounds cross the selection. Shift-click adds/removes individual
objects from the selection. Shape members move and transform together;
Copy/Paste duplicates mixed selections with their relative positions
preserved and reconnects copied lines/edges to copied shapes. Delete
removes all selected objects and detaches any remaining line endpoints
from deleted shapes. Lines and connectors have wide transparent hit
strokes so their visible strokes and arrowheads are easier to select.

## Design System

| Token | Value | Use |
|---|---|---|
| Primary | `#182F5E` (deep navy) | Sidebar surface, primary buttons, headings on light backgrounds |
| Accent | `#14766B` (muted teal) | AI-related features, active nav indicator, progress, badges |
| Background | `#F4F6F9` (cool light gray) | Page background |
| Surface | `#FFFFFF` | Cards, panels — subtle shadow (`shadow-card`), no heavy borders |
| Destructive | standard red | Errors, destructive actions only |

Implemented as HSL CSS variables in `src/styles/globals.css`, consumed via Tailwind's `tailwind.config.ts` color extensions (`bg-primary`, `text-accent`, etc.) — never hard-coded hex values in component files.

**Typography:** Sora (display/headings) + Inter (body) + IBM Plex Mono (data, timestamps, code-like values). This pairing was chosen deliberately over defaulting to Inter-everywhere or the increasingly common Space-Grotesk-for-every-AI-product look — Sora gives headings a confident, slightly geometric character that reads as "modern, AI-enabled" without leaning on a cliché, while Inter keeps body copy maximally legible for data-dense enterprise screens.

Style direction: professional, modern, trustworthy, and visibly "AI-enabled" without leaning on cliché sci-fi visual tropes (no glowing neon gradients) — the AI feels like a competent colleague, not a novelty.

## API Client

Generated from the backend's OpenAPI schema (FastAPI serves this at `/openapi.json` automatically) using `openapi-typescript` + a thin TanStack Query wrapper, so the frontend's request/response types can never silently drift from the backend contract — a schema change that breaks the frontend fails at generation/build time, not at runtime.

## Error Handling

The backend's consistent JSON error shape (see `security-architecture.md` / `backend-architecture.md`) is mapped to a single frontend error boundary + toast pattern, so every feature module gets consistent error UX without reimplementing it.

## Authentication Placeholder

Phase 0.2 ships a login screen wired against the Phase 1 internal JWT endpoints, with the token storage/refresh logic isolated behind a single `auth` module — so swapping in SSO/OIDC later touches one module, not every feature.
