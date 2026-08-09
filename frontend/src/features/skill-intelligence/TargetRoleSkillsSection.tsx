import {
  useAddRequiredSkill,
  useRemoveRequiredSkill,
  useRenameRequiredSkill,
  useTargetRoles,
} from "@/api/queries/career-profile";
import type { components } from "@/api/schema.gen";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ACTION_BUTTON_ROW_GAP } from "@/components/ui/button-variants";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { CollapseToggle } from "@/components/ui/collapse-toggle";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { CopyButton } from "@/components/ui/copy-button";
import { Input } from "@/components/ui/input";
import { itemAlternateClass } from "@/features/career-profile/section-order";
import { RenameSkillDialog } from "@/features/skill-intelligence/RenameSkillDialog";
import { getErrorMessage } from "@/lib/errors";
import { cn } from "@/lib/utils";
import { PencilLine, Plus, X } from "lucide-react";
import { type FormEvent, useState } from "react";

type TargetRole = components["schemas"]["TargetRoleResponse"];

interface TargetRoleSkillsSectionProps {
  cardBackground: "card" | "background";
}

/** Splits a comma-separated add-input into trimmed, non-empty names —
 * lets "Python, SQL, Docker" add three requirements in one submit. */
function parseSkillNames(raw: string): string[] {
  return raw
    .split(",")
    .map((s) => s.trim())
    .filter((s) => s.length > 0);
}

/**
 * Requirements editor for one target role — its own component (rather
 * than a loop inside TargetRoleSkillsSection) so its local add/rename/
 * delete state is scoped per role rather than shared across the whole
 * list.
 *
 * `required_skills` is a plain free-text list on TargetRole itself (see
 * ADR-005) — the skill_intelligence catalog this used to link against
 * (categories, proficiency) was removed entirely. Rename edits this
 * role's own list in place (preserving position), not a shared catalog
 * row, so it can't affect any other role's requirements.
 */
