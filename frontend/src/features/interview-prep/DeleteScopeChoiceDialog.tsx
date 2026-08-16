import { Button } from "@/components/ui/button";
import { Dialog } from "@/components/ui/dialog";

/**
 * Shown instead of the plain ConfirmDialog when the item being deleted
 * is tagged to more than one scope — a real user request: "While
 * deleting the item, system asks if this needs to be deleted from
 * everywhere or just from the current scope." A single-scope item
 * skips this and uses the plain ConfirmDialog as before, since
 * "remove from its only scope" and "delete everywhere" are the same
 * outcome there.
 */
export function DeleteScopeChoiceDialog({
  open,
  onCancel,
  onRemoveFromScope,
  onDeleteEverywhere,
  itemLabel,
  scopeLabel,
  isPending,
}: {
  open: boolean;
  onCancel: () => void;
  onRemoveFromScope: () => void;
  onDeleteEverywhere: () => void;
  itemLabel: string;
  scopeLabel: string;
  isPending?: boolean;
}) {
  return (
    <Dialog open={open} onClose={onCancel} title="Remove this item?">
      <p className="text-sm text-muted-foreground">
        &ldquo;{itemLabel}&rdquo; is tagged to more than one scope. Remove it from just{" "}
        <span className="font-medium text-foreground">{scopeLabel}</span>, or delete it
        everywhere it&apos;s tagged?
      </p>
      <div className="mt-4 flex flex-col gap-2 sm:flex-row sm:justify-end">
        <Button variant="ghost" onClick={onCancel} disabled={isPending}>
          Cancel
        </Button>
        <Button variant="outline" onClick={onRemoveFromScope} disabled={isPending}>
          Remove from {scopeLabel} only
        </Button>
        <Button variant="destructive" onClick={onDeleteEverywhere} disabled={isPending}>
          Delete everywhere
        </Button>
      </div>
    </Dialog>
  );
}
