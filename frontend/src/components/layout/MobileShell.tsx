import { AppFooter } from "@/components/layout/AppFooter";
import { AppHeader } from "@/components/layout/AppHeader";
import { ChatThread } from "@/components/layout/ChatThread";
import { matchNavItem } from "@/lib/nav-items";
import { useAuthStore } from "@/stores/auth-store";
import type { CSSProperties, RefObject } from "react";
import { Outlet, useLocation } from "react-router-dom";

interface MobileShellProps {
  mainRef: RefObject<HTMLElement>;
  onLogout: () => void;
}

/**
 * Mobile app shell (< `md`, see AppShell.tsx's useIsMobileShell) — the
 * hamburger-menu/footer redesign of DesktopShell.tsx's rails. No Left
 * Nav/Right Nav rails: primary navigation lives in AppHeader's
 * MobileNavMenu dropdown (an earlier version used a fixed bottom tab bar
 * instead, replaced after live testing — a tab bar has a hard width
 * budget the nav list was expected to outgrow, a dropdown doesn't share
 * that limit), and the account panel is AppHeader's MobileAccountMenu
 * dropdown (an earlier version was a full-height right-edge sheet,
 * removed to mirror the nav dropdown's own interaction pattern). Both
 * header dropdowns are self-contained (own their open state internally),
 * so this component only needs to thread `onLogout` through to AppHeader
 * — no drawer-open state lives here anymore.
 *
 * AppFooter is shared with DesktopShell rather than replaced by a
 * separate floating-button-plus-sheet (an earlier version,
 * MobileChatSheet.tsx, worked that way — removed after live feedback
 * asked for a persistent docked composer instead, matching desktop, plus
 * Settings/Sign out/last-login icons the same way the header mirrors
 * Left/Right Nav's top boxes). `user?.lastLoginAt` is read here (not
 * inside AppFooter itself) since AppFooter is also DesktopShell's plain
 * chat bar and shouldn't need an identity-store dependency for that case.
 *
 * AppHeader/AppFooter are shared with DesktopShell rather than forked —
 * their `left-[var(--current-left-nav-w)]`/
 * `right-[var(--current-right-nav-w)]` classes resolve to 0 here via the
 * wrapping div's inline style below (`display: contents`, same "carries
 * no layout of its own, just defines the CSS vars" trick DesktopShell
 * uses for its own rail widths), so `<main>` and both bars span the full
 * viewport width with no rail inset.
 */
export function MobileShell({ mainRef, onLogout }: MobileShellProps) {
  const location = useLocation();
  const activeNavItem = matchNavItem(location.pathname);
  const user = useAuthStore((state) => state.user);

  const navWidthStyle = {
    "--current-left-nav-w": "0px",
    "--current-right-nav-w": "0px",
  } as CSSProperties;

  return (
    <div style={navWidthStyle} className="contents">
      <AppHeader onLogout={onLogout} />

      <main
        ref={mainRef}
        className="fixed inset-x-0 bottom-[var(--shell-mobile-header-h)] top-[var(--shell-mobile-header-h)] overflow-y-auto scrollbar-hide bg-[hsl(var(--center-bg))]"
      >
        <div className="container py-6">
          <Outlet />
          {/* CoachPage renders the thread itself — see DesktopShell.tsx's
              identical guard for why this skips it too. */}
          {activeNavItem.to !== "/coach" && <ChatThread />}
        </div>
      </main>

      <AppFooter onLogout={onLogout} lastLoginAt={user?.lastLoginAt ?? undefined} />
    </div>
  );
}
