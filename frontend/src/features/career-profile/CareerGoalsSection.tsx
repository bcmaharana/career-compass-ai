import {
  useAddCareerGoal,
  useCareerGoals,
  useClearCareerGoals,
  useDeleteCareerGoal,
  useMoveCareerGoal,
  useUpdateCareerGoal,
} from "@/api/queries/career-profile";
import type { components } from "@/api/schema.gen";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ACTION_BUTTON_ROW_GAP } from "@/components/ui/button-variants";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { CollapseToggle } from "@/components/ui/collapse-toggle";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { Dialog } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { MoveButtons } from "@/components/ui/move-buttons";
import { RichTextDisplay, RichTextEditor } from "@/components/ui/rich-text-editor";
import { useProfileScope } from "@/features/career-profile/profile-scope";
import { ResumeIncludeToggle } from "@/features/career-profile/ResumeIncludeToggle";
import { itemAlternateClass, type SectionOrderProps } from "@/features/career-profile/section-order";
import { formatDisplayDate } from "@/lib/date-format";
import { getErrorMessage } from "@/lib/errors";
import { cn } from "@/lib/utils";
import { Eraser, Pencil, Plus, Trash2 } from "lucide-react";
import { type FormEvent, useState } from "react";

type CareerGoal = components["schemas"]["CareerGoalResponse"];
type GoalStatus = "active" | "achieved" | "abandoned";

interface FormState {
  target_role: string;
  target_date: string;
  status: GoalStatus;
  description: string;
  include_in_resume: boolean;
}

const EMPTY_FORM: FormState = {
  target_role: "",
  target_date: "",
  status: "active",
  description: "",
  include_in_resume: true,
};

function toFormState(goal: CareerGoal): FormState {
  return {
    target_role: goal.target_role,
    target_date: goal.target_date ?? "",
    status: goal.status as GoalStatus,
    description: goal.description ?? "",
    include_in_resume: goal.include_in_resume,
  };
}

const STATUS_VARIANT: Record<GoalStatus, "default" | "accent" | "primary"> = {
  active: "accent",
  achieved: "primary",
  abandoned: "default",
};

