import { Compass } from "lucide-react";
import { Link } from "react-router-dom";

/**
 * Minimal, brand-only header for the anonymous public-sharing pages
 * (PublicShowcasePage/PublicArticlePage) — no app chrome/nav, since a
 * visitor here has no session and isn't meant to see any of it. Own
 * gradient `<defs>` (CLAUDE.md's rainbow-accent convention: one per
 * independently-rendered React tree) — safe as a single fixed id here
 * since these two pages are mutually exclusive routes, never mounted
 * at the same time.
 */
export function PublicPageHeader() {
  return (
    <header className="flex items-center border-b border-border bg-primary px-6 py-4 shadow-card sm:px-10">
      <svg width="0" height="0" className="absolute" aria-hidden="true">
        <defs>
          <linearGradient id="public-page-rainbow-gradient" x1="0%" y1="0%" x2="100%" y2="0%">
            <stop offset="12.5%" stopColor="#a855f7" />
            <stop offset="37.5%" stopColor="#3b82f6" />
            <stop offset="58.33%" stopColor="#22c55e" />
            <stop offset="75%" stopColor="#fdba74" />
            <stop offset="91.67%" stopColor="#fca5a5" />
          </linearGradient>
        </defs>
      </svg>
      <Link to="/" className="flex items-center gap-2">
        <Compass className="h-6 w-6" strokeWidth={2} color="url(#public-page-rainbow-gradient)" />
        <span className="font-display text-lg font-semibold text-primary-foreground">
          Career Compass AI
        </span>
      </Link>
    </header>
  );
}
