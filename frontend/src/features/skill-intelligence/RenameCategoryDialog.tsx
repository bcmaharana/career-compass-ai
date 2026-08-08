import { Button } from "@/components/ui/button";
import { Dialog } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { getErrorMessage } from "@/lib/errors";
import type { FormEvent } from "react";

interface RenameCategoryDialogProps {
  open: boolean;
  name: string;
  onNameChange: (value: string) => void;
  onSubmit: (event: FormEvent) => void;
  onClose: () => void;
  isPending: boolean;
  error?: unknown;
}

/**
 * Renames a whole category, not one skill — shared by Core Competencies
 * and My Skills (both edit CareerProfile.core_competencies). A category
 * is just a string on each item, not its own entity (no id, no
 * display_order — see lib/group-by-category.ts), so "renaming" it means
 * the caller rewrites every item currently carrying that category
 * string, not just this one field. If the new name collides with
 * another already-existing category, that's allowed through rather than
 * blocked — the natural "merge two categories by renaming one to the
 * other" behavior, unlike RenameSkillDialog's skill-name collision
 * guard (names are meant to be unique identifiers; categories are just
 * shared labels).
 */
export function RenameCategoryDialog({
  open,
  name,
  onNameChange,
  onSubmit,
  onClose,
  isPending,
  error,
}: RenameCategoryDialogProps) {
  return (
    <Dialog open={open} onClose={onClose} title="Rename category">
      <form className="flex flex-col gap-4" onSubmit={onSubmit}>
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="rename-category-name">Category name</Label>
          <Input
            id="rename-category-name"
            autoFocus
            required
            value={name}
            onChange={(e) => onNameChange(e.target.value)}
          />
          <p className="text-xs text-muted-foreground">
            Renames this category for every skill under it.
          </p>
        </div>
        <Button type="submit" disabled={isPending || !name.trim()}>
          {isPending ? "Saving..." : "Save"}
        </Button>
        {error != null && (
          <p role="alert" className="text-sm text-destructive">
            {getErrorMessage(error)}
          </p>
        )}
      </form>
    </Dialog>
  );
}