export function CareerGoalsSection({
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
  const { data: goals, isLoading } = useCareerGoals();
  const addGoal = useAddCareerGoal();
  const updateGoal = useUpdateCareerGoal();
  const deleteGoal = useDeleteCareerGoal();
  const clearGoals = useClearCareerGoals();
  const moveGoal = useMoveCareerGoal();
  // Career Goals stay Master-only regardless of which profile is being
  // viewed (resume merge never touches them, no per-target-role use case
  // yet) — this label is the only thing that changes on a Target Role
  // Profile view, so it doesn't silently look like a bug that this
  // section's data never changes when switching roles.
  const isTargetRoleView = useProfileScope() !== null;

  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [form, setForm] = useState<FormState>(EMPTY_FORM);
  const [isOpen, setIsOpen] = useState(false);
  const [isEditMode, setIsEditMode] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<CareerGoal | null>(null);
  const [clearSectionOpen, setClearSectionOpen] = useState(false);

  function openAddDialog() {
    setEditingId(null);
    setForm(EMPTY_FORM);
    setDialogOpen(true);
  }

  function openEditDialog(goal: CareerGoal) {
    setEditingId(goal.id);
    setForm(toFormState(goal));
    setDialogOpen(true);
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (editingId) {
      updateGoal
        .mutateAsync({
          id: editingId,
          body: {
            target_role: form.target_role,
            target_date: form.target_date || null,
            status: form.status,
            description: form.description || null,
            include_in_resume: form.include_in_resume,
          },
        })
        .then(() => setDialogOpen(false))
        .catch(() => {});
    } else {
      addGoal
        .mutateAsync({
          target_role: form.target_role,
          target_date: form.target_date || null,
          description: form.description || null,
          include_in_resume: form.include_in_resume,
        })
        .then(() => {
          setDialogOpen(false);
          setIsOpen(true);
        })
        .catch(() => {});
    }
  }

  function toggleItemResume(goal: CareerGoal, include: boolean) {
    updateGoal.mutate({
      id: goal.id,
      body: {
        target_role: goal.target_role,
        target_date: goal.target_date,
        status: goal.status as GoalStatus,
        description: goal.description,
        include_in_resume: include,
      },
    });
  }

  const isSaving = addGoal.isPending || updateGoal.isPending;
  const saveError = addGoal.error ?? updateGoal.error;

  return (
    <Card className={cardBackground === "background" ? "bg-background" : undefined}>
      <CardHeader className="flex-row items-start justify-between space-y-0">
        <div className="flex items-center gap-2">
          <CardTitle>Career Goals</CardTitle>
          {isTargetRoleView && <Badge variant="default">Master profile</Badge>}
        </div>
        <div className={cn("flex items-start", ACTION_BUTTON_ROW_GAP)}>
          <ResumeIncludeToggle
            checked={resumeIncluded}
            onCheckedChange={onToggleResumeIncluded}
            disabled={resumeToggleDisabled}
            label="the Career Goals section"
          />
          <Button variant="ghost" size="sm" onClick={openAddDialog}>
            <Plus className="h-4 w-4" />
            Add
          </Button>
          <Button variant="ghost" size="sm" onClick={() => setIsEditMode((v) => !v)}>
            {isEditMode ? "Done" : "Edit"}
          </Button>
          {!!goals?.length && (
            <Button variant="ghost" size="sm" onClick={() => setClearSectionOpen(true)}>
              <Eraser className="h-4 w-4" />
              Clear
            </Button>
          )}
          <CollapseToggle
            isOpen={isOpen}
            onToggle={() => setIsOpen(!isOpen)}
            label="Career Goals"
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
        {goals?.length === 0 && (
          <p className="text-sm text-muted-foreground">No career goals set yet.</p>
        )}
        {goals?.map((goal, index) => (
          <div
            key={goal.id}
            className={cn(
              "flex items-start justify-between gap-4 rounded-md border border-border p-4",
              itemAlternateClass(cardBackground, index),
            )}
          >
            {isEditMode && (
              <MoveButtons
                onMoveUp={() => moveGoal.mutate({ id: goal.id, direction: "up" })}
                onMoveDown={() => moveGoal.mutate({ id: goal.id, direction: "down" })}
                isFirst={index === 0}
                isLast={index === goals.length - 1}
                disabled={moveGoal.isPending}
              />
            )}
            <div className="flex-1">
              <div className="flex items-center gap-2">
                <p className="text-sm font-medium md:text-base">{goal.target_role}</p>
                <Badge variant={STATUS_VARIANT[goal.status as GoalStatus]}>{goal.status}</Badge>
              </div>
              {goal.target_date && (
                <p className="text-xs font-bold italic text-accent">
                  Target: {formatDisplayDate(goal.target_date)}
                </p>
              )}
              {goal.description && <RichTextDisplay html={goal.description} className="mt-1" />}
            </div>
            <div className={cn("flex shrink-0", ACTION_BUTTON_ROW_GAP)}>
              <ResumeIncludeToggle
                checked={goal.include_in_resume}
                onCheckedChange={(checked) => toggleItemResume(goal, checked)}
                disabled={updateGoal.isPending}
                label={`the "${goal.target_role}" career goal entry`}
              />
              {isEditMode && (
                <>
                  <Button variant="ghost" size="sm" onClick={() => openEditDialog(goal)}>
                    <Pencil className="h-4 w-4" />
                  </Button>
                  <Button variant="ghost" size="sm" onClick={() => setDeleteTarget(goal)}>
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
        title={editingId ? "Edit career goal" : "Add career goal"}
      >
        <form className="flex flex-col gap-4" onSubmit={handleSubmit}>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="goal-role">Target role</Label>
            <Input
              id="goal-role"
              required
              value={form.target_role}
              onChange={(e) => setForm({ ...form, target_role: e.target.value })}
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="goal-date">Target date</Label>
            <Input
              id="goal-date"
              type="date"
              value={form.target_date}
              onChange={(e) => setForm({ ...form, target_date: e.target.value })}
            />
          </div>
          {editingId && (
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="goal-status">Status</Label>
              <select
                id="goal-status"
                value={form.status}
                onChange={(e) => setForm({ ...form, status: e.target.value as GoalStatus })}
                className="h-10 rounded-md border border-border bg-card px-3 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              >
                <option value="active">Active</option>
                <option value="achieved">Achieved</option>
                <option value="abandoned">Abandoned</option>
              </select>
            </div>
          )}
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="goal-description">Description</Label>
            <RichTextEditor
              id="goal-description"
              defaultValue={form.description}
              onChange={(html) => setForm({ ...form, description: html })}
            />
          </div>
          <Button type="submit" disabled={isSaving}>
            {isSaving ? "Saving..." : editingId ? "Save changes" : "Add goal"}
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
          if (deleteTarget) deleteGoal.mutate(deleteTarget.id);
          setDeleteTarget(null);
        }}
        title="Delete career goal?"
        description={
          deleteTarget ? `Remove "${deleteTarget.target_role}"? This can't be undone.` : ""
        }
        isPending={deleteGoal.isPending}
      />

      <ConfirmDialog
        open={clearSectionOpen}
        onCancel={() => setClearSectionOpen(false)}
        onConfirm={() => {
          clearGoals.mutate();
          setClearSectionOpen(false);
        }}
        title="Clear Career Goals?"
        description="Remove every career goal from your profile? This can't be undone."
        isPending={clearGoals.isPending}
        confirmLabel="Clear"
        confirmPendingLabel="Clearing..."
      />
    </Card>
  );
}
