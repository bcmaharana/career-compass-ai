import { useCareerProfile, useUpdateCareerProfile } from "@/api/queries/career-profile";
import type { components } from "@/api/schema.gen";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { CollapseToggle } from "@/components/ui/collapse-toggle";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { MoveButtons } from "@/components/ui/move-buttons";
import { RenameCategoryDialog } from "@/features/skill-intelligence/RenameCategoryDialog";
import { RenameSkillDialog } from "@/features/skill-intelligence/RenameSkillDialog";
import { useProfileScope } from "@/features/career-profile/profile-scope";
import type { SectionOrderProps } from "@/features/career-profile/section-order";
import { getErrorMessage } from "@/lib/errors";
import { groupCompetenciesByCategoryWithMoveIndex, moveCategoryGroup } from "@/lib/group-by-category";
import { ArrowDown, ArrowUp, Eraser, PencilLine, Plus, X } from "lucide-react";
import { type FormEvent, useState } from "react";

type CoreCompetency = components["schemas"]["CoreCompetencyPayload"];

/**
 * Split out of ProfileHeader.tsx into its own card, shown above Career
 * Highlights, per explicit request. Shares the same `useCareerProfile`
 * cache and `useUpdateCareerProfile` mutation as ProfileHeader but owns
 * its own edit state independently, the same way every other
 * career-profile section does.
 *
 * Edit-mode gated: an "Edit"/"Done" toggle in the header shows/hides
 * every per-item pencil/delete icon, the category-rename pencil, and
 * the category move-arrows — off by default (a clean read view). "+Add"
 * is deliberately NOT gated by Edit mode — adding something new is a
 * distinct, low-risk action from editing/deleting what's already there.
 * "Clear" (whole-section wipe) also stays outside Edit mode — it's a
 * separate, already ConfirmDialog-gated destructive action.
 *
 * "+Add" opens the same RenameSkillDialog used for editing an existing
 * item (name + category form) rather than a free-text input — one
 * shared dialog, distinguished by `dialogTarget.mode`.
 *
 * Each competency carries an optional `category` (e.g. "Agile &
 * Scaling") — a plain per-item attribute, not a link into a shared
 * catalog (ADR-005 removed that entirely). Competencies are grouped and
 * displayed under their category as a heading (groupCompetenciesByCategory,
 * lib/group-by-category.ts — shared with MySkillsSection.tsx, since both
 * edit the same field); items with no category land in a trailing
 * "Uncategorized" group. Renaming a category (RenameCategoryDialog) is a
 * distinct action from renaming one skill — it rewrites every item
 * currently carrying that category string.
 */
