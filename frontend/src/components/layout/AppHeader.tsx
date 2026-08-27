import { useCareerProfile } from "@/api/queries/career-profile";
import { useQuoteOfTheDay } from "@/api/queries/quotes";
import { MobileAccountMenu } from "@/components/layout/MobileAccountMenu";
import { MobileNavMenu } from "@/components/layout/MobileNavMenu";
import { ProfileIconMenu } from "@/components/layout/ProfileIconMenu";
import { Breadcrumb } from "@/components/ui/breadcrumb";
import { getBreadcrumbTrail, matchNavItem } from "@/lib/nav-items";
import { Compass } from "lucide-react";
import { Link, useLocation } from "react-router-dom";

interface AppHeaderProps {
  /** Logs the user out — threaded down to MobileAccountMenu's embedded
   * Sign out button. MobileShell.tsx passes this — which is also what
   * this component uses to decide it's in the mobile shell at all,
   * rendering the left/right icon-stack columns below only when set.
   * DesktopShell.tsx doesn't pass it, so those columns never render
   * there. */
  onLogout?: () => void;
}

/**
 * Fixed top region of the app shell (brief Part 1.3): page name, a short
 * purpose line, and a quote of the day — contextual per route via
 * matchNavItem, the same matching AppShell uses to decide when to clear
 * the chat thread. Shared by both DesktopShell and MobileShell rather than
 * forked. Height is --shell-header-h on desktop; mobile uses the shorter
 * --shell-mobile-header-h instead (smaller title/purpose text and a
 * tighter icon-stack gap mean the content genuinely needs less room —
 * MobileNavMenu.tsx/MobileAccountMenu.tsx anchor their dropdowns off the
 * same mobile token so they stay flush against whichever height is
 * actually in effect).
 *
 * Mobile adds two bordered icon-stack columns flanking the title/purpose
 * block — a condensed version of the desktop rails' own top boxes (logo
 * above ☰ on Left Nav, photo above ☰ on Right Nav), since those rails
 * don't exist in the mobile shell at all: left is the bare Compass icon,
 * no wordmark — there's no room for it once the icon-stack columns exist
 * on both sides, unlike Left Nav's own expanded state (links to
 * /dashboard, matching Left Nav's logo) above MobileNavMenu's hamburger
 * (opens the nav dropdown, replacing what was a fixed bottom tab bar — a
 * tab bar has a hard width budget the nav list was expected to outgrow);
 * right is the profile photo (opens a small Career Profile/Sign Out menu
 * via ProfileIconMenu, matching Right Nav's own photo — 2026-08-21,
 * direct request that Sign Out be reachable from the profile icon itself
 * everywhere, not only through Settings/the hamburger) above
 * MobileAccountMenu's hamburger (opens a matching compact
 * dropdown — the account panel used to be a full-height right-edge
 * drawer, changed to mirror the left dropdown's interaction pattern after
 * live feedback). Both icons and both hamburgers share the exact same
 * `h-7 w-7` box / `h-4 w-4` glyph sizing so the icon-above-hamburger pair
 * in each column lines up on a shared left edge and center line, rather
 * than each row sizing itself independently. Desktop has no need for
 * either column — its rails already show all of this — so both are gated
 * on `onLogout` being provided.
 *
 * Two rows within the title/purpose column, not three: the quote sits
 * right-aligned next to the title on the first row rather than stacked
 * below it, so the header fits in --shell-header-h at the same height as
 * the footer (--shell-footer-h) — three stacked lines didn't fit in that
 * shorter box. The quote itself is desktop-only (`hidden md:block`) —
 * no room for it on a narrow header once the icon-stack columns are there
 * too.
 *
 * The quote comes from GET /api/v1/quote-of-the-day, which itself wraps
 * an external quotes API behind a small backend adapter (see
 * backend/app/adapters/quotes/) — done server-side rather than fetched
 * directly from here because the chosen provider doesn't return CORS
 * headers for browser calls, confirmed by hand before choosing this
 * shape. This component stays ignorant of which provider is in play.
 *
 * On the desktop shell, both insets always track each rail's actual
 * current width via var(--current-left-nav-w)/var(--current-right-nav-w)
 * (set on the shell wrapper in AppShell.tsx) — neither rail is ever fully
 * hidden there, so this header needs no `lg:` breakpoint of its own for
 * that: it just always spans the gap between whatever the two rails
 * currently measure. MobileShell sets both vars to 0 instead (no rails).
 */
export function AppHeader({ onLogout }: AppHeaderProps) {
  const location = useLocation();
  const { label, purpose } = matchNavItem(location.pathname);
  const breadcrumbTrail = getBreadcrumbTrail(location.pathname);
  const { data: quote } = useQuoteOfTheDay();
  const { data: profile } = useCareerProfile();
  const isMobile = Boolean(onLogout);

  return (
    <header
      className="fixed left-[var(--current-left-nav-w)] right-[var(--current-right-nav-w)] top-0 z-10 flex h-[var(--shell-mobile-header-h)] items-stretch gap-3 rainbow-border-b bg-[linear-gradient(to_top,#2A4382,#18284E)] px-3 transition-[left,right] duration-200 ease-out md:h-[var(--shell-header-h)] md:px-6"
      aria-label="Page header"
    >
      {isMobile && (
        <div className="flex shrink-0 flex-col justify-center gap-px border-r border-white/15 pr-3 md:hidden">
          <Link
            to="/dashboard"
            aria-label="Dashboard"
            className="flex h-7 w-7 items-center justify-center rounded-md hover:bg-white/10"
          >
            <Compass
              className="h-4 w-4 shrink-0"
              strokeWidth={2}
              color="url(#rainbow-accent-gradient)"
            />
          </Link>
          <MobileNavMenu />
        </div>
      )}

      <div className="flex min-w-0 flex-1 flex-col justify-center gap-0.5">
        <Breadcrumb segments={breadcrumbTrail} variant="dark" className="hidden md:flex" />
        <div className="flex items-baseline justify-between gap-4">
          <h1 className="truncate bg-[linear-gradient(90deg,#c084fc_12.5%,#60a5fa_37.5%,#4ade80_58.33%,#fb923c_75%,#e08585_91.67%)] bg-clip-text font-display text-lg font-semibold leading-tight text-transparent md:text-2xl">
            {label}
          </h1>
          {quote && (
            <p className="hidden min-w-0 shrink truncate text-right text-xs font-bold italic text-white md:block">
              "{quote.content}"{quote.author ? ` — ${quote.author}` : ""}
            </p>
          )}
        </div>
        <p className="truncate text-xs text-primary-foreground/80 md:text-base">{purpose}</p>
      </div>

      {isMobile && onLogout && (
        <div className="flex shrink-0 flex-col items-center justify-center gap-px border-l border-white/15 pl-3 md:hidden">
          <ProfileIconMenu
            photoUrl={profile?.photo_url}
            onLogout={onLogout}
            triggerClassName="flex h-7 w-7 items-center justify-center rounded-md hover:bg-white/10"
            iconClassName="h-4 w-4"
          />
          <MobileAccountMenu />
        </div>
      )}
    </header>
  );
}
