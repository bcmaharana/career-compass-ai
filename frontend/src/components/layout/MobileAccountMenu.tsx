import { AccountPanelContent } from "@/components/layout/AccountPanelContent";
import { useMountTransition } from "@/hooks/useMountTransition";
import { cn } from "@/lib/utils";
import { useMobileDropdownStore } from "@/stores/mobile-dropdown-store";
import { Menu } from "lucide-react";
import { useEffect } from "react";
import { useLocation } from "react-router-dom";

const TRANSITION_MS = 150;

/**
 * Mobile header's right-side account trigger (see AppHeader.tsx) — a
 * hamburger button that opens a compact dropdown panel, mirroring
 * MobileNavMenu's left-side pattern (anchored top-right instead of
 * top-left) rather than the full-height right-edge slide-in drawer this
 * replaced (MobileAccountDrawer.tsx), after live feedback asked for both
 * hamburgers to behave the same way.
 *
 * Wraps AccountPanelContent — the same identity/target-roles-or-settings
 * body the desktop rail (RightNav.tsx) uses, so this and the rail never
 * drift into two different account-panel implementations — bounded to a
 * max height with its own scroll, since unlike the 5-item nav list this
 * content can genuinely run long (a long target-roles list, for
 * instance). Passes `showSettingsAndSignOut={false}`: those two actions
 * live in AppFooter.tsx's mobile-only icon columns instead (moved there
 * after live feedback, so both header hamburgers' dropdowns follow the
 * same pattern and Settings/Sign out aren't reachable two different
 * ways) — no `onLogout` needed here as a result, since the button that
 * used it is the thing that moved.
 *
 * Closes on Escape, tapping the dimmed backdrop, or selecting a
 * navigational item inside (AccountPanelContent's onNavigate). Open state
 * lives in useMobileDropdownStore (shared with MobileNavMenu.tsx) rather
 * than local state, so opening this one automatically closes that one
 * instead of both being open and stacked on screen at once.
 *
 * Auto-opens on landing at the bare /settings route — that page's own
 * message ("Choose a category from the panel on the right...") assumes a
 * persistent Right Nav rail, which doesn't exist in the mobile shell;
 * without this, that panel is just gone on mobile, telling the user to
 * pick from something they can't see. Keyed on `location.key` (which
 * changes on every navigation, not just ones that change the pathname
 * value) rather than `location.pathname` — re-clicking the footer's
 * Settings link while already on /settings is a genuine navigation the
 * user expects to reopen this, but the pathname itself doesn't change on
 * a same-URL revisit, so a plain `[location.pathname]` dependency missed
 * exactly that case: closing the dropdown once and tapping Settings again
 * silently did nothing.
 */
export function MobileAccountMenu() {
  const open = useMobileDropdownStore((state) => state.active === "account");
  const openDropdown = useMobileDropdownStore((state) => state.open);
  const closeDropdown = useMobileDropdownStore((state) => state.close);
  const { rendered, visible } = useMountTransition(open, TRANSITION_MS);
  const location = useLocation();

  useEffect(() => {
    if (location.pathname === "/settings") openDropdown("account");
  }, [location.key, location.pathname, openDropdown]);

  useEffect(() => {
    if (!open) return;
    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") closeDropdown();
    }
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [open, closeDropdown]);

  return (
    <>
      <button
        type="button"
        onClick={() => openDropdown("account")}
        aria-label="Open account panel"
        aria-expanded={open}
        className="flex h-7 w-7 items-center justify-center rounded-md text-primary-foreground/80 hover:bg-white/10 hover:text-primary-foreground"
      >
        <Menu className="h-4 w-4" />
      </button>

      {rendered && (
        <div
          className={cn(
            "fixed inset-0 z-50 bg-black/40 transition-opacity duration-150 ease-out",
            visible ? "opacity-100" : "pointer-events-none opacity-0",
          )}
          onClick={() => closeDropdown()}
        >
          <div
            role="menu"
            aria-label="Account"
            onClick={(event) => event.stopPropagation()}
            className={cn(
              "fixed right-3 top-[calc(var(--shell-mobile-header-h)+0.5rem)] flex max-h-[min(70vh,32rem)] w-72 origin-top-right flex-col overflow-hidden rounded-lg border border-white/10 bg-primary shadow-card transition-[opacity,transform] duration-150 ease-out",
              visible ? "scale-100 opacity-100" : "scale-95 opacity-0",
            )}
          >
            <AccountPanelContent
              isCollapsed={false}
              onNavigate={() => closeDropdown()}
              showSettingsAndSignOut={false}
            />
          </div>
        </div>
      )}
    </>
  );
}
