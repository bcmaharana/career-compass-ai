import {
  useAddExperience,
  useDeleteExperience,
  useExperiences,
  useMoveExperience,
  useUpdateExperience,
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

type Experience = components["schemas"]["ExperienceResponse"];

interface FormState {
  title: string;
  company: string;
  location: string;
  start_date: string;
  end_date: string;
  isPresent: boolean;
  description: string;
}

const EMPTY_FORM: FormState = {
  title: "",
  company: "",
  location: "",
  start_date: "",
  end_date: "",
  isPresent: false,
  description: "",
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
  };
}

/**
 * Renders free-text description preserving the user's own line breaks —
 * a plain <p> collapses newlines a textarea captures, making multi-line
 * text read as one run-on paragraph. `whitespace-pre-line` preserves
 * newlines (and still wraps long lines normally) without imposing any
 * bullet/list styling — deliberately not a <ul>/<li> rendering: a first
 * line meant as a header, or the user's own bullet characters typed
 * inline, would otherwise get an unwanted bullet forced in front of
 * them.
 */
function DescriptionText({ description }: { description: string | null }) {
  if (!description) return null;
  return <p className="mt-2 whitespace-pre-line text-sm">{description}</p>;
}

export function ExperienceSection({
  onMoveUp,
  onMoveDown,
  isFirst,
  isLast,
  moveDisabled,
  cardBackground,
}: SectionOrderProps) {
  const { data: experiences, isLoading } = useExperiences();
  const addExperience = useAddExperience();
  const updateExperience = useUpdateExperience();
  const deleteExperience = useDeleteExperience();
  const moveExperience = useMoveExperience();

  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [form, setForm] = useState<FormState>(EMPTY_FORM);
  const [isOpen, setIsOpen] = useState(true);
  const [collapsedDescriptionIds, setCollapsedDescriptionIds] = useState<Set<string>>(new Set());
  const [deleteTarget, setDeleteTarget] = useState<Experience | null>(null);

  function toggleDescription(id: string) {
    setCollapsedDescriptionIds((prev) => {
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

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const body = {
      title: form.title,
      company: form.company,
      location: form.location || null,
      start_date: form.start_date,
      end_date: form.isPresent ? null : form.end_date || null,
      description: form.description || null,
    };

    const mutation = editingId
      ? updateExperience.mutateAsync({ id: editingId, body })
      : addExperience.mutateAsync(body);

    mutation.then(() => setDialogOpen(false)).catch(() => {});
  }

  const isSaving = addExperience.isPending || updateExperience.isPending;
  const saveError = addExperience.error ?? updateExperience.error;
  const canSubmit = form.isPresent || form.end_date !== "";

  return (
    <Card className={cardBackground === "background" ? "bg-background" : undefined}>
      <CardHeader className="flex-row items-center justify-between space-y-0">
        <CardTitle>Professional Experience</CardTitle>
        <div className="flex items-center gap-1">
          <Button variant="outline" size="sm" onClick={openAddDialog}>
            <Plus className="h-4 w-4" />
            Add
          </Button>
          <CollapseToggle
            isOpen={isOpen}
            onToggle={() => setIsOpen(!isOpen)}
            label="Professional Experience"
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
        {experiences?.length === 0 && (
          <p className="text-sm text-muted-foreground">
            No experience added yet — add your first role to get started.
          </p>
        )}
        {experiences?.map((experience, index) => (
          <div
            key={experience.id}
            className={cn(
              "flex items-start justify-between gap-4 rounded-md border border-border p-4",
              itemAlternateClass(cardBackground, index),
            )}
          >
            <MoveButtons
              onMoveUp={() => moveExperience.mutate({ id: experience.id, direction: "up" })}
              onMoveDown={() => moveExperience.mutate({ id: experience.id, direction: "down" })}
              isFirst={index === 0}
              isLast={index === experiences.length - 1}
              disabled={moveExperience.isPending}
            />
            <div className="flex-1">
              <p className="font-medium">{experience.title}</p>
              <p className="text-sm text-muted-foreground">
                <span className="font-bold">{experience.company}</span>
                {experience.location ? ` · ${experience.location}` : ""}
              </p>
              <p className="text-xs font-bold italic text-accent">
                {formatDisplayDate(experience.start_date)} –{" "}
                {experience.end_date ? formatDisplayDate(experience.end_date) : "Present"}
              </p>
              {!collapsedDescriptionIds.has(experience.id) && (
                <DescriptionText description={experience.description} />
              )}
            </div>
            <div className="flex shrink-0 gap-1">
              <CollapseToggle
                isOpen={!collapsedDescriptionIds.has(experience.id)}
                onToggle={() => toggleDescription(experience.id)}
                label={`${experience.title} description`}
              />
              <Button variant="ghost" size="sm" onClick={() => openEditDialog(experience)}>
                <Pencil className="h-4 w-4" />
              </Button>
              <Button variant="ghost" size="sm" onClick={() => setDeleteTarget(experience)}>
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
        title={editingId ? "Edit experience" : "Add experience"}
      >
        <form className="flex flex-col gap-4" onSubmit={handleSubmit}>
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
            <Textarea
              id="exp-description"
              value={form.description}
              onChange={(e) => setForm({ ...form, description: e.target.value })}
              rows={3}
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
    </Card>
  );
}
