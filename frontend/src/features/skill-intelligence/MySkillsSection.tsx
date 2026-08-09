import { useCareerProfile, useUpdateCareerProfile } from "@/api/queries/career-profile";
import type { components } from "@/api/schema.gen";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ACTION_BUTTON_ROW_GAP } from "@/components/ui/button-variants";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { CollapseToggle } from "@/components/ui/collapse-toggle";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { CopyButton } from "@/components/ui/copy-button";
import { MoveButtons } from "@/components/ui/move-buttons";
import { RenameCategoryDialog } from "@/features/skill-intelligence/RenameCategoryDialog";
import { RenameSkillDialog } from "@/features/skill-intelligence/RenameSkillDialog";
import { getErrorMessage } from "@/lib/errors";
import { groupCompetenciesByCategoryWithMoveIndex, moveCategoryGroup } from "@/lib/group-by-category";
import { cn } from "@/lib/utils";
import { ArrowDown, ArrowUp, PencilLine, Plus, X } from "lucide-react";
import { type FormEvent, useState } from "react";

type CoreCompetency = components["schemas"]["CoreCompetencyPayload"];

interface MySkillsSectionProps {
  cardBackground: "card" | "background";
}

/** Must match UpdateCareerProfileRequest.core_competencies' max_length
 * in backend/app/api/v1/career_profile/schemas.py — shown here only for
 * the "(current/max)" count in the card title, not enforced client-side
 * (the server is still the source of truth; this is display only). */
const MAX_SKILLS = 150;

/**
 * My Skills is literally CareerProfile.core_competencies — the same field
 * Core Competencies (career-profile page) edits, just a second, always-
 * in-sync view. See CoreCompetenciesSection.tsx's own docstring for the
 * full shape shared between the two: Edit-mode-gated pencil/delete icons
 * and category rename/move (off by default, "+Add" always visible
 * regardless), category grouping (groupCompetenciesByCategory,
 * lib/group-by-category.ts), and the same shared RenameSkillDialog
 * (add + edit) / RenameCategoryDialog — kept identical between the two
 * views since having two different UX conventions for the same field
 * was a real point of user confusion before.
 *
 * Previously also had a second, dropdown-based quick-add sourced from
 * target roles' required_skills, kept deliberately alongside "+Add" as
 * a discoverability aid — removed on explicit follow-up feedback once
 * live: two differently-shaped "add a skill" controls next to each
 * other read as confusing/redundant in practice, "+Add" alone is the
 * one way to add a skill here now, same as Core Competencies.
 */
