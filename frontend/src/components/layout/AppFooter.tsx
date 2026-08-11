import { ChatComposerForm } from "@/components/layout/ChatComposerForm";
import { Tooltip } from "@/components/ui/tooltip";
import { formatLastLogin } from "@/lib/format-last-login";
import { Clock, LogOut, Settings } from "lucide-react";
import { Link } from "react-router-dom";

interface AppFooterProps {
  /** Logs the user out — threaded to the mobile-only right column's Sign
   * out icon. MobileShell.tsx passes this — which is also what this
   * component uses to decide it's in the mobile shell at all, rendering
   * the left (clock)/right (Settings, Sign out) icon columns only when
   * set. DesktopShell.tsx doesn't pass it, so those columns never render
   * there and this is just the plain chat bar it always was. */
  onLogout?: () => void;
  /** Feeds the mobile-only left column's "last logged in" tooltip —
   * mirrors DesktopShell.tsx's Left Nav bottom box, which has no mobile
   * equivalent otherwise since that rail doesn't exist below `md`. */
  lastLoginAt?: string;
}

/**
 * Fixed bottom region of the app shell (brief Part 1.2): a persistent AI
 * Chat input, present on every page. A sent message is appended to the
 * center panel by ChatThread.tsx (via the shared chat-store), never
 * rendered here. The AI Career Coach page (CoachPage.tsx) is a second
 * entry point into the exact same send flow — see useChatComposer.ts.
 *
 * Shared by both DesktopShell and MobileShell rather than forked, mirroring
 * AppHeader.tsx's own pattern exactly: on desktop this is just the chat
 * composer at --shell-footer-h; on mobile it becomes a three-column bar at
 * the shorter --shell-mobile-header-h (matching the header's height, same
 * token reused for visual symmetry) — a left column with a Clock icon
 * (tooltip shows the formatted last-login string, replacing what Left
 * Nav's rail shows on desktop and has no other mobile home), the chat
 * composer in the middle (flex-1), and a right column with Settings above
 * Sign out, stacked vertically. Settings/Sign out used to also live in the
 * mobile account dropdown's (MobileAccountMenu.tsx) own bottom box
 * (AccountPanelContent's showSettingsAndSignOut) — moved here instead so
 * there's one place for each action rather than two, now that the footer
 * covers it; the dropdown still shows the target-roles-widget-or-settings-
 * sub-nav content above where that box used to be.
 *
 * Both mobile-only columns share the exact same `h-7 w-7` box / `h-4 w-4`
 * glyph sizing as AppHeader's own icon columns, for the same top/bottom
 * visual symmetry — a `pb-[env(safe-area-inset-bottom)]` on the bar itself
 * (not extra height) reserves room for the iOS home-indicator area inside
 * the existing --shell-mobile-header-h box rather than growing past it,
 * so the footer's total height still matches the header's exactly.
 */
export function AppFooter({ onLogout, lastLoginAt }: AppFooterProps) {
  const isMobile = Boolean(onLogout);

  return (
    <footer
      className="fixed bottom-0 left-[var(--current-left-nav-w)] right-[var(--current-right-nav-w)] z-10 flex h-[var(--shell-mobile-header-h)] items-stretch gap-3 rainbow-border-t bg-[linear-gradient(to_bottom,#2A4382,#18284E)] px-3 pb-[env(safe-area-inset-bottom)] transition-[left,right] duration-200 ease-out md:h-[var(--shell-footer-h)] md:items-center md:px-6 md:pb-0"
      aria-label="AI chat"
    >
      {isMobile && (
        <div className="flex shrink-0 flex-col justify-center border-r border-white/15 pr-3 md:hidden">
          <Tooltip
            content={lastLoginAt ? formatLastLogin(lastLoginAt) : "Welcome — this is your first login."}
            placement="right"
          >
            <button
              type="button"
              aria-label="Last login time"
              className="flex h-7 w-7 items-center justify-center rounded-md text-primary-foreground/80 hover:bg-white/10 hover:text-primary-foreground"
            >
              <Clock className="h-4 w-4" />
            </button>
          </Tooltip>
        </div>
      )}

      <ChatComposerForm className="min-w-0 flex-1" />

      {onLogout && (
        <div className="flex shrink-0 flex-col items-center justify-center gap-px border-l border-white/15 pl-3 md:hidden">
          <Link
            to="/settings"
            aria-label="Settings"
            className="flex h-7 w-7 items-center justify-center rounded-md text-primary-foreground/80 hover:bg-white/10 hover:text-primary-foreground"
          >
            <Settings className="h-4 w-4" />
          </Link>
          <button
            type="button"
            onClick={onLogout}
            aria-label="Sign out"
            className="flex h-7 w-7 items-center justify-center rounded-md text-primary-foreground/80 hover:bg-white/10 hover:text-primary-foreground"
          >
            <LogOut className="h-4 w-4" />
          </button>
        </div>
      )}
    </footer>
  );
}
