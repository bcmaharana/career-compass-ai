import { useEffect, useState } from "react";

/**
 * Drives a two-phase mount/exit animation, shared by MobileNavMenu.tsx and
 * MobileAccountMenu.tsx's dropdown panels (both fade/scale) rather than
 * each hand-rolling its own copy. `rendered` controls whether the element
 * is in the DOM at all — true while open, and for `durationMs` after
 * closing so an exit transition has time to play before actually
 * unmounting. A dropdown left mounted-and-hidden purely via CSS at all
 * times would mean a "closed" panel's links/buttons were still genuinely
 * tab-reachable even though nothing was visible — fully unmounting after
 * the exit transition avoids that.
 *
 * `visible` drives the actual transition classes, flipped a frame after
 * mount via requestAnimationFrame so the browser commits the closed
 * starting position before animating to the open one.
 */
export function useMountTransition(
  open: boolean,
  durationMs: number,
): { rendered: boolean; visible: boolean } {
  const [rendered, setRendered] = useState(open);
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    if (open) {
      setRendered(true);
      const raf = requestAnimationFrame(() => setVisible(true));
      return () => cancelAnimationFrame(raf);
    }
    setVisible(false);
    const timeout = setTimeout(() => setRendered(false), durationMs);
    return () => clearTimeout(timeout);
  }, [open, durationMs]);

  return { rendered, visible };
}
