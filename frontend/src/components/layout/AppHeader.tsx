import { useQuoteOfTheDay } from "@/api/queries/quotes";
import { matchNavItem } from "@/lib/nav-items";
import { useLocation } from "react-router-dom";

/**
 * Fixed top region of the app shell (brief Part 1.3): page name, a short
 * purpose line, and a quote of the day — contextual per route via
 * matchNavItem, the same matching AppShell uses to decide when to clear
 * the chat thread.
 *
 * Two rows, not three: the quote sits right-aligned next to the title on
 * the first row rather than stacked below it, so the header fits in
 * --shell-header-h at the same height as the footer (--shell-footer-h) —
 * three stacked lines didn't fit in that shorter box.
 *
 * The quote comes from GET /api/v1/quote-of-the-day, which itself wraps
 * an external quotes API behind a small backend adapter (see
 * backend/app/adapters/quotes/) — done server-side rather than fetched
 * directly from here because the chosen provider doesn't return CORS
 * headers for browser calls, confirmed by hand before choosing this
 * shape. This component stays ignorant of which provider is in play.
 *
 * Both insets always track each rail's actual current width via
 * var(--current-left-nav-w)/var(--current-right-nav-w) (set on the
 * shell wrapper in AppShell.tsx) — neither rail is ever fully hidden
 * anymore (both toggle between full and icon-only width, via a button
 * that lives in each rail's own top box, not here), so this header
 * needs no `lg:` breakpoint at all: it just always spans the gap
 * between whatever the two rails currently measure.
 */
export function AppHeader() {
  const location = useLocation();
  const { label, purpose } = matchNavItem(location.pathname);
  const { data: quote } = useQuoteOfTheDay();

  return (
    <header
      className="fixed left-[var(--current-left-nav-w)] right-[var(--current-right-nav-w)] top-0 z-10 flex h-[var(--shell-header-h)] flex-col justify-center gap-0.5 border-b border-gray-700 bg-[linear-gradient(90deg,#a855f7_12.5%,#3b82f6_37.5%,#22c55e_58.33%,#fdba74_75%,#fca5a5_91.67%)] px-6 transition-[left,right] duration-200 ease-out"
      aria-label="Page header"
    >
      <div className="flex items-baseline justify-between gap-4">
        <h1 className="truncate font-display text-2xl font-semibold leading-tight">{label}</h1>
        {quote && (
          <p className="min-w-0 shrink truncate text-right text-xs font-bold italic text-accent">
            "{quote.content}"{quote.author ? ` — ${quote.author}` : ""}
          </p>
        )}
      </div>
      <p className="truncate text-base text-[hsl(var(--header-purpose-text))]">{purpose}</p>
    </header>
  );
}
