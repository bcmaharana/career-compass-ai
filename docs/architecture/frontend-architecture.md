# Frontend Architecture — Career Compass AI

> Phase 0.2 status: scaffold implemented — see `frontend/` for the real, buildable project. Feature routes/pages beyond the placeholder dashboard and login screen arrive with their owning phases (Phase 1 auth, Phase 2 career profile, etc.).

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
│   ├── skill-intelligence/
│   ├── opportunity-intelligence/
│   ├── learning-intelligence/
│   └── ai-coach/
├── routes/         # route definitions, layout shells
├── stores/         # Zustand stores
├── api/            # generated client from backend OpenAPI schema + TanStack Query hooks
└── styles/         # Tailwind config, design tokens
```

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
