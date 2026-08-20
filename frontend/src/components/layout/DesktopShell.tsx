import { AppFooter } from "@/components/layout/AppFooter";
import { AppHeader } from "@/components/layout/AppHeader";
import { ChatThread } from "@/components/layout/ChatThread";
import { RightNav } from "@/components/layout/RightNav";
import { Tooltip } from "@/components/ui/tooltip";
import { formatLastLogin } from "@/lib/format-last-login";
import { NAV_ITEMS, matchNavItem } from "@/lib/nav-items";
import { cn } from "@/lib/utils";
import { useAuthStore } from "@/stores/auth-store";
import { ChevronDown, ChevronRight, Clock, Compass, Menu } from "lucide-react";
import { useEffect, useState } from "react";
import type { CSSProperties, RefObject } from "react";
import { Link, NavLink, Outlet, useLocation } from "react-router-dom";

/** Matches Tailwind's `lg` breakpoint (1024px) — kept as a plain media
 * query rather than a Tailwind class because Left Nav's collapsed state
 * is no longer purely CSS-driven (see leftNavCollapsed below): it also
 * responds to a manual toggle, so JS needs to know when a resize has
 * crossed the same threshold Tailwind's `lg:` classes use elsewhere in
 * this shell (Right Nav, AppHeader's avatar trigger). */
const NARROW_QUERY = "(max-width: 1023px)";

function getIsNarrow(): boolean {
  return typeof window !== "undefined" && window.matchMedia(NARROW_QUERY).matches;
}

/** Shared by Left Nav and Right Nav: starts collapsed below `lg` and at
 * `alwaysCollapsedWhenWide ? true : false` at/above it, then stays free
 * to be toggled manually — but crossing the breakpoint in either
 * direction always resets back to that default, discarding whatever was
 * manually chosen. Each rail gets its own independent instance/state.
 * Right Nav passes `alwaysCollapsedWhenWide: true` (2026-08-09, explicit
 * request) so it starts thin regardless of viewport width, expandable
 * only via its own ☰ toggle — Left Nav keeps the original width-only
 * default (collapsed below `lg`, expanded at/above it). */
function useNarrowDefaultCollapse(
  alwaysCollapsedWhenWide = false,
): [boolean, (collapsed: boolean) => void] {
  const [collapsed, setCollapsed] = useState(() => alwaysCollapsedWhenWide || getIsNarrow());

  useEffect(() => {
    const mediaQueryList = window.matchMedia(NARROW_QUERY);
    function handleChange(event: MediaQueryListEvent) {
      setCollapsed(alwaysCollapsedWhenWide || event.matches);
    }
    mediaQueryList.addEventListener("change", handleChange);
    return () => mediaQueryList.removeEventListener("change", handleChange);
  }, [alwaysCollapsedWhenWide]);

  return [collapsed, setCollapsed];
}

interface DesktopShellProps {
  mainRef: RefObject<HTMLElement>;
  onLogout: () => void;
}

/**
 * Desktop/tablet app shell (>= `md`, see AppShell.tsx's useIsMobileShell):
 * four fixed regions (Left Nav, Header, Footer, Right Nav) around one
 * independently scrollable center panel.
 *
 * All four fixed regions use `position: fixed` against the viewport
 * (not `sticky`) so none of them can ever be scrolled or pushed off —
 * sizing them is handled entirely by the `--shell-*` CSS variables in
 * globals.css, which the center `<main>` also reads for its inset, so
 * the fixed regions and the scrollable area can't drift out of sync.
 * The wrapping div below carries no layout of its own (`display: contents`)
 * — it exists only to define --current-left-nav-w/--current-right-nav-w
 * for AppHeader/AppFooter/RightNav/`<main>`'s CSS var references, since
 * this state is otherwise local to this component. The Footer is the one
 * region whose actual height isn't a fixed `--shell-*` token — its
 * composer textarea can grow (ChatComposerForm.tsx), so `<main>` reads
 * `--current-footer-h` instead (AppFooter.tsx publishes it via a
 * ResizeObserver, with `--shell-footer-h` as the CSS fallback for the
 * instant before that observer's first measurement lands).
 */
