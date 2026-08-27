import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { useCallback, useRef, useState } from "react";
import { useBlocker } from "react-router-dom";

/**
 * Confirms before an in-progress edit is discarded — either by actual
 * route navigation (a breadcrumb segment, Left Nav, browser back/forward
 * — anything react-router sees), or by a non-navigation close a caller
 * gates explicitly (a Dialog's Escape/X, an inline edit's Cancel button).
 * Both paths render through the exact same prompt (this hook's own
 * `guardElement`, one `ConfirmDialog` instance) rather than two separate
 * UIs.
 *
 * Requires the app's router to be a v6.4+ "data router" (createBrowserRouter)
 * for useBlocker to work — true for this app's router.tsx.
 *
 * Usage:
 *   const { confirmDiscard, guardElement } = useUnsavedChangesGuard(isDirty);
 *   <Dialog open={open} onClose={() => { void (async () => {
 *     if (await confirmDiscard()) setOpen(false);
 *   })(); }} ...>
 *   {guardElement}
 *
 * `isDirty` should be a plain boolean the caller already computes (e.g.
 * comparing a live draft against a value snapshotted once at edit-open
 * time) — this hook does no dirty-tracking of its own.
 */
export function useUnsavedChangesGuard(isDirty: boolean) {
  const blocker = useBlocker(
    ({ currentLocation, nextLocation }) =>
      isDirty && currentLocation.pathname !== nextLocation.pathname,
  );

  const [manualPromptOpen, setManualPromptOpen] = useState(false);
  const resolverRef = useRef<((confirmed: boolean) => void) | null>(null);

  /** Resolves true immediately (no prompt) when not dirty — every call
   * site can call this unconditionally rather than checking isDirty
   * itself first. */
  const confirmDiscard = useCallback((): Promise<boolean> => {
    if (!isDirty) return Promise.resolve(true);
    return new Promise((resolve) => {
      resolverRef.current = resolve;
      setManualPromptOpen(true);
    });
  }, [isDirty]);

  const isOpen = blocker.state === "blocked" || manualPromptOpen;

  function handleConfirm() {
    if (blocker.state === "blocked") blocker.proceed();
    if (manualPromptOpen) {
      setManualPromptOpen(false);
      resolverRef.current?.(true);
      resolverRef.current = null;
    }
  }

  function handleCancel() {
    if (blocker.state === "blocked") blocker.reset();
    if (manualPromptOpen) {
      setManualPromptOpen(false);
      resolverRef.current?.(false);
      resolverRef.current = null;
    }
  }

  const guardElement = (
    <ConfirmDialog
      open={isOpen}
      onCancel={handleCancel}
      onConfirm={handleConfirm}
      title="Leave without saving?"
      description="You have unsaved changes. If you leave now, they'll be lost."
      confirmLabel="Leave"
      confirmPendingLabel="Leaving..."
    />
  );

  return { confirmDiscard, guardElement };
}
