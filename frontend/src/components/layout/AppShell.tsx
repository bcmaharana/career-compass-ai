import { AppFooter } from "@/components/layout/AppFooter";
import { AppHeader } from "@/components/layout/AppHeader";
import { ChatThread } from "@/components/layout/ChatThread";
import { RightNav } from "@/components/layout/RightNav";
import { formatDisplayDate } from "@/lib/date-format";
import { NAV_ITEMS, matchNavItem } from "@/lib/nav-items";
import { cn } from "@/lib/utils";
import { useAuthStore } from "@/stores/auth-store";
import { useChatStore } from "@/stores/chat-store";
import { useQueryClient } from "@tanstack/react-query";
import { Compass } from "lucide-react";
import { useEffect, useRef } from "react";
import { Link, NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";

/** "Last logged in @ 12:30pm ET on Sunday, 26-Jul-2026" — always the
 * *viewer's* local time/timezone, not a fixed zone, matching every other
 * local-time display in this shell (see RightNav's useLocalClock). */
function formatLastLogin(isoTimestamp: string): string {
  const date = new Date(isoTimestamp);
  const time = date
    .toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit", hour12: true })
    .toLowerCase()
    .replace(" ", "");
  const tzAbbr =
    new Intl.DateTimeFormat(undefined, { timeZoneName: "short" })
      .formatToParts(date)
      .find((part) => part.type === "timeZoneName")?.value ?? "";
  const weekday = date.toLocaleDateString(undefined, { weekday: "long" });
  const isoDate = `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;
  return `Last logged in @ ${time} ${tzAbbr} on ${weekday}, ${formatDisplayDate(isoDate)}`;
}

/**
 * Application shell: four fixed regions (Left Nav, Header, Footer, Right
 * Nav) around one independently scrollable center panel.
 *
 * All four fixed regions use `position: fixed` against the viewport
 * (not `sticky`) so none of them can ever be scrolled or pushed off —
 * sizing them is handled entirely by the `--shell-*` CSS variables in
 * globals.css, which the center `<main>` also reads for its inset, so
 * the fixed regions and the scrollable area can't drift out of sync.
 * The outer wrapper is itself `fixed inset-0` so the document body never
 * gains scrollable height of its own; only `<main>` scrolls.
 */
export function AppShell() {
  const navigate = useNavigate();
  const location = useLocation();
  const user = useAuthStore((state) => state.user);
  const clearSession = useAuthStore((state) => state.clearSession);
  const queryClient = useQueryClient();

  const chatMessages = useChatStore((state) => state.messages);
  const clearChat = useChatStore((state) => state.clear);
  const mainRef = useRef<HTMLElement>(null);
  const activeNavItem = matchNavItem(location.pathname);
  const previousNavItemRef = useRef(activeNavItem);

  // Clears the visible chat thread on a genuine Left Nav section change
  // (brief Part 1.2) — the conversation itself stays persisted server-side
  // regardless; this only resets what's rendered in the center panel.
  useEffect(() => {
    if (previousNavItemRef.current !== activeNavItem) {
      clearChat();
      previousNavItemRef.current = activeNavItem;
    }
  }, [activeNavItem, clearChat]);

  // Auto-scrolls the center panel down to reveal a newly appended
  // exchange, the same "new messages push the view down" behavior as
  // this chat interface itself — underlying page content just scrolls
  // out of view above, it's never removed.
  useEffect(() => {
    if (chatMessages.length === 0) return;
    mainRef.current?.scrollTo({ top: mainRef.current.scrollHeight, behavior: "smooth" });
  }, [chatMessages.length]);

  function handleLogout() {
    clearSession();
    // The query cache is a module-level singleton, not scoped per
    // session — without clearing it, logging back in (even as a
    // different user) could briefly show whatever data the *previous*
    // session had cached before a background refetch replaced it.
    queryClient.clear();
    navigate("/login", { replace: true });
  }

  return (
    <div className="fixed inset-0 overflow-hidden bg-background">
      {/* Hidden defs only — provides #rainbow-accent-gradient for the
          logo icon's stroke below. Not rendered visually itself. */}
      <svg width="0" height="0" className="absolute" aria-hidden="true">
        <defs>
          <linearGradient id="rainbow-accent-gradient" x1="0%" y1="0%" x2="100%" y2="0%">
            <stop offset="12.5%" stopColor="#a855f7" />
            <stop offset="37.5%" stopColor="#3b82f6" />
            <stop offset="58.33%" stopColor="#22c55e" />
            <stop offset="75%" stopColor="#fdba74" />
            <stop offset="91.67%" stopColor="#fca5a5" />
          </linearGradient>
        </defs>
      </svg>

      <aside className="fixed inset-y-0 left-0 z-20 flex w-[var(--shell-left-nav-w)] flex-col bg-primary text-primary-foreground">
        <Link
          to="/"
          className="flex h-[var(--shell-header-h)] items-center gap-2 bg-[hsl(var(--primary-light))] px-6"
        >
          <Compass
            className="h-8 w-8 shrink-0"
            strokeWidth={2}
            color="url(#rainbow-accent-gradient)"
          />
          <span
            className="inline-block whitespace-nowrap bg-[linear-gradient(90deg,#a855f7_12.5%,#3b82f6_37.5%,#22c55e_58.33%,#fdba74_75%,#fca5a5_91.67%)] bg-clip-text font-display text-xl font-semibold tracking-tight text-transparent"
          >
            Career Compass
          </span>
        </Link>

        <div className="border-t border-gray-500" />

        <nav className="mt-4 flex flex-1 flex-col gap-1 overflow-y-auto px-3">
          {NAV_ITEMS.map(({ to, label, icon: Icon, end }) => (
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

        <div className="mt-auto flex min-h-[var(--shell-footer-h)] shrink-0 flex-col justify-center border-t border-gray-500 bg-[hsl(var(--primary-light))] px-3 py-2">
          <p className="px-3 text-xs leading-snug text-primary-foreground/70">
            {user?.lastLoginAt
              ? formatLastLogin(user.lastLoginAt)
              : "Welcome — this is your first login."}
          </p>
        </div>
      </aside>

      <AppHeader />
      <AppFooter />
      <RightNav onLogout={handleLogout} />

      <main
        ref={mainRef}
        className="fixed bottom-[var(--shell-footer-h)] left-[var(--shell-left-nav-w)] right-[var(--shell-right-nav-w)] top-[var(--shell-header-h)] overflow-y-auto bg-[hsl(var(--center-bg))]"
      >
        <div className="container py-8">
          <Outlet />
          <ChatThread />
        </div>
      </main>
    </div>
  );
}
