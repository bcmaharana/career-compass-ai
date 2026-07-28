import { useCareerProfile, useUpdateCareerProfile } from "@/api/queries/career-profile";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { CollapseToggle } from "@/components/ui/collapse-toggle";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { Input } from "@/components/ui/input";
import { RenameSkillDialog } from "@/features/skill-intelligence/RenameSkillDialog";
import { getErrorMessage } from "@/lib/errors";
import { PencilLine, Plus, X } from "lucide-react";
import { type FormEvent, useState } from "react";

interface MySkillsSectionProps {
  cardBackground: "card" | "background";
}

/** Splits a comma-separated add-input into trimmed, non-empty names —
 * lets "Python, SQL, Docker" add three skills in one submit instead of
 * three separate round trips. */
function parseSkillNames(raw: string): string[] {
  return raw
    .split(",")
    .map((s) => s.trim())
    .filter((s) => s.length > 0);
}

/**
 * My Skills is literally CareerProfile.core_competencies — the same field
 * Core Competencies (career-profile page) edits, just a second, always-
 * in-sync view. Immediate-commit add/remove/rename (no Edit/Save toggle),
 * unlike Core Competencies' batch edit mode, matching Target Role Skill
 * Requirements' per-item UX. See ADR-005: the skill_intelligence catalog
 * (categories, proficiency levels, shared-catalog rename) was removed
 * entirely in favor of this plain free-text list — rename here only ever
 * edits this one list, not a globally shared row.
 */
export function MySkillsSection({ cardBackground }: MySkillsSectionProps) {
  const { data: profile } = useCareerProfile();
  const updateProfile = useUpdateCareerProfile();

  const [isOpen, setIsOpen] = useState(true);
  const [draft, setDraft] = useState("");
  const [deleteTarget, setDeleteTarget] = useState<string | null>(null);
  const [renameTarget, setRenameTarget] = useState<string | null>(null);
  const [renameName, setRenameName] = useState("");

  const skills = profile?.core_competencies ?? [];

  function persist(next: string[]) {
    updateProfile.mutate({
      headline: profile?.headline ?? null,
      summary: profile?.summary ?? null,
      core_competencies: next,
    });
  }

  function handleAdd(event: FormEvent) {
    event.preventDefault();
    const names = parseSkillNames(draft);
    if (names.length === 0) return;
    const next = [...skills];
    for (const name of names) {
      if (!next.some((s) => s.toLowerCase() === name.toLowerCase())) {
        next.push(name);
      }
    }
    if (next.length !== skills.length) persist(next);
    setDraft("");
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
    const collides = skills.some(
      (s) => s.toLowerCase() === trimmed.toLowerCase() && s.toLowerCase() !== renameTarget.toLowerCase(),
    );
    if (collides) return;
    persist(skills.map((s) => (s === renameTarget ? trimmed : s)));
    setRenameTarget(null);
  }

  return (
    <Card className={cardBackground === "background" ? "bg-background" : undefined}>
      <CardHeader className="flex-row items-center justify-between space-y-0">
        <CardTitle>My Skills</CardTitle>
        <div className="flex items-center gap-2">
          <form onSubmit={handleAdd} className="flex items-center gap-1.5">
            <Input
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              placeholder="Add existing skill(s)"
              aria-label="New skill(s), comma-separated"
              className="h-8 w-48"
            />
            <Button
              type="submit"
              variant="outline"
              size="sm"
              disabled={!draft.trim() || updateProfile.isPending}
            >
              <Plus className="h-4 w-4" />
              Add
            </Button>
          </form>
          <CollapseToggle isOpen={isOpen} onToggle={() => setIsOpen(!isOpen)} label="My Skills" />
        </div>
      </CardHeader>
      {isOpen && (
        <CardContent>
          {skills.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              No skills added yet — track your skill inventory here.
            </p>
          ) : (
            <div className="flex flex-wrap gap-1.5">
              {skills.map((skill) => (
                <Badge key={skill} variant="accent" className="gap-1">
                  {skill}
                  <button
                    type="button"
                    onClick={() => openRename(skill)}
                    aria-label={`Rename ${skill}`}
                  >
                    <PencilLine className="h-3 w-3" />
                  </button>
                  <button
                    type="button"
                    onClick={() => setDeleteTarget(skill)}
                    aria-label={`Remove ${skill}`}
                  >
                    <X className="h-3 w-3" />
                  </button>
                </Badge>
              ))}
            </div>
          )}
          {updateProfile.isError && (
            <p role="alert" className="mt-2 text-sm text-destructive">
              {getErrorMessage(updateProfile.error)}
            </p>
          )}
        </CardContent>
      )}

      <RenameSkillDialog
        open={renameTarget !== null}
        name={renameName}
        onNameChange={setRenameName}
        onSubmit={handleRenameSubmit}
        onClose={() => setRenameTarget(null)}
        isPending={updateProfile.isPending}
      />

      <ConfirmDialog
        open={deleteTarget !== null}
        onCancel={() => setDeleteTarget(null)}
        onConfirm={() => {
          if (deleteTarget) persist(skills.filter((s) => s !== deleteTarget));
          setDeleteTarget(null);
        }}
        title="Remove skill?"
        description={
          deleteTarget ? `Remove "${deleteTarget}" from your inventory? This can't be undone.` : ""
        }
        isPending={updateProfile.isPending}
      />
    </Card>
  );
}
