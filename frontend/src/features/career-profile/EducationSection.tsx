import {
  useAddEducation,
  useClearEducations,
  useDeleteEducation,
  useEducations,
  useMoveEducation,
  useUpdateEducation,
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

type Education = components["schemas"]["EducationResponse"];

interface FormState {
  institution: string;
  degree: string;
  field_of_study: string;
  start_date: string;
  end_date: string;
  description: string;
  include_in_resume: boolean;
}

const EMPTY_FORM: FormState = {
  institution: "",
  degree: "",
  field_of_study: "",
  start_date: "",
  end_date: "",
  description: "",
  include_in_resume: true,
};

function toFormState(education: Education): FormState {
  return {
    institution: education.institution,
    degree: education.degree ?? "",
    field_of_study: education.field_of_study ?? "",
    start_date: education.start_date ?? "",
    end_date: education.end_date ?? "",
    description: education.description ?? "",
    include_in_resume: education.include_in_resume,
  };
}

export function EducationSection({
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
  const { data: educations, isLoading } = useEducations(scope);
  const addEducation = useAddEducation(scope);
  const updateEducation = useUpdateEducation(scope);
  const deleteEducation = useDeleteEducation(scope);
  const clearEducations = useClearEducations(scope);
  const moveEducation = useMoveEducation(scope);
  const { data: masterEducations } = useEducations(null);

  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [form, setForm] = useState<FormState>(EMPTY_FORM);
  const [isEditMode, setIsEditMode] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<Education | null>(null);
  const [clearSectionOpen, setClearSectionOpen] = useState(false);

  function openAddDialog() {
    setEditingId(null);
    setForm(EMPTY_FORM);
    setDialogOpen(true);
  }

  function openEditDialog(education: Education) {
    setEditingId(education.id);
    setForm(toFormState(education));
    setDialogOpen(true);
  }

  function copyFromMaster(educationId: string) {
    const source = masterEducations?.find((e) => e.id === educationId);
    if (source) setForm(toFormState(source));
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const body = {
      institution: form.institution,
      degree: form.degree || null,
      field_of_study: form.field_of_study || null,
      start_date: form.start_date || null,
      end_date: form.end_date || null,
      description: form.description || null,
      include_in_resume: form.include_in_resume,
    };

    const mutation = editingId
      ? updateEducation.mutateAsync({ id: editingId, body })
      : addEducation.mutateAsync(body);

    mutation
      .then(() => {
        setDialogOpen(false);
        if (!editingId) onRequestOpen();
      })
      .catch(() => {});
  }

  function toggleItemResume(education: Education, include: boolean) {
    updateEducation.mutate({
      id: education.id,
      body: {
        institution: education.institution,
        degree: education.degree,
        field_of_study: education.field_of_study,
        start_date: education.start_date,
        end_date: education.end_date,
        description: education.description,
        include_in_resume: include,
      },
    });
  }

  const isSaving = addEducation.isPending || updateEducation.isPending;
  const saveError = addEducation.error ?? updateEducation.error;

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
        <CardTitle>Education</CardTitle>
        <div className="flex items-center gap-2">
          <div
            className={cn("flex items-start", ACTION_BUTTON_ROW_GAP)}
            onClick={(e) => e.stopPropagation()}
          >
            <ResumeIncludeToggle
              checked={resumeIncluded}
              onCheckedChange={onToggleResumeIncluded}
              disabled={resumeToggleDisabled}
              label="the Education section"
            />
            <Button variant="ghost" size="sm" onClick={openAddDialog}>
              <Plus className="h-3.5 w-3.5" />
              Add
            </Button>
            <Button variant="ghost" size="sm" onClick={() => setIsEditMode((v) => !v)}>
              {isEditMode ? "Done" : "Edit"}
            </Button>
            {!!educations?.length && (
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
        {educations?.length === 0 && (
          <p className="text-sm text-muted-foreground">No education added yet.</p>
        )}
        {educations?.map((education, index) => (
          <div
            key={education.id}
            className={cn(
              "flex items-start justify-between gap-4 rounded-md border border-border px-4 py-2",
              itemAlternateClass(cardBackground, index),
            )}
          >
            {isEditMode && (
              <MoveButtons
                onMoveUp={() => moveEducation.mutate({ id: education.id, direction: "up" })}
                onMoveDown={() => moveEducation.mutate({ id: education.id, direction: "down" })}
                isFirst={index === 0}
                isLast={index === educations.length - 1}
                disabled={moveEducation.isPending}
                className="h-7 w-7 p-0"
              />
            )}
            <div className="flex-1">
              <p className="text-sm font-medium">{education.institution}</p>
              <p className="text-sm text-muted-foreground">
                {[education.degree, education.field_of_study].filter(Boolean).join(", ")}
              </p>
              {(education.start_date || education.end_date) && (
                <p className="text-xs font-bold italic text-accent">
                  {education.start_date ? formatDisplayDate(education.start_date) : "?"} –{" "}
                  {education.end_date ? formatDisplayDate(education.end_date) : "Present"}
                </p>
              )}
              {education.description && (
                <RichTextDisplay html={education.description} className="mt-2" />
              )}
            </div>
            <div className={cn("flex shrink-0", ACTION_BUTTON_ROW_GAP)}>
              <ResumeIncludeToggle
                checked={education.include_in_resume}
                onCheckedChange={(checked) => toggleItemResume(education, checked)}
                disabled={updateEducation.isPending}
                label={`the "${education.institution}" education entry`}
              />
              {isEditMode && (
                <>
                  <Button
                    variant="ghost"
                    size="sm"
                    className="h-7 w-7 p-0"
                    onClick={() => openEditDialog(education)}
                  >
                    <Pencil className="h-3.5 w-3.5" />
                  </Button>
                  <Button
                    variant="ghost"
                    size="sm"
                    className="h-7 w-7 p-0"
                    onClick={() => setDeleteTarget(education)}
                  >
                    <Trash2 className="h-3.5 w-3.5" />
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
        title={editingId ? "Edit education" : "Add education"}
      >
        <form className="flex flex-col gap-4" onSubmit={handleSubmit}>
          {!editingId && scope !== null && !!masterEducations?.length && (
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="edu-copy-from-master">Copy from Master (optional)</Label>
              <Select id="edu-copy-from-master" value="" onChange={(e) => copyFromMaster(e.target.value)}>
                <option value="">Start blank</option>
                {masterEducations.map((e) => (
                  <option key={e.id} value={e.id}>
                    {e.institution}
                  </option>
                ))}
              </Select>
            </div>
          )}
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="edu-institution">Institution</Label>
            <Input
              id="edu-institution"
              required
              value={form.institution}
              onChange={(e) => setForm({ ...form, institution: e.target.value })}
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="edu-degree">Degree</Label>
            <Input
              id="edu-degree"
              value={form.degree}
              onChange={(e) => setForm({ ...form, degree: e.target.value })}
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="edu-field">Field of study</Label>
            <Input
              id="edu-field"
              value={form.field_of_study}
              onChange={(e) => setForm({ ...form, field_of_study: e.target.value })}
            />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="edu-start">Start date</Label>
              <Input
                id="edu-start"
                type="date"
                value={form.start_date}
                onChange={(e) => setForm({ ...form, start_date: e.target.value })}
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="edu-end">End date</Label>
              <Input
                id="edu-end"
                type="date"
                value={form.end_date}
                onChange={(e) => setForm({ ...form, end_date: e.target.value })}
              />
            </div>
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="edu-description">Description</Label>
            <RichTextEditor
              id="edu-description"
              defaultValue={form.description}
              onChange={(html) => setForm({ ...form, description: html })}
            />
          </div>
          <Button type="submit" disabled={isSaving}>
            {isSaving ? "Saving..." : editingId ? "Save changes" : "Add education"}
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
          if (deleteTarget) deleteEducation.mutate(deleteTarget.id);
          setDeleteTarget(null);
        }}
        title="Delete education?"
        description={
          deleteTarget ? `Remove "${deleteTarget.institution}"? This can't be undone.` : ""
        }
        isPending={deleteEducation.isPending}
      />

      <ConfirmDialog
        open={clearSectionOpen}
        onCancel={() => setClearSectionOpen(false)}
        onConfirm={() => {
          clearEducations.mutate();
          setClearSectionOpen(false);
        }}
        title="Clear Education?"
        description="Remove every education entry from your profile? This can't be undone."
        isPending={clearEducations.isPending}
        confirmLabel="Clear"
        confirmPendingLabel="Clearing..."
      />
    </Card>
  );
}
