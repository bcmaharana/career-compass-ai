import { cn } from "@/lib/utils";
import { LogOut, UserCircle } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import type { ReactNode } from "react";
import { Link } from "react-router-dom";

interface ProfileIconMenuProps {
  photoUrl?: string | null;
  /** Always provided by every real caller — RightNav/AppHeader's mobile
   * icon-stack column both only render this component when a real
   * onLogout is in scope. */
  onLogout: () => void;
  /** Closes a parent drawer/dropdown on navigating away — mirrors every
   * other navigational element in AccountPanelContent. */
  onNavigate?: () => void;
  /** Sizing/hover styling of the trigger button itself — differs between
   * the desktop rail's large photo (h-9 w-9) and the mobile header's
   * small icon-in-a-box (h-7 w-7 box, h-4 w-4 glyph). */
  triggerClassName: string;
  /** Sizing of the photo/UserCircle glyph inside the trigger. */
  iconClassName: string;
  /** Optional non-interactive block shown above the two menu items —
   * AccountPanelContent's collapsed rail passes its greeting/name/date
   * summary here (2026-08-21: that content used to live in a separate
   * hover Tooltip wrapped around this same trigger, but a hover tooltip
   * and this click-menu both anchor off the same trigger and rendered
   * on top of each other the instant the menu opened while the mouse was
   * still over the icon — folding it into the menu itself, instead of a
   * second overlapping popup, removes the collision entirely). Omitted
   * by every other caller (expanded rail already shows this text
   * persistently alongside the icon; the mobile header has no such
   * summary at all). */
  header?: ReactNode;
}

/**
 * The profile photo/icon shown on the desktop Right Nav rail (both
 * collapsed and expanded) and the mobile header — clicking it now opens
 * a small menu (Career Profile / Sign Out) instead of navigating straight
 * to Career Profile, so Sign Out is always one click away from wherever
 * the profile icon is visible, not just reachable through a separate
 * Settings/hamburger path (2026-08-21, direct request).
 *
 * A local click-outside/Escape-to-close popover rather than the
 * full-screen-backdrop pattern MobileNavMenu/MobileAccountMenu use — this
 * is a small, two-item menu anchored directly under a small trigger, not
 * a large panel that needs a dimmed backdrop of its own.
 */
export function ProfileIconMenu({
  photoUrl,
  onLogout,
  onNavigate,
  triggerClassName,
  iconClassName,
  header,
}: ProfileIconMenuProps) {
  const [open, setOpen] = useState(false);
  const [photoLoadFailed, setPhotoLoadFailed] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    function handlePointerDown(event: PointerEvent) {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        setOpen(false);
      }
    }
    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") setOpen(false);
    }
    document.addEventListener("pointerdown", handlePointerDown);
    window.addEventListener("keydown", handleKeyDown);
    return () => {
      document.removeEventListener("pointerdown", handlePointerDown);
      window.removeEventListener("keydown", handleKeyDown);
    };
  }, [open]);

  function handleProfileClick() {
    setOpen(false);
    onNavigate?.();
  }

  function handleLogoutClick() {
    setOpen(false);
    onLogout();
  }

  return (
    <div ref={containerRef} className="relative">
      <button
        type="button"
        onClick={() => setOpen((prev) => !prev)}
        aria-label="Account menu"
        aria-haspopup="menu"
        aria-expanded={open}
        className={cn("transition-opacity hover:opacity-80", triggerClassName)}
      >
        {photoUrl && !photoLoadFailed ? (
          <img
            src={photoUrl}
            alt=""
            className={cn("shrink-0 rounded-full object-cover", iconClassName)}
            onError={() => setPhotoLoadFailed(true)}
          />
        ) : (
          <UserCircle
            className={cn("shrink-0 text-primary-foreground/70", iconClassName)}
            strokeWidth={1.5}
          />
        )}
      </button>

      {open && (
        <div
          role="menu"
          aria-label="Account"
          className="absolute right-0 top-full z-50 mt-2 w-56 overflow-hidden rounded-md border border-white/10 bg-primary shadow-card"
        >
          {header && (
            <div className="whitespace-nowrap border-b border-white/10 px-3 py-2 text-xs leading-snug text-primary-foreground/70">
              {header}
            </div>
          )}
          <Link
            to="/profile"
            role="menuitem"
            onClick={handleProfileClick}
            className="flex items-center gap-2 px-3 py-2 text-xs font-medium text-primary-foreground/80 transition-colors hover:bg-white/10 hover:text-primary-foreground"
          >
            <UserCircle className="h-4 w-4 shrink-0" />
            Career Profile
          </Link>
          <button
            type="button"
            role="menuitem"
            onClick={handleLogoutClick}
            className="flex w-full items-center gap-2 px-3 py-2 text-left text-xs font-medium text-primary-foreground/80 transition-colors hover:bg-white/10 hover:text-primary-foreground"
          >
            <LogOut className="h-4 w-4 shrink-0" />
            Sign Out
          </button>
        </div>
      )}
    </div>
  );
}
