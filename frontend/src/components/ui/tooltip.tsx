import { cn } from "@/lib/utils";
import { useRef, useState } from "react";
import type { ReactNode } from "react";
import { createPortal } from "react-dom";

interface TooltipProps {
  /** Plain string for every existing caller — also accepts a ReactNode
   * (e.g. a fragment with `<br />`s) for a multi-line tooltip, like
   * RightNav's collapsed profile photo. `<br />` forces a real line
   * break regardless of the `whitespace-nowrap` these tooltips render
   * with (nowrap only collapses source whitespace/newlines in text; it
   * doesn't suppress an actual `<br />` element). */
  content: ReactNode;
  children: ReactNode;
  className?: string;
  /** "bottom" (default): below and left-aligned with the trigger — for
   * a truncated inline label like TargetRolesWidget's. Renders nowrap
   * (2026-08-09, was whitespace-normal + max-w-xs) — a narrow icon-only
   * trigger (no explicit width) sizes its containing block to the
   * icon's own width, and the old wrapping rules let a short tooltip
   * like "Sign in" break across two lines inside that narrow box;
   * TargetRolesWidget's trigger is a wide flex-1 row, so nowrap doesn't
   * change anything there.
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
    // Vertically centered on the trigger via -translate-y-1/2 below —
    // fine for every existing short single-line tooltip, but a taller
    // multi-line one (e.g. RightNav's collapsed profile photo) centered
    // on a trigger near the very top of the viewport pushes its own top
    // edge above y=0, clipping it. A floor keeps the centering point far
    // enough down that even a several-line tooltip stays fully on-screen
    // for a trigger that close to the top; it's a no-op for every
    // trigger already below this point.
    const top = Math.max(rect.top + rect.height / 2, 56);
    setCoords({ top, left });
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
        className="pointer-events-none absolute left-0 top-full z-20 mt-1 hidden whitespace-nowrap rounded-md bg-foreground px-2 py-1 text-xs font-normal text-background shadow-card group-hover:block"
      >
        {content}
      </div>
    </div>
  );
}
