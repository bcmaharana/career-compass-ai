import { AccountPanelContent } from "@/components/layout/AccountPanelContent";
import { Menu } from "lucide-react";

interface RightNavProps {
  onLogout: () => void;
  /** A persistent width toggle, not a drawer. Collapsed shows icon-only
   * content (profile photo, Settings/sub-nav icons) at --shell-icon-nav-w;
   * expanded shows full labels/text at --shell-right-nav-w. */
  isCollapsed: boolean;
  /** Flips isCollapsed — wired to the ☰ button in this rail's own top
   * box, visible at every screen width. */
  onToggle: () => void;
}

/**
 * Fixed right region of the desktop app shell (brief Part 1.4). Spans the
 * full viewport height and never scrolls or hides — see DesktopShell.tsx.
 * Below `md` (MobileShell.tsx) this rail doesn't render at all — its
 * content becomes MobileAccountDrawer.tsx's slide-in drawer instead, both
 * sharing AccountPanelContent.tsx rather than duplicating the identity/
 * contextual/settings-signout markup.
 *
 * This component now only owns the fixed-rail wrapper and the ☰
 * width-toggle button — everything else lives in AccountPanelContent.
 */
export function RightNav({ onLogout, isCollapsed, onToggle }: RightNavProps) {
  return (
    <nav
      className="fixed inset-y-0 right-0 z-20 flex w-[var(--current-right-nav-w)] flex-col rainbow-border-l transition-[width] duration-200 ease-out"
      aria-label="Right navigation"
    >
      <AccountPanelContent
        onLogout={onLogout}
        isCollapsed={isCollapsed}
        onToggle={onToggle}
        toggleButton={
          <button
            type="button"
            onClick={onToggle}
            aria-label={isCollapsed ? "Expand account panel" : "Collapse account panel"}
            aria-expanded={!isCollapsed}
            title={isCollapsed ? "Expand account panel" : "Collapse account panel"}
            className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md text-primary-foreground/80 hover:bg-white/10 hover:text-primary-foreground"
          >
            <Menu className="h-5 w-5" />
          </button>
        }
      />
    </nav>
  );
}
