import {
  useAddKeyAchievement,
  useClearKeyAchievements,
  useKeyAchievements,
  useDeleteKeyAchievement,
  useMoveKeyAchievement,
  useUpdateKeyAchievement,
} from "@/api/queries/career-profile";
import type { components } from "@/api/schema.gen";
import { Button } from "@/components/ui/button";
import { ACTION_BUTTON_ROW_GAP } from "@/components/ui/button-variants";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { CollapseToggle } from "@/components/ui/collapse-toggle";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { Dialog } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { MoveButtons } from "@/components/ui/move-buttons";
import { Select } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { useProfileScope } from "@/features/career-profile/profile-scope";
import { ResumeIncludeToggle } from "@/features/career-profile/ResumeIncludeToggle";
import { itemAlternateClass, type SectionOrderProps } from "@/features/career-profile/section-order";
import { formatDisplayDate } from "@/lib/date-format";
import { getErrorMessage } from "@/lib/errors";
import { cn } from "@/lib/utils";
import { Eraser, Pencil, Plus, Trash2 } from "lucide-react";
import { type FormEvent, useState } from "react";

type KeyAchievement = components["schemas"]["KeyAchievementResponse"];

interface FormState {
  title: string;
  company: string;
  description: string;
  occurred_on: string;
  include_in_resume: boolean;
}

const EMPTY_FORM: FormState = {
  title: "",
  company: "",
  description: "",
  occurred_on: "",
  include_in_resume: true,
};

function toFormState(achievement: KeyAchievement): FormState {
  return {
    title: achievement.title,
    company: achievement.company ?? "",
    description: achievement.description ?? "",
    occurred_on: achievement.occurred_on ?? "",
    include_in_resume: achievement.include_in_resume,
  };
}

