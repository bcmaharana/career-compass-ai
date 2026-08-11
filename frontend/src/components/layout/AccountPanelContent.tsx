import { useCareerProfile } from "@/api/queries/career-profile";
import { Tooltip } from "@/components/ui/tooltip";
import { TargetRolesWidget } from "@/features/career-profile/TargetRolesWidget";
import { formatDisplayDate } from "@/lib/date-format";
import { SETTINGS_NAV_ITEMS, isSettingsRoute, matchNavItem } from "@/lib/nav-items";
import { cn } from "@/lib/utils";
import { useAuthStore } from "@/stores/auth-store";
import { Crosshair, LogOut, Settings, UserCircle } from "lucide-react";
import { useEffect, useState } from "react";
import type { ReactNode } from "react";
import { Link, NavLink, useLocation } from "react-router-dom";

function pad(value: number): string {
  return String(value).padStart(2, "0");
}

/** Time-of-day greeting, recomputed on every render — since it's driven
 * by useLocalClock's ticking `now`, it flips over live as the viewer
 * crosses a boundary hour without needing a page refresh. */
function getGreeting(date: Date): string {
  const hour = date.getHours();
  if (hour < 12) return "Good morning";
  if (hour < 17) return "Good afternoon";
  return "Good evening";
}

/** Local (not UTC) date, ticking over at local midnight — a fixed
 * "current date" widget should track the viewer's own clock, and
 * `Date#toISOString` would report UTC, silently off by a day near
 * midnight for anyone not in UTC+0. */
function useLocalClock(): Date {
  const [now, setNow] = useState(() => new Date());
  useEffect(() => {
    const id = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(id);
  }, []);
  return now;
}

interface AccountPanelContentProps {
  /** Required in practice whenever `showSettingsAndSignOut` is true (the
   * only case the Sign out button actually renders) — typed optional
   * since MobileAccountMenu.tsx, which always passes
   * `showSettingsAndSignOut={false}`, has no need to supply one at all. */
  onLogout?: () => void;
  /** Icon-only rendering (rail collapsed to --shell-icon-nav-w) vs. full
   * labels/text. The mobile drawer (MobileAccountDrawer.tsx) always
   * passes `false` — a drawer has no icon-only state of its own. */
  isCollapsed: boolean;
  /** The ☰ width-toggle button — rail-only chrome (RightNav.tsx), not
   * rendered at all when omitted (the drawer has nothing to toggle). */
  toggleButton?: ReactNode;
  /** Rail-only: expands the rail when the collapsed Target Roles icon is
   * tapped (mirrors the ☰ toggle). Unused/omitted in the drawer, which is
   * never collapsed. */
  onToggle?: () => void;
  /** Drawer-only: fired by every navigational element (profile photo/name,
   * Settings sub-nav items, the Settings link) so MobileAccountDrawer can
   * close itself on navigation — a link changing the route out from under
   * an open drawer would otherwise leave the drawer's backdrop covering
   * the new page, since navigating doesn't touch the drawer's own open
   * state. The rail has no such state to close, so RightNav omits this. */
  onNavigate?: () => void;
  /** The bottom Settings-link/Sign-out-button box. Defaults to shown
   * (RightNav's desktop rail, which has no other home for either action).
   * MobileAccountMenu.tsx passes `false` — mobile moved both into
   * AppFooter.tsx's own icon columns instead, so showing them here too
   * would just be the same two actions in two places. */
  showSettingsAndSignOut?: boolean;
}

/**
 * The identity/contextual/settings-signout body shared by Right Nav's
 * desktop rail (RightNav.tsx) and the mobile account drawer
 * (MobileAccountDrawer.tsx) — extracted so the ~200 lines of rainbow-
 * gradient markup below has exactly one copy instead of drifting between
 * a rail version and a drawer version. RightNav supplies its own `<nav>`
 * fixed-rail wrapper and `toggleButton`; the drawer wraps this in a
 * `Sheet` instead and passes no toggle button.
 *
 * Three sections: a top box (profile photo/identity, plus the optional
 * toggle button); a per-page contextual slot in the middle — the Career
 * Profile page's target-roles widget, the Settings sub-nav
 * (SETTINGS_NAV_ITEMS) under /settings/*, or nothing otherwise, all
 * matched by route via matchNavItem/isSettingsRoute; and Settings + Sign
 * out pinned to the bottom box.
 */
