import { useCareerProfile } from "@/api/queries/career-profile";
import { TargetRolesWidget } from "@/features/career-profile/TargetRolesWidget";
import { formatDisplayDate } from "@/lib/date-format";
import { SETTINGS_NAV_ITEMS, isSettingsRoute, matchNavItem } from "@/lib/nav-items";
import { cn } from "@/lib/utils";
import { useAuthStore } from "@/stores/auth-store";
import { LogOut, Settings, UserCircle } from "lucide-react";
import { useEffect, useState } from "react";
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

interface RightNavProps {
  onLogout: () => void;
}

/**
 * Fixed right region of the app shell (brief Part 1.4). Spans the full
 * viewport height and never scrolls or hides — see AppShell.tsx.
 *
 * Three sections, mirroring the Left Nav's skeleton (top box @
 * --shell-header-h / middle flexible content / bottom box @
 * --shell-footer-h, both end boxes on --primary-light so the two rails
 * bookend the page): identity (name, email, date) up top; a per-page
 * contextual slot in the middle — the Career Profile page's target-roles
 * widget (Part 2.5, TargetRolesWidget.tsx), the Settings sub-nav
 * (SETTINGS_NAV_ITEMS) under /settings/*, or a plain structural
 * placeholder otherwise, all matched by route via matchNavItem/
 * isSettingsRoute; and Settings + Sign out pinned to the bottom box.
 *
 * The Left Nav is deliberately constant across every route (always the
 * 4 main NAV_ITEMS, never swapped) — Settings' own sub-navigation lives
 * here instead, since this rail is already the "changes per page" one.
 */
export function RightNav({ onLogout }: RightNavProps) {
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

  return (
    <nav
      className="fixed inset-y-0 right-0 z-20 flex w-[var(--shell-right-nav-w)] flex-col"
      aria-label="Right navigation"
    >
      <div className="flex h-[var(--shell-header-h)] flex-col justify-center gap-0.5 bg-[hsl(var(--primary-light))] px-4 text-primary-foreground">
        <Link to="/profile" className="flex items-center gap-3 hover:opacity-80">
          {profile?.photo_url && !photoLoadFailed ? (
            <img
              src={profile.photo_url}
              alt=""
              className="h-9 w-9 shrink-0 rounded-full object-cover"
              onError={() => setPhotoLoadFailed(true)}
            />
          ) : (
            <UserCircle className="h-9 w-9 shrink-0 text-primary-foreground/70" strokeWidth={1.5} />
          )}
          <div className="min-w-0">
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
          </div>
        </Link>

        <p className="truncate pl-12 text-xs text-primary-foreground/80">{formattedDate}</p>
      </div>

      <div className="border-t border-gray-500" />

      <div className="flex-1 overflow-y-auto bg-primary">
        {inSettings ? (
          <nav className="flex flex-col gap-1 p-3">
            {SETTINGS_NAV_ITEMS.map(({ to, label, icon: Icon, end }) => (
              <NavLink
                key={to}
                to={to}
                end={end}
                className={({ isActive }) =>
                  cn(
                    "flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors",
                    isActive
                      ? "bg-[linear-gradient(90deg,#a855f7_12.5%,#3b82f6_37.5%,#22c55e_58.33%,#fdba74_75%,#fca5a5_91.67%)] text-primary"
                      : "text-primary-foreground/80 hover:bg-white/5 hover:text-primary-foreground",
                  )
                }
              >
                <Icon className="h-4 w-4" />
                {label}
              </NavLink>
            ))}
          </nav>
        ) : (
          isCareerProfilePage && <TargetRolesWidget />
        )}
      </div>

      <div className="mt-auto flex min-h-[var(--shell-footer-h)] shrink-0 flex-col justify-center gap-1 border-t border-gray-500 bg-[hsl(var(--primary-light))] px-3 py-2">
        <Link
          to="/settings"
          className={cn(
            "flex items-center gap-3 rounded-md px-3 py-1.5 text-sm font-medium transition-colors",
            inSettings
              ? "bg-[linear-gradient(90deg,#a855f7_12.5%,#3b82f6_37.5%,#22c55e_58.33%,#fdba74_75%,#fca5a5_91.67%)] text-primary"
              : "text-primary-foreground/80 hover:bg-white/5 hover:text-primary-foreground",
          )}
        >
          <Settings className="h-4 w-4" />
          Settings
        </Link>
        <div className="rounded-md bg-[linear-gradient(90deg,#a855f7_12.5%,#3b82f6_37.5%,#22c55e_58.33%,#fdba74_75%,#fca5a5_91.67%)] p-[3px]">
          <button
            onClick={onLogout}
            className="flex w-full items-center gap-3 rounded-[4px] bg-primary px-3 py-1.5 text-sm font-medium transition-colors hover:bg-white/5"
          >
            <LogOut className="h-4 w-4" strokeWidth={2} color="url(#rainbow-accent-gradient)" />
            <span className="bg-[linear-gradient(90deg,#a855f7_12.5%,#3b82f6_37.5%,#22c55e_58.33%,#fdba74_75%,#fca5a5_91.67%)] bg-clip-text text-transparent">
              Sign out
            </span>
          </button>
        </div>
      </div>
    </nav>
  );
}
