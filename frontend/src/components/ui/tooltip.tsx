import { cn } from "@/lib/utils";
import { useRef, useState } from "react";
import type { ReactNode } from "react";
import { createPortal } from "react-dom";

interface TooltipProps {
  content: string;
  children: ReactNode;
  className?: string;
  /** "bottom" (default, unchanged): below and left-aligned with the
   * trigger — for a truncated inline label like TargetRolesWidget's.
   * "right"/"left": vertically centered beside the trigger, opening
   * away from whichever screen edge the rail sits against — "right" for
   * Left Nav's collapsed icon rail, "left" for Right Nav's (opening
   * "right" there would push the tooltip off-screen). */
  placement?: "bottom" | "right" | "left";
}

/**
 * Minimal hover tooltip — no Radix dependency (see CLAUDE.md's "no
 * heavy UI kit" convention). Appears the instant the mouse enters,
 * unlike a native `title` attribute tooltip, which most browsers delay
 * by roughly 600ms-1s before showing.
 *
 * "right"/"left" placement portals into document.body instead of using
 * the plain CSS group-hover approach "bottom" placement uses. Both
 * collapsed icon rails (Left Nav "right", Right Nav "left") sit inside
 * an `overflow-y-auto` <nav>/scroll container — per the CSS overflow
 * spec, a non-visible overflow-y forces the computed overflow-x to auto
 * too, which silently clips any absolutely-positioned descendant (this
 * tooltip) that visually extends past the rail's edge. Confirmed live
 * for "right": the tooltip was rendering, just clipped away entirely at
 * the rail boundary, reading as "hidden behind the center panel." A
 * portal renders outside that clipping ancestor, sidestepping the
 * problem entirely; "bottom" placement (TargetRolesWidget) has no such
 * ancestor and stays on the simpler, already-working CSS mechanism
 * rather than risk a regression there for an unaffected case.
 */
export function Tooltip({ content, children, className, placement = "bottom" }: TooltipProps) {
  const [sidePlacementVisible, setSidePlacementVisible] = useState(false);
  const [coords, setCoords] = useState({ top: 0, left: 0 });
  const triggerRef = useRef<HTMLDivElement>(null);

  function show() {
    const rect = triggerRef.current?.getBoundingClientRect();
    if (!rect) return;
    const left = placement === "left" ? rect.left - 8 : rect.right + 8;
    setCoords({ top: rect.top + rect.height / 2, left });
    setSidePlacementVisible(true);
  }
  function hide() {
    setSidePlacementVisible(false);
  }

  if (placement === "right" || placement === "left") {
    return (
      <div
        ref={triggerRef}
        className={cn("relative cursor-pointer", className)}
        onMouseEnter={show}
        onMouseLeave={hide}
        onFocus={show}
        onBlur={hide}
      >
        {children}
        {sidePlacementVisible &&
          createPortal(
            <span
              role="tooltip"
              style={{ top: coords.top, left: coords.left }}
              className={cn(
                "pointer-events-none fixed z-50 -translate-y-1/2 whitespace-nowrap rounded-md bg-foreground px-2 py-1 text-xs font-normal text-background shadow-card",
                placement === "left" && "-translate-x-full",
              )}
            >
              {content}
            </span>,
            document.body,
          )}
      </div>
    );
  }

  return (
    <div className={cn("group relative cursor-pointer", className)}>
      {children}
      <div
        role="tooltip"
        className="pointer-events-none absolute left-0 top-full z-20 mt-1 hidden max-w-xs whitespace-normal rounded-md bg-foreground px-2 py-1 text-xs font-normal text-background shadow-card group-hover:block"
      >
        {content}
      </div>
    </div>
  );
}