export function KeyAchievementsSection({
  onMoveUp,
  onMoveDown,
  isFirst,
  isLast,
  moveDisabled,
  cardBackground,
  resumeIncluded,
  onToggleResumeIncluded,
  resumeToggleDisabled,
}: SectionOrderProps) {
  const scope = useProfileScope();
  const { data: achievements, isLoading } = useKeyAchievements(scope);
  const addAchievement = useAddKeyAchievement(scope);
  const updateAchievement = useUpdateKeyAchievement(scope);
  const deleteAchievement = useDeleteKeyAchievement(scope);
  const clearAchievements = useClearKeyAchievements(scope);
  const moveAchievement = useMoveKeyAchievement(scope);
  const { data: masterAchievements } = useKeyAchievements(null);

  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [form, setForm] = useState<FormState>(EMPTY_FORM);
  const [isOpen, setIsOpen] = useState(false);
  const [isEditMode, setIsEditMode] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<KeyAchievement | null>(null);
  const [clearSectionOpen, setClearSectionOpen] = useState(false);

  function openAddDialog() {
    setEditingId(null);
    setForm(EMPTY_FORM);
    setDialogOpen(true);
  }

  function openEditDialog(achievement: KeyAchievement) {
    setEditingId(achievement.id);
    setForm(toFormState(achievement));
    setDialogOpen(true);
  }

  function copyFromMaster(achievementId: string) {
    const source = masterAchievements?.find((a) => a.id === achievementId);
    if (source) setForm(toFormState(source));
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const body = {
      title: form.title,
      company: form.company || null,
      description: form.description || null,
      occurred_on: form.occurred_on || null,
      include_in_resume: form.include_in_resume,
    };
    const mutation = editingId
      ? updateAchievement.mutateAsync({ id: editingId, body })
      : addAchievement.mutateAsync(body);
    mutation
      .then(() => {
        setDialogOpen(false);
        if (!editingId) setIsOpen(true);
      })
      .catch(() => {});
  }

  function toggleItemResume(achievement: KeyAchievement, include: boolean) {
    updateAchievement.mutate({
      id: achievement.id,
      body: {
        title: achievement.title,
        company: achievement.company,
        description: achievement.description,
        occurred_on: achievement.occurred_on,
        include_in_resume: include,
      },
    });
  }

  const isSaving = addAchievement.isPending || updateAchievement.isPending;
  const saveError = addAchievement.error ?? updateAchievement.error;

  return (
    <Card className={cardBackground === "background" ? "bg-background" : undefined}>
      <CardHeader className="flex-row items-start justify-between space-y-0">
        <CardTitle>Key Achievements</CardTitle>
        <div className={cn("flex items-start", ACTION_BUTTON_ROW_GAP)}>
          <ResumeIncludeToggle
            checked={resumeIncluded}
            onCheckedChange={onToggleResumeIncluded}
            disabled={resumeToggleDisabled}
            label="the Key Achievements section"
          />
          <Button variant="ghost" size="sm" onClick={openAddDialog}>
            <Plus className="h-4 w-4" />
            Add
          </Button>
          <Button variant="ghost" size="sm" onClick={() => setIsEditMode((v) => !v)}>
            {isEditMode ? "Done" : "Edit"}
          </Button>
          {!!achievements?.length && (
            <Button variant="ghost" size="sm" onClick={() => setClearSectionOpen(true)}>
              <Eraser className="h-4 w-4" />
              Clear
            </Button>
          )}
          <CollapseToggle
            isOpen={isOpen}
            onToggle={() => setIsOpen(!isOpen)}
            label="Key Achievements"
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
        {isLoading && <p className="text-sm text-muted-foreground">Loading...</p>}
        {achievements?.length === 0 && (
          <p className="text-sm text-muted-foreground">
            No achievements added yet — concrete wins and results worth calling out on their own.
          </p>
        )}
        {achievements?.map((achievement, index) => (
          <div
            key={achievement.id}
            className={cn(
              "flex items-start justify-between gap-4 rounded-md border border-border p-4",
              itemAlternateClass(cardBackground, index),
            )}
          >
            {isEditMode && (
              <MoveButtons
                onMoveUp={() => moveAchievement.mutate({ id: achievement.id, direction: "up" })}
                onMoveDown={() => moveAchievement.mutate({ id: achievement.id, direction: "down" })}
                isFirst={index === 0}
                isLast={index === achievements.length - 1}
                disabled={moveAchievement.isPending}
              />
            )}
            <div className="flex-1">
              <p className="text-sm font-medium md:text-base">{achievement.title}</p>
              {achievement.company && (
                <p className="text-sm text-muted-foreground">{achievement.company}</p>
              )}
              {achievement.occurred_on && (
                <p className="text-xs font-bold italic text-accent">
                  {formatDisplayDate(achievement.occurred_on)}
                </p>
              )}
              {achievement.description && (
                <p className="mt-1 whitespace-pre-line text-sm">{achievement.description}</p>
              )}
            </div>
            <div className={cn("flex shrink-0", ACTION_BUTTON_ROW_GAP)}>
              <ResumeIncludeToggle
                checked={achievement.include_in_resume}
                onCheckedChange={(checked) => toggleItemResume(achievement, checked)}
                disabled={updateAchievement.isPending}
                label={`the "${achievement.title}" achievement entry`}
              />
              {isEditMode && (
                <>
                  <Button variant="ghost" size="sm" onClick={() => openEditDialog(achievement)}>
                    <Pencil className="h-4 w-4" />
                  </Button>
                  <Button variant="ghost" size="sm" onClick={() => setDeleteTarget(achievement)}>
                    <Trash2 className="h-4 w-4" />
                  </Button>
                </>
              )}
            </div>
          </div>
        ))}
      </CardContent>
      )}

      <Dialog
        open={dialogOpen}
        onClose={() => setDialogOpen(false)}
        title={editingId ? "Edit achievement" : "Add achievement"}
      >
        <form className="flex flex-col gap-4" onSubmit={handleSubmit}>
          {!editingId && scope !== null && !!masterAchievements?.length && (
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="achievement-copy-from-master">Copy from Master (optional)</Label>
              <Select
                id="achievement-copy-from-master"
                value=""
                onChange={(e) => copyFromMaster(e.target.value)}
              >
                <option value="">Start blank</option>
                {masterAchievements.map((a) => (
                  <option key={a.id} value={a.id}>
                    {a.title}
                  </option>
                ))}
              </Select>
            </div>
          )}
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="achievement-title">Title</Label>
            <Input
              id="achievement-title"
              required
              value={form.title}
              onChange={(e) => setForm({ ...form, title: e.target.value })}
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="achievement-company">Company</Label>
            <Input
              id="achievement-company"
              value={form.company}
              onChange={(e) => setForm({ ...form, company: e.target.value })}
              placeholder="Optional"
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="achievement-description">Description</Label>
            <Textarea
              id="achievement-description"
              value={form.description}
              onChange={(e) => setForm({ ...form, description: e.target.value })}
              rows={3}
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="achievement-date">Date (optional)</Label>
            <Input
              id="achievement-date"
              type="date"
              value={form.occurred_on}
              onChange={(e) => setForm({ ...form, occurred_on: e.target.value })}
            />
          </div>
          <Button type="submit" disabled={isSaving}>
            {isSaving ? "Saving..." : editingId ? "Save changes" : "Add achievement"}
          </Button>
          {saveError && (
            <p role="alert" className="text-sm text-destructive">
              {getErrorMessage(saveError)}
            </p>
          )}
        </form>
      </Dialog>

      <ConfirmDialog
        open={deleteTarget !== null}
        onCancel={() => setDeleteTarget(null)}
        onConfirm={() => {
          if (deleteTarget) deleteAchievement.mutate(deleteTarget.id);
          setDeleteTarget(null);
        }}
        title="Delete achievement?"
        description={deleteTarget ? `Remove "${deleteTarget.title}"? This can't be undone.` : ""}
        isPending={deleteAchievement.isPending}
      />

      <ConfirmDialog
        open={clearSectionOpen}
        onCancel={() => setClearSectionOpen(false)}
        onConfirm={() => {
          clearAchievements.mutate();
          setClearSectionOpen(false);
        }}
        title="Clear Key Achievements?"
        description="Remove every key achievement from your profile? This can't be undone."
        isPending={clearAchievements.isPending}
        confirmLabel="Clear"
        confirmPendingLabel="Clearing..."
      />
    </Card>
  );
}
