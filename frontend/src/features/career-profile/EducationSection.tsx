import {
  useAddEducation,
  useDeleteEducation,
  useEducations,
  useMoveEducation,
  useUpdateEducation,
} from "@/api/queries/career-profile";
import type { components } from "@/api/schema.gen";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { CollapseToggle } from "@/components/ui/collapse-toggle";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { Dialog } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { MoveButtons } from "@/components/ui/move-buttons";
import { Textarea } from "@/components/ui/textarea";
import { itemAlternateClass, type SectionOrderProps } from "@/features/career-profile/section-order";
import { formatDisplayDate } from "@/lib/date-format";
import { getErrorMessage } from "@/lib/errors";
import { cn } from "@/lib/utils";
import { Pencil, Plus, Trash2 } from "lucide-react";
import { type FormEvent, useState } from "react";

type Education = components["schemas"]["EducationResponse"];

interface FormState {
  institution: string;
  degree: string;
  field_of_study: string;
  start_date: string;
  end_date: string;
  description: string;
}

const EMPTY_FORM: FormState = {
  institution: "",
  degree: "",
  field_of_study: "",
  start_date: "",
  end_date: "",
  description: "",
};

function toFormState(education: Education): FormState {
  return {
    institution: education.institution,
    degree: education.degree ?? "",
    field_of_study: education.field_of_study ?? "",
    start_date: education.start_date ?? "",
    end_date: education.end_date ?? "",
    description: education.description ?? "",
  };
}

export function EducationSection({
  onMoveUp,
  onMoveDown,
  isFirst,
  isLast,
  moveDisabled,
  cardBackground,
}: SectionOrderProps) {
  const { data: educations, isLoading } = useEducations();
  const addEducation = useAddEducation();
  const updateEducation = useUpdateEducation();
  const deleteEducation = useDeleteEducation();
  const moveEducation = useMoveEducation();

  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [form, setForm] = useState<FormState>(EMPTY_FORM);
  const [isOpen, setIsOpen] = useState(true);
  const [deleteTarget, setDeleteTarget] = useState<Education | null>(null);

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

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const body = {
      institution: form.institution,
      degree: form.degree || null,
      field_of_study: form.field_of_study || null,
      start_date: form.start_date || null,
      end_date: form.end_date || null,
      description: form.description || null,
    };

    const mutation = editingId
      ? updateEducation.mutateAsync({ id: editingId, body })
      : addEducation.mutateAsync(body);

    mutation.then(() => setDialogOpen(false)).catch(() => {});
  }

  const isSaving = addEducation.isPending || updateEducation.isPending;
  const saveError = addEducation.error ?? updateEducation.error;

  return (
    <Card className={cardBackground === "background" ? "bg-background" : undefined}>
      <CardHeader className="flex-row items-center justify-between space-y-0">
        <CardTitle>Education</CardTitle>
        <div className="flex items-center gap-1">
          <Button variant="outline" size="sm" onClick={openAddDialog}>
            <Plus className="h-4 w-4" />
            Add
          </Button>
          <CollapseToggle isOpen={isOpen} onToggle={() => setIsOpen(!isOpen)} label="Education" />
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
        {educations?.length === 0 && (
          <p className="text-sm text-muted-foreground">No education added yet.</p>
        )}
        {educations?.map((education, index) => (
          <div
            key={education.id}
            className={cn(
              "flex items-start justify-between gap-4 rounded-md border border-border p-4",
              itemAlternateClass(cardBackground, index),
            )}
          >
            <MoveButtons
              onMoveUp={() => moveEducation.mutate({ id: education.id, direction: "up" })}
              onMoveDown={() => moveEducation.mutate({ id: education.id, direction: "down" })}
              isFirst={index === 0}
              isLast={index === educations.length - 1}
              disabled={moveEducation.isPending}
            />
            <div className="flex-1">
              <p className="font-medium">{education.institution}</p>
              <p className="text-sm text-muted-foreground">
                {[education.degree, education.field_of_study].filter(Boolean).join(", ")}
              </p>
              {(education.start_date || education.end_date) && (
                <p className="text-xs font-bold italic text-accent">
                  {education.start_date ? formatDisplayDate(education.start_date) : "?"} –{" "}
                  {education.end_date ? formatDisplayDate(education.end_date) : "Present"}
                </p>
              )}
            </div>
            <div className="flex shrink-0 gap-1">
              <Button variant="ghost" size="sm" onClick={() => openEditDialog(education)}>
                <Pencil className="h-4 w-4" />
              </Button>
              <Button variant="ghost" size="sm" onClick={() => setDeleteTarget(education)}>
                <Trash2 className="h-4 w-4" />
              </Button>
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
            <Textarea
              id="edu-description"
              value={form.description}
              onChange={(e) => setForm({ ...form, description: e.target.value })}
              rows={3}
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
    </Card>
  );
}
