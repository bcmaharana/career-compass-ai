import { Button } from "@/components/ui/button";
import { Dialog } from "@/components/ui/dialog";

interface ConfirmDialogProps {
  open: boolean;
  onCancel: () => void;
  onConfirm: () => void;
  title: string;
  description: string;
  isPending?: boolean;
  /** Defaults to "Delete"/"Deleting..." — override for non-delete
   * destructive actions (e.g. "Clear"/"Clearing..."). */
  confirmLabel?: string;
  confirmPendingLabel?: string;
}

/**
 * Shared "are you sure?" confirmation, built on the existing Dialog
 * primitive rather than the browser's native confirm() — matches this
 * project's design system instead of an unstyled OS popup, and matches
 * the Escape-to-close / no-backdrop-click behavior every other dialog
 * on this page already has.
 *
 * Every career-profile section's delete button used to call its delete
 * mutation directly on click — a stray click on the trash icon
 * permanently deleted the item with no way back. This is the fix,
 * applied consistently everywhere a delete button exists.
 */
export function ConfirmDialog({
  open,
  onCancel,
  onConfirm,
  title,
  description,
  isPending,
  confirmLabel = "Delete",
  confirmPendingLabel = "Deleting...",
}: ConfirmDialogProps) {
  return (
    <Dialog open={open} onClose={onCancel} title={title}>
      <p className="text-sm text-muted-foreground">{description}</p>
      <div className="mt-4 flex justify-end gap-2">
        <Button variant="ghost" onClick={onCancel} disabled={isPending}>
          Cancel
        </Button>
        <Button variant="destructive" onClick={onConfirm} disabled={isPending}>
          {isPending ? confirmPendingLabel : confirmLabel}
        </Button>
      </div>
    </Dialog>
  );
}
