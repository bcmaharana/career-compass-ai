import {
  useAddCareerHighlight,
  useCareerHighlights,
  useClearCareerHighlights,
  useDeleteCareerHighlight,
  useMoveCareerHighlight,
  useUpdateCareerHighlight,
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

type CareerHighlight = components["schemas"]["CareerHighlightResponse"];

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

function toFormState(highlight: CareerHighlight): FormState {
  return {
    title: highlight.title,
    company: highlight.company ?? "",
    description: highlight.description ?? "",
    occurred_on: highlight.occurred_on ?? "",
    include_in_resume: highlight.include_in_resume,
  };
}

export function CareerHighlightsSection({
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
  const { data: highlights, isLoading } = useCareerHighlights(scope);
  const addHighlight = useAddCareerHighlight(scope);
  const updateHighlight = useUpdateCareerHighlight(scope);
  const deleteHighlight = useDeleteCareerHighlight(scope);
  const clearHighlights = useClearCareerHighlights(scope);
  const moveHighlight = useMoveCareerHighlight(scope);
  const { data: masterHighlights } = useCareerHighlights(null);

  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [form, setForm] = useState<FormState>(EMPTY_FORM);
  const [isEditMode, setIsEditMode] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<CareerHighlight | null>(null);
  const [clearSectionOpen, setClearSectionOpen] = useState(false);

  function openAddDialog() {
    setEditingId(null);
    setForm(EMPTY_FORM);
    setDialogOpen(true);
  }

  function openEditDialog(highlight: CareerHighlight) {
    setEditingId(highlight.id);
    setForm(toFormState(highlight));
    setDialogOpen(true);
  }

  function copyFromMaster(highlightId: string) {
    const source = masterHighlights?.find((h) => h.id === highlightId);
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
      ? updateHighlight.mutateAsync({ id: editingId, body })
      : addHighlight.mutateAsync(body);
    mutation
      .then(() => {
        setDialogOpen(false);
        if (!editingId) onRequestOpen();
      })
      .catch(() => {});
  }

  function toggleItemResume(highlight: CareerHighlight, include: boolean) {
    updateHighlight.mutate({
      id: highlight.id,
      body: {
        title: highlight.title,
        company: highlight.company,
        description: highlight.description,
        occurred_on: highlight.occurred_on,
        include_in_resume: include,
      },
    });
  }

  const isSaving = addHighlight.isPending || updateHighlight.isPending;
  const saveError = addHighlight.error ?? updateHighlight.error;

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
        <CardTitle>Career Highlights</CardTitle>
        <div className="flex items-center gap-2">
          <div
            className={cn("flex items-start", ACTION_BUTTON_ROW_GAP)}
            onClick={(e) => e.stopPropagation()}
          >
            <ResumeIncludeToggle
              checked={resumeIncluded}
              onCheckedChange={onToggleResumeIncluded}
              disabled={resumeToggleDisabled}
              label="the Career Highlights section"
            />
            <Button variant="ghost" size="sm" onClick={openAddDialog}>
              <Plus className="h-3.5 w-3.5" />
              Add
            </Button>
            <Button variant="ghost" size="sm" onClick={() => setIsEditMode((v) => !v)}>
              {isEditMode ? "Done" : "Edit"}
            </Button>
            {!!highlights?.length && (
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
        {highlights?.length === 0 && (
          <p className="text-sm text-muted-foreground">
            No highlights added yet — standout moments from your career, separate from your full
            work history.
          </p>
        )}
        {highlights?.map((highlight, index) => (
          <div
            key={highlight.id}
            className={cn(
              "flex items-start justify-between gap-4 rounded-md border border-border px-4 py-2",
              itemAlternateClass(cardBackground, index),
            )}
          >
            {isEditMode && (
              <MoveButtons
                onMoveUp={() => moveHighlight.mutate({ id: highlight.id, direction: "up" })}
                onMoveDown={() => moveHighlight.mutate({ id: highlight.id, direction: "down" })}
                isFirst={index === 0}
                isLast={index === highlights.length - 1}
                disabled={moveHighlight.isPending}
                className="h-7 w-7 p-0"
              />
            )}
            <div className="flex-1">
              <p className="text-sm font-medium">{highlight.title}</p>
              {highlight.company && (
                <p className="text-sm text-muted-foreground">{highlight.company}</p>
              )}
              {highlight.occurred_on && (
                <p className="text-xs font-bold italic text-accent">
                  {formatDisplayDate(highlight.occurred_on)}
                </p>
              )}
              {highlight.description && (
                <RichTextDisplay html={highlight.description} className="mt-1" />
              )}
            </div>
            <div className={cn("flex shrink-0", ACTION_BUTTON_ROW_GAP)}>
              <ResumeIncludeToggle
                checked={highlight.include_in_resume}
                onCheckedChange={(checked) => toggleItemResume(highlight, checked)}
                disabled={updateHighlight.isPending}
                label={`the "${highlight.title}" highlight entry`}
              />
              {isEditMode && (
                <>
                  <Button
                    variant="ghost"
                    size="sm"
                    className="h-7 w-7 p-0"
                    onClick={() => openEditDialog(highlight)}
                  >
                    <Pencil className="h-3.5 w-3.5" />
                  </Button>
                  <Button
                    variant="ghost"
                    size="sm"
                    className="h-7 w-7 p-0"
                    onClick={() => setDeleteTarget(highlight)}
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
        title={editingId ? "Edit highlight" : "Add highlight"}
      >
        <form className="flex flex-col gap-4" onSubmit={handleSubmit}>
          {!editingId && scope !== null && !!masterHighlights?.length && (
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="highlight-copy-from-master">Copy from Master (optional)</Label>
              <Select
                id="highlight-copy-from-master"
                value=""
                onChange={(e) => copyFromMaster(e.target.value)}
              >
                <option value="">Start blank</option>
                {masterHighlights.map((h) => (
                  <option key={h.id} value={h.id}>
                    {h.title}
                  </option>
                ))}
              </Select>
            </div>
          )}
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="highlight-title">Title</Label>
            <Input
              id="highlight-title"
              required
              value={form.title}
              onChange={(e) => setForm({ ...form, title: e.target.value })}
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="highlight-company">Company</Label>
            <Input
              id="highlight-company"
              value={form.company}
              onChange={(e) => setForm({ ...form, company: e.target.value })}
              placeholder="Optional"
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="highlight-description">Description</Label>
            <RichTextEditor
              id="highlight-description"
              defaultValue={form.description}
              onChange={(html) => setForm({ ...form, description: html })}
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="highlight-date">Date (optional)</Label>
            <Input
              id="highlight-date"
              type="date"
              value={form.occurred_on}
              onChange={(e) => setForm({ ...form, occurred_on: e.target.value })}
            />
          </div>
          <Button type="submit" disabled={isSaving}>
            {isSaving ? "Saving..." : editingId ? "Save changes" : "Add highlight"}
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
          if (deleteTarget) deleteHighlight.mutate(deleteTarget.id);
          setDeleteTarget(null);
        }}
        title="Delete highlight?"
        description={deleteTarget ? `Remove "${deleteTarget.title}"? This can't be undone.` : ""}
        isPending={deleteHighlight.isPending}
      />

      <ConfirmDialog
        open={clearSectionOpen}
        onCancel={() => setClearSectionOpen(false)}
        onConfirm={() => {
          clearHighlights.mutate();
          setClearSectionOpen(false);
        }}
        title="Clear Career Highlights?"
        description="Remove every career highlight from your profile? This can't be undone."
        isPending={clearHighlights.isPending}
        confirmLabel="Clear"
        confirmPendingLabel="Clearing..."
      />
    </Card>
  );
}
