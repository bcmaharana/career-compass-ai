import {
  useAddExperience,
  useClearExperiences,
  useDeleteExperience,
  useExperiences,
  useMoveExperience,
  useUpdateExperience,
} from "@/api/queries/career-profile";
import type { components } from "@/api/schema.gen";
import { Button } from "@/components/ui/button";
import { ACTION_BUTTON_ROW_GAP } from "@/components/ui/button-variants";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { Dialog } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { MoveButtons } from "@/components/ui/move-buttons";
import { RichTextDisplay, RichTextEditor } from "@/components/ui/rich-text-editor";
import { Select } from "@/components/ui/select";
import { useProfileScope } from "@/features/career-profile/profile-scope";
import { ResumeIncludeToggle } from "@/features/career-profile/ResumeIncludeToggle";
import { itemAlternateClass, type SectionOrderProps } from "@/features/career-profile/section-order";
import { formatDisplayDate } from "@/lib/date-format";
import { getErrorMessage } from "@/lib/errors";
import { cn } from "@/lib/utils";
import { ChevronDown, ChevronRight, Eraser, Pencil, Plus, Trash2 } from "lucide-react";
import { type FormEvent, useState } from "react";

type Experience = components["schemas"]["ExperienceResponse"];

interface FormState {
  title: string;
  company: string;
  location: string;
  start_date: string;
  end_date: string;
  isPresent: boolean;
  description: string;
  include_in_resume: boolean;
}

const EMPTY_FORM: FormState = {
  title: "",
  company: "",
  location: "",
  start_date: "",
  end_date: "",
  isPresent: false,
  description: "",
  include_in_resume: true,
};

function toFormState(experience: Experience): FormState {
  return {
    title: experience.title,
    company: experience.company,
    location: experience.location ?? "",
    start_date: experience.start_date,
    end_date: experience.end_date ?? "",
    isPresent: experience.end_date === null,
    description: experience.description ?? "",
    include_in_resume: experience.include_in_resume,
  };
}

