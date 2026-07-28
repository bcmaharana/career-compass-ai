import { Button } from "@/components/ui/button";
import { Dialog } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { getErrorMessage } from "@/lib/errors";
import type { FormEvent } from "react";

interface RenameSkillDialogProps {
  open: boolean;
  name: string;
  onNameChange: (value: string) => void;
  onSubmit: (event: FormEvent) => void;
  onClose: () => void;
  isPending: boolean;
  error?: unknown;
}

/**
 * Generic inline-rename dialog reused by both My Skills and Target Role
 * Skill Requirements — each is just a plain string in its own list (no
 * shared catalog since ADR-005), so renaming only ever affects the one
 * list it's called from, unlike the old catalog-wide rename this replaced.
 */
export function RenameSkillDialog({
  open,
  name,
  onNameChange,
  onSubmit,
  onClose,
  isPending,
  error,
}: RenameSkillDialogProps) {
  return (
    <Dialog open={open} onClose={onClose} title="Rename skill">
      <form className="flex flex-col gap-4" onSubmit={onSubmit}>
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="rename-skill-name">Skill name</Label>
          <Input
            id="rename-skill-name"
            autoFocus
            required
            value={name}
            onChange={(e) => onNameChange(e.target.value)}
          />
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