export function AccountPanelContent({
  onLogout,
  isCollapsed,
  toggleButton,
  onToggle,
  onNavigate,
  showSettingsAndSignOut = true,
}: AccountPanelContentProps) {
  const user = useAuthStore((state) => state.user);
  const { data: profile } = useCareerProfile();
  const [photoLoadFailed, setPhotoLoadFailed] = useState(false);
  const now = useLocalClock();
  const location = useLocation();
  const isCareerProfilePage = matchNavItem(location.pathname).to === "/profile";
  const inSettings = isSettingsRoute(location.pathname);

  const localIsoDate = `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`;
  const weekday = now.toLocaleDateString(undefined, { weekday: "long" });
  const formattedDate = `${weekday}, ${formatDisplayDate(localIsoDate)}`;
  const greeting = getGreeting(now);
  // Formal "Salutation Lastname, Firstname" (e.g. "Mr. Smith, John"),
  // not the backend's blended full_name/display_name (which reads
  // "Salutation Firstname Lastname") — this widget wants the
  // lastname-first form regardless of what full_name provides.
  const formalName =
    user?.firstName && user?.lastName
      ? `${user.salutation ? `${user.salutation} ` : ""}${user.lastName}, ${user.firstName}`
      : undefined;
  const displayName = formalName || user?.email || "—";
  const formattedTime = now.toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" });
  // Collapsed rail hides the greeting/name/email/date text block
  // entirely (see the `!isCollapsed` block below) — this mirrors that
  // same line-by-line breakdown (greeting, name, optional email, date)
  // into the profile photo's hover tooltip instead, plus a live clock
  // time folded onto the date line (that block has no separate time
  // display to mirror), so none of it is lost while collapsed.
  const collapsedIdentitySummary = (
    <>
      {greeting},
      <br />
      {displayName}
      {user?.fullName && user?.email && (
        <>
          <br />
          {user.email}
        </>
      )}
      <br />
      {formattedDate}, {formattedTime}
    </>
  );

  const activeGradientClasses =
    "bg-[linear-gradient(90deg,#a855f7_12.5%,#3b82f6_37.5%,#22c55e_58.33%,#fdba74_75%,#fca5a5_91.67%)] text-primary";
  const inactiveClasses =
    "text-primary-foreground/80 hover:bg-white/5 hover:text-primary-foreground";

  return (
    <>
      <div
        className={cn(
          // Two columns, not stacked rows like Left Nav's header:
          // profile icon + ☰ (when present) stacked vertically on the
          // left, greeting/name/email/date as a text block to their
          // right, top-aligned to the profile icon via this row's own
          // items-start — not centered, since a centered text block
          // would drift below the icon column's top edge once the icon
          // column is shorter than the text block.
          "flex gap-3 bg-[hsl(var(--primary-light))] px-3 py-3 text-primary-foreground",
          isCollapsed ? "justify-center" : "items-start",
        )}
      >
        <div className={cn("flex flex-col gap-1", isCollapsed ? "items-center" : "items-start")}>
          {isCollapsed ? (
            <Tooltip content={collapsedIdentitySummary} placement="left">
              <Link
                to="/profile"
                aria-label="Career Profile"
                onClick={onNavigate}
                className="hover:opacity-80"
              >
                {profile?.photo_url && !photoLoadFailed ? (
                  <img
                    src={profile.photo_url}
                    alt=""
                    className="h-9 w-9 shrink-0 rounded-full object-cover"
                    onError={() => setPhotoLoadFailed(true)}
                  />
                ) : (
                  <UserCircle
                    className="h-9 w-9 shrink-0 text-primary-foreground/70"
                    strokeWidth={1.5}
                  />
                )}
              </Link>
            </Tooltip>
          ) : (
            <Link
              to="/profile"
              aria-label="Career Profile"
              onClick={onNavigate}
              className="hover:opacity-80"
            >
              {profile?.photo_url && !photoLoadFailed ? (
                <img
                  src={profile.photo_url}
                  alt=""
                  className="h-9 w-9 shrink-0 rounded-full object-cover"
                  onError={() => setPhotoLoadFailed(true)}
                />
              ) : (
                <UserCircle
                  className="h-9 w-9 shrink-0 text-primary-foreground/70"
                  strokeWidth={1.5}
                />
              )}
            </Link>
          )}

          {toggleButton}
        </div>

        {!isCollapsed && (
          <Link to="/profile" onClick={onNavigate} className="min-w-0 flex-1 hover:opacity-80">
            <p
              className="inline-block truncate bg-[linear-gradient(90deg,#a855f7_12.5%,#3b82f6_37.5%,#22c55e_58.33%,#fdba74_75%,#fca5a5_91.67%)] bg-clip-text text-xs italic text-transparent"
              title={`${greeting}, ${displayName}`}
            >
              {greeting},
            </p>
            <p className="truncate text-xs font-normal not-italic text-primary-foreground">
              {displayName}
            </p>
            {user?.fullName && user?.email && (
              <p className="truncate text-xs text-primary-foreground/60">{user.email}</p>
            )}
            <p className="truncate text-xs text-primary-foreground/80">{formattedDate}</p>
          </Link>
        )}
      </div>

      <div className="h-px bg-[linear-gradient(90deg,#a855f7_12.5%,#3b82f6_37.5%,#22c55e_58.33%,#fdba74_75%,#fca5a5_91.67%)]" />

      <div className="flex-1 overflow-y-auto bg-primary">
        {inSettings ? (
          <nav className="flex flex-col gap-1 p-3">
            {SETTINGS_NAV_ITEMS.map(({ to, label, icon: Icon, end }) => {
              const link = (
                <NavLink
                  key={to}
                  to={to}
                  end={end}
                  aria-label={label}
                  onClick={onNavigate}
                  className={({ isActive }) =>
                    cn(
                      "flex w-full items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors",
                      isCollapsed && "justify-center px-0",
                      isActive ? activeGradientClasses : inactiveClasses,
                    )
                  }
                >
                  <Icon className="h-4 w-4 shrink-0" />
                  {!isCollapsed && label}
                </NavLink>
              );

              if (!isCollapsed) return link;

              return (
                <Tooltip key={to} content={label} placement="left" className="flex w-full">
                  {link}
                </Tooltip>
              );
            })}
          </nav>
        ) : (
          isCareerProfilePage &&
          (isCollapsed ? (
            <div className="flex justify-center p-3">
              <Tooltip content="Target Roles" placement="left">
                <button
                  type="button"
                  onClick={onToggle}
                  aria-label="Expand to view Target Roles"
                  className="flex h-9 w-9 items-center justify-center rounded-md text-primary-foreground/80 hover:bg-white/10 hover:text-primary-foreground"
                >
                  <Crosshair className="h-4 w-4" />
                </button>
              </Tooltip>
            </div>
          ) : (
            <TargetRolesWidget onNavigate={onNavigate} />
          ))
        )}
      </div>

      {showSettingsAndSignOut && (
        <div
          className={cn(
            "relative mt-auto flex flex-col gap-1 rainbow-border-t bg-[hsl(var(--primary-light))] px-3 py-2",
            isCollapsed && "min-h-[var(--shell-icon-endbox-h)]",
          )}
        >
          {isCollapsed ? (
            <Tooltip content="Settings" placement="left" className="flex w-full justify-center">
              <Link
                to="/settings"
                aria-label="Settings"
                onClick={onNavigate}
                className={cn(
                  "flex h-9 w-9 items-center justify-center rounded-md transition-colors",
                  inSettings ? activeGradientClasses : inactiveClasses,
                )}
              >
                <Settings className="h-4 w-4" />
              </Link>
            </Tooltip>
          ) : (
            <Link
              to="/settings"
              onClick={onNavigate}
              className={cn(
                "flex items-center gap-3 rounded-md px-3 py-1.5 text-sm font-medium transition-colors",
                inSettings ? activeGradientClasses : inactiveClasses,
              )}
            >
              <Settings className="h-4 w-4" />
              Settings
            </Link>
          )}

          {isCollapsed ? (
            <Tooltip content="Sign out" placement="left" className="flex w-full justify-center">
              <div className="rounded-md bg-[linear-gradient(90deg,#a855f7_12.5%,#3b82f6_37.5%,#22c55e_58.33%,#fdba74_75%,#fca5a5_91.67%)] p-[3px]">
                <button
                  type="button"
                  onClick={onLogout}
                  aria-label="Sign out"
                  className="flex h-8 w-8 items-center justify-center rounded-[4px] bg-primary transition-colors hover:bg-white/5"
                >
                  <LogOut className="h-4 w-4" strokeWidth={2} color="url(#rainbow-accent-gradient)" />
                </button>
              </div>
            </Tooltip>
          ) : (
            <div className="rounded-md bg-[linear-gradient(90deg,#a855f7_12.5%,#3b82f6_37.5%,#22c55e_58.33%,#fdba74_75%,#fca5a5_91.67%)] p-[3px]">
              <button
                type="button"
                onClick={onLogout}
                className="flex w-full items-center gap-3 rounded-[4px] bg-primary px-3 py-1.5 text-sm font-medium transition-colors hover:bg-white/5"
              >
                <LogOut className="h-4 w-4" strokeWidth={2} color="url(#rainbow-accent-gradient)" />
                <span className="bg-[linear-gradient(90deg,#a855f7_12.5%,#3b82f6_37.5%,#22c55e_58.33%,#fdba74_75%,#fca5a5_91.67%)] bg-clip-text text-transparent">
                  Sign out
                </span>
              </button>
            </div>
          )}
        </div>
      )}
    </>
  );
}
