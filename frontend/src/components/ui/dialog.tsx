import { RAINBOW_GRADIENT_HOVER_BG } from "@/components/ui/button-variants";
import { cn } from "@/lib/utils";
import { X } from "lucide-react";
import type { ReactNode } from "react";
import { useEffect } from "react";

interface DialogProps {
  open: boolean;
  onClose: () => void;
  title: string;
  description?: string;
  children: ReactNode;
  className?: string;
}

/**
 * A minimal controlled modal — deliberately not built on Radix or any
 * other headless-UI library, matching this project's preference for a
 * small dependency footprint (see package.json). Closes on Escape or
 * the explicit close button only — not on backdrop click.
 *
 * Backdrop-click-to-close was removed deliberately: dragging a
 * <textarea>'s native resize handle can end with the pointer outside
 * the dialog's bounds, and some browsers synthesize the resulting
 * "click" event on whatever element is under the pointer at that point
 * (the backdrop) rather than the element the interaction started on —
 * closing the dialog mid-edit even though the user never intended to
 * dismiss it. Reported as "expanding a textbox kicks me out of edit
 * mode" — reproducible with the textarea's resize handle specifically,
 * not a general click-outside case.
 *
 * Capped to a fraction of the viewport height (max-h-[85vh]), with the
 * header (title/description/close button) staying fixed and only the
 * body (`children`) scrolling internally — direct 2026-08-20 report:
 * editing an Experience entry with a long multi-bullet description grew
 * the dialog taller than the viewport with no way to reach the Save
 * button or even see the box's own bottom edge, since neither this
 * component nor its backdrop had any max-height/overflow handling at
 * all before this. The header staying fixed (not scrolling away with
 * the rest) keeps the close (X) button reachable regardless of how long
 * the body grows.
 */
export function Dialog({ open, onClose, title, description, children, className }: DialogProps) {
  useEffect(() => {
    if (!open) return;
    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") onClose();
    }
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="dialog-title"
        className={cn(
          "flex max-h-[85vh] w-full max-w-lg flex-col rounded-lg border border-border bg-card shadow-card",
          className,
        )}
      >
        <div className="flex shrink-0 items-start justify-between px-6 pb-4 pt-6">
          <div>
            <h2 id="dialog-title" className="font-display text-lg font-semibold">
              {title}
            </h2>
            {description && <p className="mt-1 text-sm text-muted-foreground">{description}</p>}
          </div>
          <button
            onClick={onClose}
            aria-label="Close"
            className={cn(
              "rounded-md p-1 text-muted-foreground hover:text-primary",
              RAINBOW_GRADIENT_HOVER_BG,
            )}
          >
            <X className="h-3.5 w-3.5" />
          </button>
        </div>
        <div className="overflow-y-auto px-6 pb-6">{children}</div>
      </div>
    </div>
  );
}