export function ExperienceSection({
  onMoveUp,
  onMoveDown,
  isFirst,
  isLast,
  moveDisabled,
  cardBackground,
  resumeIncluded,
  onToggleResumeIncluded,
  resumeToggleDisabled,
  isOpen,
  onToggleOpen,
  onRequestOpen,
}: SectionOrderProps) {
  const scope = useProfileScope();
  const { data: experiences, isLoading } = useExperiences(scope);
  const addExperience = useAddExperience(scope);
  const updateExperience = useUpdateExperience(scope);
  const deleteExperience = useDeleteExperience(scope);
  const clearExperiences = useClearExperiences(scope);
  const moveExperience = useMoveExperience(scope);
  // Always fetched (cheap, cached) so the Target Role Profile's Add
  // dialog can offer "copy from Master" — never shown on Master itself.
  const { data: masterExperiences } = useExperiences(null);

  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [form, setForm] = useState<FormState>(EMPTY_FORM);
  const [isEditMode, setIsEditMode] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<Experience | null>(null);
  const [clearSectionOpen, setClearSectionOpen] = useState(false);
  // Per-item expand state — collapsed by default, showing only title/
  // company+location/date range (3 lines); clicking the item reveals its
  // full description, no clamp or "Show more" link (direct 2026-08-20
  // request, replacing the earlier ClampedRichText treatment here).
  const [expandedItemIds, setExpandedItemIds] = useState<Set<string>>(new Set());

  function toggleItemExpanded(id: string) {
    setExpandedItemIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  }

  function openAddDialog() {
    setEditingId(null);
    setForm(EMPTY_FORM);
    setDialogOpen(true);
  }

  function openEditDialog(experience: Experience) {
    setEditingId(experience.id);
    setForm(toFormState(experience));
    setDialogOpen(true);
  }

  // Pre-fills the Add form from a Master item the user picked — nothing
  // is saved until they submit, and they can still edit any field first.
  // No live link back to Master afterward (per the Master/Target-Role-
  // Profile design: a one-time copy, not a sync).
  function copyFromMaster(experienceId: string) {
    const source = masterExperiences?.find((e) => e.id === experienceId);
    if (source) setForm(toFormState(source));
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const body = {
      title: form.title,
      company: form.company,
      location: form.location || null,
      start_date: form.start_date,
      end_date: form.isPresent ? null : form.end_date || null,
      description: form.description || null,
      include_in_resume: form.include_in_resume,
    };

    const mutation = editingId
      ? updateExperience.mutateAsync({ id: editingId, body })
      : addExperience.mutateAsync(body);

    mutation
      .then(() => {
        setDialogOpen(false);
        // A collapsed section's Add button is still reachable (it lives
        // in the header, not behind the collapse toggle) — expand so the
        // newly added item is actually visible instead of the section
        // silently staying collapsed after a successful add.
        if (!editingId) onRequestOpen();
      })
      .catch(() => {});
  }

  function toggleItemResume(experience: Experience, include: boolean) {
    updateExperience.mutate({
      id: experience.id,
      body: {
        title: experience.title,
        company: experience.company,
        location: experience.location,
        start_date: experience.start_date,
        end_date: experience.end_date,
        description: experience.description,
        include_in_resume: include,
      },
    });
  }

  const isSaving = addExperience.isPending || updateExperience.isPending;
  const saveError = addExperience.error ?? updateExperience.error;
  const canSubmit = form.isPresent || form.end_date !== "";

  return (
    <Card className={cardBackground === "background" ? "bg-background" : undefined}>
      <CardHeader
        role="button"
        tabIndex={0}
        aria-expanded={isOpen}
        onClick={onToggleOpen}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            onToggleOpen();
          }
        }}
        className="flex-row cursor-pointer select-none items-start justify-between space-y-0"
      >
        <CardTitle>Professional Experience</CardTitle>
        <div className="flex items-center gap-2">
          <div
            className={cn("flex items-start", ACTION_BUTTON_ROW_GAP)}
            onClick={(e) => e.stopPropagation()}
          >
            <ResumeIncludeToggle
              checked={resumeIncluded}
              onCheckedChange={onToggleResumeIncluded}
              disabled={resumeToggleDisabled}
              label="the Professional Experience section"
            />
            <Button variant="ghost" size="sm" onClick={openAddDialog}>
              <Plus className="h-3.5 w-3.5" />
              Add
            </Button>
            <Button variant="ghost" size="sm" onClick={() => setIsEditMode((v) => !v)}>
              {isEditMode ? "Done" : "Edit"}
            </Button>
            {!!experiences?.length && (
              <Button variant="ghost" size="sm" onClick={() => setClearSectionOpen(true)}>
                <Eraser className="h-3.5 w-3.5" />
                Clear
              </Button>
            )}
            <MoveButtons
              onMoveUp={onMoveUp}
              onMoveDown={onMoveDown}
              isFirst={isFirst}
              isLast={isLast}
              disabled={moveDisabled}
            />
          </div>
          {isOpen ? (
            <ChevronDown className="h-4 w-4 shrink-0 text-muted-foreground" />
          ) : (
            <ChevronRight className="h-4 w-4 shrink-0 text-muted-foreground" />
          )}
        </div>
      </CardHeader>
      {isOpen && (
      <CardContent className="flex flex-col gap-3">
        {isLoading && <p className="text-sm text-muted-foreground">Loading...</p>}
        {experiences?.length === 0 && (
          <p className="text-sm text-muted-foreground">
            No experience added yet — add your first role to get started.
          </p>
        )}
        {experiences?.map((experience, index) => {
          const isItemExpanded = expandedItemIds.has(experience.id);
          return (
          <div
            key={experience.id}
            className={cn(
              "flex items-start justify-between gap-4 rounded-md border border-border px-4 py-2",
              itemAlternateClass(cardBackground, index),
            )}
          >
            {isEditMode && (
              <div onClick={(e) => e.stopPropagation()}>
                <MoveButtons
                  onMoveUp={() => moveExperience.mutate({ id: experience.id, direction: "up" })}
                  onMoveDown={() => moveExperience.mutate({ id: experience.id, direction: "down" })}
                  isFirst={index === 0}
                  isLast={index === experiences.length - 1}
                  disabled={moveExperience.isPending}
                  className="h-7 w-7 p-0"
                />
              </div>
            )}
            <div
              role="button"
              tabIndex={0}
              aria-expanded={isItemExpanded}
              onClick={() => toggleItemExpanded(experience.id)}
              onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === " ") {
                  e.preventDefault();
                  toggleItemExpanded(experience.id);
                }
              }}
              className="flex-1 cursor-pointer select-none"
            >
              <p className="text-sm font-medium">{experience.title}</p>
              <p className="text-sm text-muted-foreground">
                <span className="font-bold">{experience.company}</span>
                {experience.location ? ` · ${experience.location}` : ""}
              </p>
              <p className="text-xs font-bold italic text-accent">
                {formatDisplayDate(experience.start_date)} –{" "}
                {experience.end_date ? formatDisplayDate(experience.end_date) : "Present"}
              </p>
              {isItemExpanded && experience.description && (
                <RichTextDisplay html={experience.description} className="mt-2" />
              )}
            </div>
            <div
              className={cn("flex shrink-0 items-center", ACTION_BUTTON_ROW_GAP)}
              onClick={(e) => e.stopPropagation()}
            >
              <ResumeIncludeToggle
                checked={experience.include_in_resume}
                onCheckedChange={(checked) => toggleItemResume(experience, checked)}
                disabled={updateExperience.isPending}
                label={`the "${experience.title}" experience entry`}
              />
              {isEditMode && (
                <>
                  <Button
                    variant="ghost"
                    size="sm"
                    className="h-7 w-7 p-0"
                    onClick={() => openEditDialog(experience)}
                  >
                    <Pencil className="h-3.5 w-3.5" />
                  </Button>
                  <Button
                    variant="ghost"
                    size="sm"
                    className="h-7 w-7 p-0"
                    onClick={() => setDeleteTarget(experience)}
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                  </Button>
                </>
              )}
            </div>
          </div>
          );
        })}
      </CardContent>
      )}

      <Dialog
        open={dialogOpen}
        onClose={() => setDialogOpen(false)}
        title={editingId ? "Edit experience" : "Add experience"}
      >
        <form className="flex flex-col gap-4" onSubmit={handleSubmit}>
          {!editingId && scope !== null && !!masterExperiences?.length && (
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="exp-copy-from-master">Copy from Master (optional)</Label>
              <Select id="exp-copy-from-master" value="" onChange={(e) => copyFromMaster(e.target.value)}>
                <option value="">Start blank</option>
                {masterExperiences.map((e) => (
                  <option key={e.id} value={e.id}>
                    {e.title} at {e.company}
                  </option>
                ))}
              </Select>
            </div>
          )}
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="exp-title">Title</Label>
            <Input
              id="exp-title"
              required
              value={form.title}
              onChange={(e) => setForm({ ...form, title: e.target.value })}
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="exp-company">Company</Label>
            <Input
              id="exp-company"
              required
              value={form.company}
              onChange={(e) => setForm({ ...form, company: e.target.value })}
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="exp-location">Location</Label>
            <Input
              id="exp-location"
              value={form.location}
              onChange={(e) => setForm({ ...form, location: e.target.value })}
            />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="exp-start">Start date</Label>
              <Input
                id="exp-start"
                type="date"
                required
                value={form.start_date}
                onChange={(e) => setForm({ ...form, start_date: e.target.value })}
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="exp-end">
                End date {!form.isPresent && <span className="text-destructive">*</span>}
              </Label>
              <Input
                id="exp-end"
                type="date"
                required={!form.isPresent}
                disabled={form.isPresent}
                value={form.end_date}
                onChange={(e) => setForm({ ...form, end_date: e.target.value })}
              />
            </div>
          </div>
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={form.isPresent}
              onChange={(e) =>
                setForm({ ...form, isPresent: e.target.checked, end_date: "" })
              }
              className="h-4 w-4 rounded border-border"
            />
            I currently work here
          </label>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="exp-description">Description</Label>
            <RichTextEditor
              id="exp-description"
              defaultValue={form.description}
              onChange={(html) => setForm({ ...form, description: html })}
              placeholder="Line breaks are preserved as entered — add your own bullets if you want them"
            />
          </div>
          <Button type="submit" disabled={isSaving || !canSubmit}>
            {isSaving ? "Saving..." : editingId ? "Save changes" : "Add experience"}
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
          if (deleteTarget) deleteExperience.mutate(deleteTarget.id);
          setDeleteTarget(null);
        }}
        title="Delete experience?"
        description={
          deleteTarget
            ? `Remove "${deleteTarget.title}" at ${deleteTarget.company}? This can't be undone.`
            : ""
        }
        isPending={deleteExperience.isPending}
      />

      <ConfirmDialog
        open={clearSectionOpen}
        onCancel={() => setClearSectionOpen(false)}
        onConfirm={() => {
          clearExperiences.mutate();
          setClearSectionOpen(false);
        }}
        title="Clear Professional Experience?"
        description="Remove every experience entry from your profile? This can't be undone."
        isPending={clearExperiences.isPending}
        confirmLabel="Clear"
        confirmPendingLabel="Clearing..."
      />
    </Card>
  );
}
