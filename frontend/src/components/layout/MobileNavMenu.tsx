import { useMountTransition } from "@/hooks/useMountTransition";
import { NAV_ITEMS, matchNavItem } from "@/lib/nav-items";
import { PLATFORM_BASE_URL } from "@/lib/platform";
import { cn } from "@/lib/utils";
import { useMobileDropdownStore } from "@/stores/mobile-dropdown-store";
import { LayoutGrid, Menu } from "lucide-react";
import { useEffect } from "react";
import { NavLink, useLocation } from "react-router-dom";

const TRANSITION_MS = 150;

/**
 * Mobile header's left-side nav trigger (see AppHeader.tsx) — a hamburger
 * button that opens a compact dropdown panel listing NAV_ITEMS, anchored
 * just below the header, rather than a full-height drawer. This replaced
 * an earlier fixed bottom tab bar: a tab bar has a hard width budget that
 * doesn't grow, and the nav list is expected to grow past what 5 tabs
 * already comfortably fit.
 *
 * Selecting an item navigates and closes the menu; so does Escape or
 * tapping the dimmed backdrop. Open state lives in useMobileDropdownStore
 * (shared with MobileAccountMenu.tsx) rather than local state, so opening
 * this one automatically closes that one instead of both being open and
 * stacked on screen at once.
 */
export function MobileNavMenu() {
  const open = useMobileDropdownStore((state) => state.active === "nav");
  const openDropdown = useMobileDropdownStore((state) => state.open);
  const closeDropdown = useMobileDropdownStore((state) => state.close);
  const { rendered, visible } = useMountTransition(open, TRANSITION_MS);
  const location = useLocation();
  const activeTo = matchNavItem(location.pathname).to;

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
        onClick={() => openDropdown("nav")}
        aria-label="Open navigation menu"
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
            aria-label="Primary navigation"
            onClick={(event) => event.stopPropagation()}
            className={cn(
              "fixed left-3 top-[calc(var(--shell-mobile-header-h)+0.5rem)] w-56 origin-top-left rounded-lg border border-white/10 bg-primary py-2 shadow-card transition-[opacity,transform] duration-150 ease-out",
              visible ? "scale-100 opacity-100" : "scale-95 opacity-0",
            )}
          >
            <a
              href={PLATFORM_BASE_URL}
              role="menuitem"
              className="flex items-center gap-3 border-b border-white/10 px-4 py-2.5 text-sm font-medium text-primary-foreground/80 hover:bg-white/5 hover:text-primary-foreground"
            >
              <LayoutGrid className="h-4 w-4 shrink-0" />
              Back to Hub
            </a>

            {NAV_ITEMS.map(({ to, label, icon: Icon, end, children }) => {
              const isActive = activeTo === to;
              return (
                <div key={to}>
                  <NavLink
                    to={to}
                    end={end}
                    role="menuitem"
                    onClick={() => closeDropdown()}
                    className={cn(
                      "flex items-center gap-3 px-4 py-2.5 text-sm font-medium",
                      isActive
                        ? "bg-[linear-gradient(90deg,#a855f7_12.5%,#3b82f6_37.5%,#22c55e_58.33%,#fdba74_75%,#fca5a5_91.67%)] text-primary"
                        : "text-primary-foreground/80 hover:bg-white/5 hover:text-primary-foreground",
                    )}
                  >
                    <Icon className="h-4 w-4 shrink-0" />
                    {label}
                  </NavLink>
                  {/* Nested pages (e.g. Interview Prep under Learning
                      Intelligence) always show indented here — this is
                      already a transient, full-list overlay, so there's
                      no separate expand/collapse affordance the way the
                      persistent desktop rail needs one. */}
                  {children?.map((child) => {
                    const isChildActive = activeTo === child.to;
                    return (
                      <NavLink
                        key={child.to}
                        to={child.to}
                        end={child.end}
                        role="menuitem"
                        onClick={() => closeDropdown()}
                        className={cn(
                          "flex items-center gap-3 py-2 pl-10 pr-4 text-sm font-medium",
                          isChildActive
                            ? "bg-[linear-gradient(90deg,#a855f7_12.5%,#3b82f6_37.5%,#22c55e_58.33%,#fdba74_75%,#fca5a5_91.67%)] text-primary"
                            : "text-primary-foreground/80 hover:bg-white/5 hover:text-primary-foreground",
                        )}
                      >
                        <child.icon className="h-4 w-4 shrink-0" />
                        {child.label}
                      </NavLink>
                    );
                  })}
                </div>
              );
            })}
          </div>
        </div>
      )}
    </>
  );
}