export function CoreCompetenciesSection({
  onMoveUp,
  onMoveDown,
  isFirst,
  isLast,
  moveDisabled,
  cardBackground,
}: SectionOrderProps) {
  const scope = useProfileScope();
  const { data: profile } = useCareerProfile(scope);
  const updateProfile = useUpdateCareerProfile(scope);

  const [isOpen, setIsOpen] = useState(false);
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
  const [clearSectionOpen, setClearSectionOpen] = useState(false);

  const competencies = profile?.core_competencies ?? [];
  const categoryOptions = Array.from(
    new Set(competencies.map((c) => c.category).filter((c): c is string => Boolean(c))),
  ).sort((a, b) => a.localeCompare(b));
  const { groups, categorizedCount } = groupCompetenciesByCategoryWithMoveIndex(competencies);

  function persist(next: CoreCompetency[]) {
    // headline/summary are resent unchanged from the shared cache —
    // unlike core_competencies itself, the backend overwrites
    // headline/summary unconditionally on every call (see
    // CareerProfileService.update), so omitting them here would wipe
    // them out rather than leave them alone.
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

  function openEditDialog(item: CoreCompetency) {
    setDialogTarget({ mode: "edit", originalName: item.name });
    setFormName(item.name);
    setFormCategory(item.category ?? "");
  }

  function handleDialogSubmit(event: FormEvent) {
    event.preventDefault();
    if (!dialogTarget) return;
    const trimmed = formName.trim();
    if (!trimmed) return;
    const collides = competencies.some(
      (c) =>
        c.name.toLowerCase() === trimmed.toLowerCase() &&
        c.name.toLowerCase() !== dialogTarget.originalName?.toLowerCase(),
    );
    if (collides) return;
    const trimmedCategory = formCategory.trim();
    const nextItem: CoreCompetency = { name: trimmed, category: trimmedCategory || null };
    if (dialogTarget.mode === "add") {
      persist([...competencies, nextItem]);
    } else {
      persist(competencies.map((c) => (c.name === dialogTarget.originalName ? nextItem : c)));
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
      competencies.map((c) =>
        c.category === renameCategoryTarget ? { ...c, category: trimmed } : c,
      ),
    );
    setRenameCategoryTarget(null);
  }

  return (
    <Card className={cardBackground === "background" ? "bg-background" : undefined}>
      <CardHeader className="flex-row items-start justify-between space-y-0">
        <CardTitle>Core Competencies</CardTitle>
        <div className="flex items-start gap-1">
          <Button variant="ghost" size="sm" onClick={openAddDialog}>
            <Plus className="h-4 w-4" />
            Add
          </Button>
          <Button variant="ghost" size="sm" onClick={() => setIsEditMode((v) => !v)}>
            {isEditMode ? "Done" : "Edit"}
          </Button>
          {competencies.length > 0 && (
            <Button variant="ghost" size="sm" onClick={() => setClearSectionOpen(true)}>
              <Eraser className="h-4 w-4" />
              Clear
            </Button>
          )}
          <CollapseToggle
            isOpen={isOpen}
            onToggle={() => setIsOpen(!isOpen)}
            label="Core Competencies"
          />
          <MoveButtons
            onMoveUp={onMoveUp}
            onMoveDown={onMoveDown}
            isFirst={isFirst}
            isLast={isLast}
            disabled={moveDisabled}
          />
        </div>
      </CardHeader>
      {isOpen && (
        <CardContent className="flex flex-col gap-3">
          {competencies.length > 0 ? (
            <div className="flex flex-col gap-3">
              {groups.map((group) => (
                <div key={group.category ?? "__uncategorized"} className="flex flex-col gap-1.5">
                  <div className="flex items-center gap-1">
                    {isEditMode && group.category !== null && (
                      <MoveButtons
                        onMoveUp={() =>
                          persist(moveCategoryGroup(competencies, group.category as string, "up"))
                        }
                        onMoveDown={() =>
                          persist(moveCategoryGroup(competencies, group.category as string, "down"))
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
                    {group.items.map((c) => (
                      <Badge key={c.name} variant="accent" className="gap-1">
                        {c.name}
                        {isEditMode && (
                          <>
                            <button
                              type="button"
                              onClick={() => openEditDialog(c)}
                              aria-label={`Edit ${c.name}`}
                            >
                              <PencilLine className="h-3 w-3" />
                            </button>
                            <button
                              type="button"
                              onClick={() => setDeleteTarget(c.name)}
                              aria-label={`Remove ${c.name}`}
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
          ) : (
            <p className="text-sm text-muted-foreground">No competencies added yet.</p>
          )}
          {updateProfile.isError && (
            <p role="alert" className="text-sm text-destructive">
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
        title={dialogTarget?.mode === "add" ? "Add competency" : "Edit competency"}
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
          if (deleteTarget) persist(competencies.filter((c) => c.name !== deleteTarget));
          setDeleteTarget(null);
        }}
        title="Remove competency?"
        description={
          deleteTarget
            ? `Remove "${deleteTarget}" from your core competencies? This can't be undone.`
            : ""
        }
        isPending={updateProfile.isPending}
      />

      <ConfirmDialog
        open={clearSectionOpen}
        onCancel={() => setClearSectionOpen(false)}
        onConfirm={() => {
          persist([]);
          setClearSectionOpen(false);
        }}
        title="Clear Core Competencies?"
        description="Remove every core competency from your profile? This can't be undone."
        isPending={updateProfile.isPending}
        confirmLabel="Clear"
        confirmPendingLabel="Clearing..."
      />
    </Card>
  );
}