export function MySkillsSection({ cardBackground }: MySkillsSectionProps) {
  const { data: profile } = useCareerProfile();
  const updateProfile = useUpdateCareerProfile();

  const [isOpen, setIsOpen] = useState(true);
  const [isEditMode, setIsEditMode] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<string | null>(null);
  const [dialogTarget, setDialogTarget] = useState<{
    mode: "add" | "edit";
    originalName: string | null;
  } | null>(null);
  const [formName, setFormName] = useState("");
  const [formCategory, setFormCategory] = useState("");
  const [renameCategoryTarget, setRenameCategoryTarget] = useState<string | null>(null);
  const [renameCategoryValue, setRenameCategoryValue] = useState("");

  const skills = profile?.core_competencies ?? [];
  const categoryOptions = Array.from(
    new Set(skills.map((s) => s.category).filter((c): c is string => Boolean(c))),
  ).sort((a, b) => a.localeCompare(b));
  const { groups, categorizedCount } = groupCompetenciesByCategoryWithMoveIndex(skills);

  function persist(next: CoreCompetency[]) {
    updateProfile.mutate({
      headline: profile?.headline ?? null,
      summary: profile?.summary ?? null,
      core_competencies: next,
    });
  }

  function openAddDialog() {
    setDialogTarget({ mode: "add", originalName: null });
    setFormName("");
    setFormCategory("");
  }

  function openEditDialog(skill: CoreCompetency) {
    setDialogTarget({ mode: "edit", originalName: skill.name });
    setFormName(skill.name);
    setFormCategory(skill.category ?? "");
  }

  function handleDialogSubmit(event: FormEvent) {
    event.preventDefault();
    if (!dialogTarget) return;
    const trimmed = formName.trim();
    if (!trimmed) return;
    const collides = skills.some(
      (s) =>
        s.name.toLowerCase() === trimmed.toLowerCase() &&
        s.name.toLowerCase() !== dialogTarget.originalName?.toLowerCase(),
    );
    if (collides) return;
    const trimmedCategory = formCategory.trim();
    const nextItem: CoreCompetency = { name: trimmed, category: trimmedCategory || null };
    if (dialogTarget.mode === "add") {
      persist([...skills, nextItem]);
    } else {
      persist(skills.map((s) => (s.name === dialogTarget.originalName ? nextItem : s)));
    }
    setDialogTarget(null);
  }

  function openRenameCategory(category: string) {
    setRenameCategoryTarget(category);
    setRenameCategoryValue(category);
  }

  function handleRenameCategorySubmit(event: FormEvent) {
    event.preventDefault();
    if (!renameCategoryTarget) return;
    const trimmed = renameCategoryValue.trim();
    if (!trimmed) return;
    persist(
      skills.map((s) => (s.category === renameCategoryTarget ? { ...s, category: trimmed } : s)),
    );
    setRenameCategoryTarget(null);
  }

  return (
    <Card className={cardBackground === "background" ? "bg-background" : undefined}>
      <CardHeader className="flex-row items-start justify-between space-y-0">
        <CardTitle>
          My Skills{" "}
          <span className="text-sm font-normal italic text-muted-foreground">
            ({skills.length}/{MAX_SKILLS})
          </span>
        </CardTitle>
        <div className={cn("flex items-start", ACTION_BUTTON_ROW_GAP)}>
          <Button variant="ghost" size="sm" onClick={openAddDialog}>
            <Plus className="h-4 w-4" />
            Add
          </Button>
          <Button variant="ghost" size="sm" onClick={() => setIsEditMode((v) => !v)}>
            {isEditMode ? "Done" : "Edit"}
          </Button>
          <CopyButton
            text={skills.map((s) => s.name).join(", ")}
            disabled={skills.length === 0}
            variant="ghost"
          />
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
            <div className="flex flex-col gap-3">
              {groups.map((group) => (
                <div key={group.category ?? "__uncategorized"} className="flex flex-col gap-1.5">
                  <div className="flex items-center gap-1">
                    {isEditMode && group.category !== null && (
                      <MoveButtons
                        onMoveUp={() =>
                          persist(moveCategoryGroup(skills, group.category as string, "up"))
                        }
                        onMoveDown={() =>
                          persist(moveCategoryGroup(skills, group.category as string, "down"))
                        }
                        isFirst={group.moveIndex === 0}
                        isLast={group.moveIndex === categorizedCount - 1}
                        label={`${group.category} category`}
                        orientation="horizontal"
                        upIcon={ArrowUp}
                        downIcon={ArrowDown}
                      />
                    )}
                    <p className="text-sm font-semibold text-foreground">
                      {group.category ?? "Uncategorized"}:
                    </p>
                    {isEditMode && group.category !== null && (
                      <button
                        type="button"
                        onClick={() => openRenameCategory(group.category as string)}
                        aria-label={`Rename ${group.category} category`}
                      >
                        <PencilLine className="h-3.5 w-3.5 text-muted-foreground" />
                      </button>
                    )}
                  </div>
                  <div className="flex flex-wrap gap-1.5">
                    {group.items.map((skill) => (
                      <Badge key={skill.name} variant="accent" className="gap-1">
                        {skill.name}
                        {isEditMode && (
                          <>
                            <button
                              type="button"
                              onClick={() => openEditDialog(skill)}
                              aria-label={`Edit ${skill.name}`}
                            >
                              <PencilLine className="h-3 w-3" />
                            </button>
                            <button
                              type="button"
                              onClick={() => setDeleteTarget(skill.name)}
                              aria-label={`Remove ${skill.name}`}
                            >
                              <X className="h-3 w-3" />
                            </button>
                          </>
                        )}
                      </Badge>
                    ))}
                  </div>
                </div>
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
        open={dialogTarget !== null}
        name={formName}
        onNameChange={setFormName}
        category={formCategory}
        onCategoryChange={setFormCategory}
        categoryOptions={categoryOptions}
        onSubmit={handleDialogSubmit}
        onClose={() => setDialogTarget(null)}
        isPending={updateProfile.isPending}
        title={dialogTarget?.mode === "add" ? "Add skill" : "Edit skill"}
        submitLabel={dialogTarget?.mode === "add" ? "Add" : "Save"}
      />

      <RenameCategoryDialog
        open={renameCategoryTarget !== null}
        name={renameCategoryValue}
        onNameChange={setRenameCategoryValue}
        onSubmit={handleRenameCategorySubmit}
        onClose={() => setRenameCategoryTarget(null)}
        isPending={updateProfile.isPending}
      />

      <ConfirmDialog
        open={deleteTarget !== null}
        onCancel={() => setDeleteTarget(null)}
        onConfirm={() => {
          if (deleteTarget) persist(skills.filter((s) => s.name !== deleteTarget));
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