function TargetRoleRequirementsRow({
  targetRole,
  rowClassName,
}: {
  targetRole: TargetRole;
  rowClassName: string;
}) {
  const addRequiredSkill = useAddRequiredSkill();
  const removeRequiredSkill = useRemoveRequiredSkill();
  const renameRequiredSkill = useRenameRequiredSkill();

  const [draft, setDraft] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<string | null>(null);
  const [renameTarget, setRenameTarget] = useState<string | null>(null);
  const [renameName, setRenameName] = useState("");

  async function handleAdd(event: FormEvent) {
    event.preventDefault();
    const names = parseSkillNames(draft);
    if (names.length === 0) return;
    setIsSubmitting(true);
    try {
      // Sequential, not Promise.all: each add reads-then-writes the same
      // required_skills array server-side, so firing them concurrently
      // could race and lose one of the additions.
      for (const name of names) {
        await addRequiredSkill.mutateAsync({ targetRoleId: targetRole.id, name });
      }
      setDraft("");
    } catch {
      // Error surfaced via addRequiredSkill.isError below.
    } finally {
      setIsSubmitting(false);
    }
  }

  function openRename(skill: string) {
    setRenameTarget(skill);
    setRenameName(skill);
  }

  function handleRenameSubmit(event: FormEvent) {
    event.preventDefault();
    if (!renameTarget) return;
    const trimmed = renameName.trim();
    if (!trimmed) return;
    renameRequiredSkill
      .mutateAsync({ targetRoleId: targetRole.id, oldName: renameTarget, newName: trimmed })
      .then(() => setRenameTarget(null))
      .catch(() => {});
  }

  return (
    <div className={cn("flex flex-col gap-3 rounded-md border border-border p-4", rowClassName)}>
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <Badge variant="accent">{targetRole.tag}</Badge>
          <p className="font-medium">
            {targetRole.role_name}{" "}
            <span className="text-sm font-normal italic text-muted-foreground">
              ({targetRole.required_skills.length})
            </span>
          </p>
        </div>
        <div className={cn("flex items-center", ACTION_BUTTON_ROW_GAP)}>
          <form onSubmit={handleAdd} className="flex items-center gap-1.5">
            <Input
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              placeholder="Add target role skill(s)"
              aria-label={`New required skill(s) for ${targetRole.role_name}, comma-separated`}
              className="h-8 w-48"
            />
            <Button
              type="submit"
              variant="ghost"
              size="sm"
              disabled={!draft.trim() || isSubmitting}
            >
              <Plus className="h-4 w-4" />
              Add
            </Button>
          </form>
          <CopyButton
            text={targetRole.required_skills.join(", ")}
            disabled={targetRole.required_skills.length === 0}
            variant="ghost"
          />
        </div>
      </div>

      <div className="flex flex-wrap gap-1.5">
        {targetRole.required_skills.length === 0 && (
          <p className="text-sm text-muted-foreground">No required skills linked yet.</p>
        )}
        {targetRole.required_skills.map((skill) => (
          <span
            key={skill}
            className="flex items-center gap-1 rounded-full bg-muted px-2.5 py-0.5 text-xs font-medium text-muted-foreground"
          >
            {skill}
            <button
              type="button"
              onClick={() => openRename(skill)}
              aria-label={`Rename ${skill}`}
              className="hover:text-foreground"
            >
              <PencilLine className="h-3 w-3" />
            </button>
            <button
              type="button"
              onClick={() => setDeleteTarget(skill)}
              aria-label={`Remove ${skill} requirement`}
              className="hover:text-destructive"
            >
              <X className="h-3 w-3" />
            </button>
          </span>
        ))}
      </div>

      {addRequiredSkill.isError && (
        <p role="alert" className="text-xs text-destructive">
          {getErrorMessage(addRequiredSkill.error)}
        </p>
      )}

      <RenameSkillDialog
        open={renameTarget !== null}
        name={renameName}
        onNameChange={setRenameName}
        onSubmit={handleRenameSubmit}
        onClose={() => setRenameTarget(null)}
        isPending={renameRequiredSkill.isPending}
        error={renameRequiredSkill.isError ? renameRequiredSkill.error : undefined}
      />

      <ConfirmDialog
        open={deleteTarget !== null}
        onCancel={() => setDeleteTarget(null)}
        onConfirm={() => {
          if (deleteTarget) {
            removeRequiredSkill.mutate({ targetRoleId: targetRole.id, name: deleteTarget });
          }
          setDeleteTarget(null);
        }}
        title="Remove this requirement?"
        description={
          deleteTarget
            ? `Remove "${deleteTarget}" as a requirement for ${targetRole.role_name}? This can't be undone.`
            : ""
        }
        isPending={removeRequiredSkill.isPending}
      />
    </div>
  );
}

export function TargetRoleSkillsSection({ cardBackground }: TargetRoleSkillsSectionProps) {
  const { data: targetRoles } = useTargetRoles();
  const [isOpen, setIsOpen] = useState(true);

  return (
    <Card className={cardBackground === "background" ? "bg-background" : undefined}>
      <CardHeader className="flex-row items-start justify-between space-y-0">
        <CardTitle>Target Role Skill Requirements</CardTitle>
        <CollapseToggle
          isOpen={isOpen}
          onToggle={() => setIsOpen(!isOpen)}
          label="Target Role Skill Requirements"
        />
      </CardHeader>
      {isOpen && (
        <CardContent className="flex flex-col gap-3">
          {targetRoles?.length === 0 && (
            <p className="text-sm text-muted-foreground">
              Add a target role in the Career Profile page's Target Roles widget, then link the
              skills it requires here.
            </p>
          )}
          {targetRoles?.map((role, index) => (
            <TargetRoleRequirementsRow
              key={role.id}
              targetRole={role}
              rowClassName={itemAlternateClass(cardBackground, index)}
            />
          ))}
        </CardContent>
      )}
    </Card>
  );
}
