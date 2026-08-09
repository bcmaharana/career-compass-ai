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
import { CollapseToggle } from "@/components/ui/collapse-toggle";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { Dialog } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { MoveButtons } from "@/components/ui/move-buttons";
import { Select } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { useProfileScope } from "@/features/career-profile/profile-scope";
import { itemAlternateClass, type SectionOrderProps } from "@/features/career-profile/section-order";
import { formatDisplayDate } from "@/lib/date-format";
import { getErrorMessage } from "@/lib/errors";
import { cn } from "@/lib/utils";
import { Eraser, Pencil, Plus, Trash2 } from "lucide-react";
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
 * Renders free-text description preserving the user's own line breaks,
 * with a line-by-line "• "-prefixed run rendered as a real <ul>/<li>
 * bulleted list and every other run as plain paragraphs — matching
 * whichever shape each line actually was in the source (resume
 * extraction now preserves Word's own bullet formatting as a literal
 * "• " prefix per line, see resume_text_extractor.py; a plain intro
 * sentence ahead of a role's bullets keeps no such prefix). Consecutive
 * same-type lines are grouped into one block so an intro sentence (or
 * two) renders above a single bulleted list, rather than alternating
 * <p>/<ul> per line.
 */
function DescriptionText({ description }: { description: string | null }) {
  if (!description) return null;
  const lines = description.split("\n").filter((line) => line.trim());
  if (lines.length === 0) return null;

  const blocks: { bullet: boolean; lines: string[] }[] = [];
  for (const rawLine of lines) {
    const bullet = rawLine.trimStart().startsWith("• ");
    const text = bullet ? rawLine.trimStart().slice(2) : rawLine;
    const last = blocks[blocks.length - 1];
    if (last && last.bullet === bullet) {
      last.lines.push(text);
    } else {
      blocks.push({ bullet, lines: [text] });
    }
  }

  return (
    <div className="mt-2 space-y-1.5 text-sm">
      {blocks.map((block, i) =>
        block.bullet ? (
          <ul key={i} className="list-disc space-y-1 pl-5">
            {block.lines.map((line, j) => (
              <li key={j}>{line}</li>
            ))}
          </ul>
        ) : (
          <div key={i} className="space-y-1">
            {block.lines.map((line, j) => (
              <p key={j}>{line}</p>
            ))}
          </div>
        ),
      )}
    </div>
  );
}

export function ExperienceSection({
  onMoveUp,
  onMoveDown,
  isFirst,
  isLast,
  moveDisabled,
  cardBackground,
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
  const [isOpen, setIsOpen] = useState(false);
  const [isEditMode, setIsEditMode] = useState(false);
  const [collapsedDescriptionIds, setCollapsedDescriptionIds] = useState<Set<string>>(new Set());
  const [deleteTarget, setDeleteTarget] = useState<Experience | null>(null);
  const [clearSectionOpen, setClearSectionOpen] = useState(false);

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
    };

    const mutation = editingId
      ? updateExperience.mutateAsync({ id: editingId, body })
      : addExperience.mutateAsync(body);

    mutation
      .then(() => {
        setDialogOpen(false);
        // A collapsed section's Add button is still reachable (it lives
        // in the header, not behind CollapseToggle) — expand so the
        // newly added item is actually visible instead of the section
        // silently staying collapsed after a successful add.
        if (!editingId) setIsOpen(true);
      })
      .catch(() => {});
  }

  const isSaving = addExperience.isPending || updateExperience.isPending;
  const saveError = addExperience.error ?? updateExperience.error;
  const canSubmit = form.isPresent || form.end_date !== "";

  return (
    <Card className={cardBackground === "background" ? "bg-background" : undefined}>
      <CardHeader className="flex-row items-start justify-between space-y-0">
        <CardTitle>Professional Experience</CardTitle>
        <div className={cn("flex items-start", ACTION_BUTTON_ROW_GAP)}>
          <Button variant="ghost" size="sm" onClick={openAddDialog}>
            <Plus className="h-4 w-4" />
            Add
          </Button>
          <Button variant="ghost" size="sm" onClick={() => setIsEditMode((v) => !v)}>
            {isEditMode ? "Done" : "Edit"}
          </Button>
          {!!experiences?.length && (
            <Button variant="ghost" size="sm" onClick={() => setClearSectionOpen(true)}>
              <Eraser className="h-4 w-4" />
              Clear
            </Button>
          )}
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
            {isEditMode && (
              <MoveButtons
                onMoveUp={() => moveExperience.mutate({ id: experience.id, direction: "up" })}
                onMoveDown={() => moveExperience.mutate({ id: experience.id, direction: "down" })}
                isFirst={index === 0}
                isLast={index === experiences.length - 1}
                disabled={moveExperience.isPending}
              />
            )}
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
            <div className={cn("flex shrink-0", ACTION_BUTTON_ROW_GAP)}>
              <CollapseToggle
                isOpen={!collapsedDescriptionIds.has(experience.id)}
                onToggle={() => toggleDescription(experience.id)}
                label={`${experience.title} description`}
              />
              {isEditMode && (
                <>
                  <Button variant="ghost" size="sm" onClick={() => openEditDialog(experience)}>
                    <Pencil className="h-4 w-4" />
                  </Button>
                  <Button variant="ghost" size="sm" onClick={() => setDeleteTarget(experience)}>
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