export function DesktopShell({ mainRef, onLogout }: DesktopShellProps) {
  const location = useLocation();
  const user = useAuthStore((state) => state.user);
  const activeNavItem = matchNavItem(location.pathname);

  // A persistent width toggle, not a drawer — neither rail ever covers
  // content, each just occupies either its full --shell-*-nav-w (with
  // labels) or the shared --shell-icon-nav-w icon-only width. The toggle
  // button that flips each one lives in that rail's own top box, visible
  // at every screen width, per explicit product direction: users can
  // reclaim center-panel width on a wide screen too, not only on a narrow
  // one. See useNarrowDefaultCollapse's docstring for the width-based
  // default / manual-override rules, which are identical for both rails
  // but tracked independently.
  const [leftNavCollapsed, setLeftNavCollapsed] = useNarrowDefaultCollapse();
  const [rightNavCollapsed, setRightNavCollapsed] = useNarrowDefaultCollapse(true);

  function toggleLeftNav() {
    setLeftNavCollapsed(!leftNavCollapsed);
  }
  function toggleRightNav() {
    setRightNavCollapsed(!rightNavCollapsed);
  }

  // Which top-level items with children (e.g. Learning Intelligence,
  // holding Interview Prep) currently show their nested pages —
  // collapsed by default, matching every other collapsible affordance
  // in this app. Driven by the current route on every navigation: a
  // branch auto-expands the moment its parent or a child becomes the
  // active page (so landing directly on /interview-prep — a bookmark, a
  // link from elsewhere — doesn't leave it hidden inside a collapsed
  // branch), and just as importantly auto-*collapses* the moment the
  // active page leaves that branch for anything else, even if it was
  // manually toggled open — clicking any other Left Nav item always
  // closes it back up.
  const [expandedBranches, setExpandedBranches] = useState<Set<string>>(new Set());
  useEffect(() => {
    const activeTo = matchNavItem(location.pathname).to;
    setExpandedBranches((prev) => {
      const next = new Set(prev);
      let changed = false;
      for (const item of NAV_ITEMS) {
        if (!item.children) continue;
        const isActiveBranch =
          activeTo === item.to || item.children.some((child) => child.to === activeTo);
        if (isActiveBranch && !next.has(item.to)) {
          next.add(item.to);
          changed = true;
        } else if (!isActiveBranch && next.has(item.to)) {
          next.delete(item.to);
          changed = true;
        }
      }
      return changed ? next : prev;
    });
  }, [location.pathname]);

  function toggleBranch(to: string) {
    setExpandedBranches((prev) => {
      const next = new Set(prev);
      if (next.has(to)) next.delete(to);
      else next.add(to);
      return next;
    });
  }

  // Both rails' actual current widths — the single source every fixed
  // region below reads via var(--current-left-nav-w)/
  // var(--current-right-nav-w), same "one variable, nothing can drift"
  // principle the --shell-* tokens already use, just JS-driven here
  // since these also depend on manual toggle state, not only the
  // viewport. --shell-icon-nav-w is defined once in globals.css
  // alongside the other --shell-* tokens, shared by both rails.
  const navWidthStyle = {
    "--current-left-nav-w": leftNavCollapsed
      ? "var(--shell-icon-nav-w)"
      : "var(--shell-left-nav-w)",
    "--current-right-nav-w": rightNavCollapsed
      ? "var(--shell-icon-nav-w)"
      : "var(--shell-right-nav-w)",
  } as CSSProperties;

  return (
    <div style={navWidthStyle} className="contents">
      <aside className="fixed inset-y-0 left-0 z-20 flex w-[var(--current-left-nav-w)] flex-col rainbow-border-r bg-primary text-primary-foreground transition-[width] duration-200 ease-out">
        <div
          className={cn(
            // No longer --shell-side-footer-h: that height was sized for
            // a single row, and this box is now two stacked rows (logo
            // above ☰, both always visible — text only added when
            // expanded) — so it sizes to its own content instead of
            // sharing the token Left Nav's bottom box and Right Nav's
            // two end boxes still use. Logo-then-☰ (not the reverse) so
            // this box's height is driven by the same icon-plus-icon
            // rhythm Right Nav's swapped header now matches (gap-1
            // between the two, deliberately tight).
            "flex flex-col gap-1 bg-[hsl(var(--primary-light))] px-3 py-3",
            leftNavCollapsed ? "items-center" : "items-start",
          )}
        >
          <Link to="/dashboard" className="flex min-w-0 items-center gap-2">
            <Compass
              className="h-7 w-7 shrink-0"
              strokeWidth={2}
              color="url(#rainbow-accent-gradient)"
            />
            {!leftNavCollapsed && (
              <span
                className="inline-block whitespace-nowrap bg-[linear-gradient(90deg,#a855f7_12.5%,#3b82f6_37.5%,#22c55e_58.33%,#fdba74_75%,#fca5a5_91.67%)] bg-clip-text font-display text-xl font-semibold tracking-tight text-transparent"
              >
                Career Compass
              </span>
            )}
          </Link>

          <button
            type="button"
            onClick={toggleLeftNav}
            aria-label={leftNavCollapsed ? "Expand navigation" : "Collapse navigation"}
            aria-expanded={!leftNavCollapsed}
            title={leftNavCollapsed ? "Expand navigation" : "Collapse navigation"}
            className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md text-primary-foreground/80 hover:bg-white/10 hover:text-primary-foreground"
          >
            <Menu className="h-5 w-5" />
          </button>
        </div>

        <div className="h-px bg-[linear-gradient(90deg,#a855f7_12.5%,#3b82f6_37.5%,#22c55e_58.33%,#fdba74_75%,#fca5a5_91.67%)]" />

        <nav className="mt-4 flex flex-1 flex-col gap-1 overflow-y-auto px-3">
          {NAV_ITEMS.map(({ to, label, icon: Icon, end, children }) => {
            const link = (
              <NavLink
                to={to}
                end={end}
                aria-label={label}
                className={({ isActive }) =>
                  cn(
                    "flex w-full items-center gap-3 rounded-md px-3 py-2 text-xs font-medium transition-colors",
                    leftNavCollapsed && "justify-center px-0",
                    isActive
                      ? "bg-[linear-gradient(90deg,#a855f7_12.5%,#3b82f6_37.5%,#22c55e_58.33%,#fdba74_75%,#fca5a5_91.67%)] text-primary"
                      : "text-primary-foreground/80 hover:bg-white/5 hover:text-primary-foreground",
                  )
                }
              >
                <Icon className="h-4 w-4 shrink-0" />
                {!leftNavCollapsed && label}
              </NavLink>
            );

            // No nested pages, or the rail is collapsed to icon-only
            // (no room for a tree affordance, same reason labels are
            // already hidden then) — render exactly as a plain item.
            if (!children || leftNavCollapsed) {
              if (!leftNavCollapsed) return <div key={to}>{link}</div>;
              return (
                <Tooltip key={to} content={label} placement="right" className="flex w-full">
                  {link}
                </Tooltip>
              );
            }

            const isExpanded = expandedBranches.has(to);
            return (
              <div key={to} className="flex flex-col gap-1">
                <div className="flex items-center gap-1">
                  <div className="min-w-0 flex-1">{link}</div>
                  <button
                    type="button"
                    onClick={() => toggleBranch(to)}
                    aria-label={isExpanded ? `Collapse ${label}` : `Expand ${label}`}
                    aria-expanded={isExpanded}
                    className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md text-primary-foreground/60 hover:bg-white/5 hover:text-primary-foreground"
                  >
                    {isExpanded ? (
                      <ChevronDown className="h-4 w-4" />
                    ) : (
                      <ChevronRight className="h-4 w-4" />
                    )}
                  </button>
                </div>
                {isExpanded && (
                  <div className="ml-4 flex flex-col gap-1 border-l border-white/10 pl-2">
                    {children.map((child) => (
                      <NavLink
                        key={child.to}
                        to={child.to}
                        end={child.end}
                        aria-label={child.label}
                        className={({ isActive }) =>
                          cn(
                            "flex w-full items-center gap-3 rounded-md px-3 py-2 text-xs font-medium transition-colors",
                            isActive
                              ? "bg-[linear-gradient(90deg,#a855f7_12.5%,#3b82f6_37.5%,#22c55e_58.33%,#fdba74_75%,#fca5a5_91.67%)] text-primary"
                              : "text-primary-foreground/80 hover:bg-white/5 hover:text-primary-foreground",
                          )
                        }
                      >
                        <child.icon className="h-4 w-4 shrink-0" />
                        {child.label}
                      </NavLink>
                    ))}
                  </div>
                )}
              </div>
            );
          })}
        </nav>

        {leftNavCollapsed ? (
          <div className="relative mt-auto flex min-h-[var(--shell-icon-endbox-h)] flex-col items-center justify-center rainbow-border-t bg-[hsl(var(--primary-light))] px-3 py-2">
            <Tooltip
              content={
                user?.lastLoginAt
                  ? formatLastLogin(user.lastLoginAt)
                  : "Welcome — this is your first login."
              }
              placement="right"
            >
              <button
                type="button"
                aria-label="Last login time"
                className="flex h-12 w-12 items-center justify-center rounded-md text-primary-foreground/70 hover:bg-white/10 hover:text-primary-foreground"
              >
                <Clock className="h-6 w-6" />
              </button>
            </Tooltip>
          </div>
        ) : (
          <div className="relative mt-auto flex h-[var(--shell-side-footer-h)] shrink-0 flex-col justify-center rainbow-border-t bg-[hsl(var(--primary-light))] px-3 py-2">
            <p className="px-3 text-sm leading-snug text-primary-foreground/70">
              {user?.lastLoginAt
                ? formatLastLogin(user.lastLoginAt)
                : "Welcome — this is your first login."}
            </p>
          </div>
        )}
      </aside>

      <AppHeader />
      <AppFooter />
      <RightNav onLogout={onLogout} isCollapsed={rightNavCollapsed} onToggle={toggleRightNav} />

      <main
        ref={mainRef}
        className="fixed bottom-[var(--current-footer-h,var(--shell-footer-h))] left-[var(--current-left-nav-w)] right-[var(--current-right-nav-w)] top-[var(--shell-header-h)] overflow-y-auto scrollbar-hide bg-[hsl(var(--center-bg))] transition-[left,right] duration-200 ease-out"
      >
        <div className="container py-6 md:py-8">
          <Outlet />
          {/* CoachPage renders the thread itself (a richer, labeled
              layout) — rendering the generic compact ChatThread too
              would show the same messages array twice. */}
          {activeNavItem.to !== "/coach" && <ChatThread />}
        </div>
      </main>
    </div>
  );
}
