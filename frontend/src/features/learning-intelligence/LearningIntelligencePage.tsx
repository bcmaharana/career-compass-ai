import { useTargetRoles } from "@/api/queries/career-profile";
import {
  useAddLearningItem,
  useDeleteLearningItem,
  useLearningItems,
  useLearningRecommendations,
  useMoveLearningItem,
  useRegenerateLearningRecommendations,
  useUpdateLearningItem,
} from "@/api/queries/learning-intelligence";
import { useGapAnalysis } from "@/api/queries/skill-intelligence";
import type { components } from "@/api/schema.gen";
import { Badge } from "@/components/ui/badge";
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
import { getErrorMessage } from "@/lib/errors";
import { RefreshCw } from "lucide-react";
import { Pencil, Plus, Trash2 } from "lucide-react";
import { type FormEvent, useEffect, useState } from "react";

type LearningItem = components["schemas"]["LearningItemResponse"];

interface FormState {
  title: string;
  provider: string;
  url: string;
  status: string;
  target_role_id: string;
  notes: string;
}

const EMPTY_FORM: FormState = {
  title: "",
  provider: "",
  url: "",
  status: "planned",
  target_role_id: "",
  notes: "",
};

function toFormState(item: LearningItem): FormState {
  return {
    title: item.title,
    provider: item.provider ?? "",
    url: item.url ?? "",
    status: item.status,
    target_role_id: item.target_role_id ?? "",
    notes: item.notes ?? "",
  };
}

const STATUS_LABELS: Record<string, string> = {
  planned: "Planned",
  in_progress: "In progress",
  completed: "Completed",
};

/**
 * Phase 7 — Learning Intelligence. Two independent sections: a
 * self-managed learning log (CRUD+reorder, same pattern as
 * CertificationSection.tsx) and AI-generated recommendations per target
 * role, reusing useGapAnalysis() directly rather than re-fetching gap
 * data. Single-file page, matching ResumeIntelligencePage.tsx's
 * precedent for a feature this size.
 */
export function LearningIntelligencePage() {
  const { data: items, isLoading: itemsLoading } = useLearningItems();
  const addItem = useAddLearningItem();
  const updateItem = useUpdateLearningItem();
  const deleteItem = useDeleteLearningItem();
  const moveItem = useMoveLearningItem();
  const { data: targetRoles } = useTargetRoles();
  const { data: gapAnalysis } = useGapAnalysis();

  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [form, setForm] = useState<FormState>(EMPTY_FORM);
  const [deleteTarget, setDeleteTarget] = useState<LearningItem | null>(null);

  const [selectedRoleId, setSelectedRoleId] = useState<string | null>(null);
  useEffect(() => {
    if (!selectedRoleId && targetRoles && targetRoles.length > 0) {
      setSelectedRoleId(targetRoles[0]!.id);
    }
  }, [targetRoles, selectedRoleId]);
  const {
    data: recommendations,
    isLoading: recommendationsLoading,
  } = useLearningRecommendations(selectedRoleId);
  const regenerate = useRegenerateLearningRecommendations();

  function openAddDialog() {
    setEditingId(null);
    setForm(EMPTY_FORM);
    setDialogOpen(true);
  }

  function openEditDialog(item: LearningItem) {
    setEditingId(item.id);
    setForm(toFormState(item));
    setDialogOpen(true);
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (editingId) {
      updateItem
        .mutateAsync({
          id: editingId,
          body: {
            title: form.title,
            provider: form.provider || null,
            url: form.url || null,
            status: form.status,
            target_role_id: form.target_role_id || null,
            notes: form.notes || null,
          },
        })
        .then(() => setDialogOpen(false))
        .catch(() => {});
    } else {
      addItem
        .mutateAsync({
          title: form.title,
          provider: form.provider || null,
          url: form.url || null,
          target_role_id: form.target_role_id || null,
          notes: form.notes || null,
        })
        .then(() => setDialogOpen(false))
        .catch(() => {});
    }
  }

  const isSaving = addItem.isPending || updateItem.isPending;
  const saveError = addItem.error ?? updateItem.error;
  const gapForSelectedRole = gapAnalysis?.target_role_gaps.find(
    (g) => g.target_role_id === selectedRoleId,
  );

  return (
    <div className="flex flex-col gap-6">
      <Card>
        <CardHeader className="flex-row items-start justify-between space-y-0">
          <CardTitle>Learning Log</CardTitle>
          <Button variant="ghost" size="sm" onClick={openAddDialog}>
            <Plus className="h-4 w-4" />
            Add
          </Button>
        </CardHeader>
        <CardContent className="flex flex-col gap-3">
          {itemsLoading && <p className="text-sm text-muted-foreground">Loading...</p>}
          {items?.length === 0 && (
            <p className="text-sm text-muted-foreground">
              No learning items yet — add a course, book, or certification you're working toward.
            </p>
          )}
          {items?.map((item, index) => (
            <div
              key={item.id}
              className="flex items-start justify-between gap-4 rounded-md border border-border p-4"
            >
              <MoveButtons
                onMoveUp={() => moveItem.mutate({ id: item.id, direction: "up" })}
                onMoveDown={() => moveItem.mutate({ id: item.id, direction: "down" })}
                isFirst={index === 0}
                isLast={index === items.length - 1}
                disabled={moveItem.isPending}
              />
              <div className="flex-1">
                <div className="flex items-center gap-2">
                  <p className="text-sm font-medium md:text-base">{item.title}</p>
                  <Badge variant={item.status === "completed" ? "accent" : "default"}>
                    {STATUS_LABELS[item.status] ?? item.status}
                  </Badge>
                </div>
                {item.provider && (
                  <p className="text-sm text-muted-foreground">{item.provider}</p>
                )}
                {item.notes && (
                  <RichTextDisplay html={item.notes} className="text-xs text-muted-foreground" />
                )}
              </div>
              <div className={`flex shrink-0 ${ACTION_BUTTON_ROW_GAP}`}>
                <Button variant="ghost" size="sm" onClick={() => openEditDialog(item)}>
                  <Pencil className="h-4 w-4" />
                </Button>
                <Button variant="ghost" size="sm" onClick={() => setDeleteTarget(item)}>
                  <Trash2 className="h-4 w-4" />
                </Button>
              </div>
            </div>
          ))}
        </CardContent>
      </Card>

      {targetRoles && targetRoles.length > 0 && (
        <Card>
          <CardHeader className="flex-row items-start justify-between space-y-0">
            <CardTitle>Recommended Resources</CardTitle>
            {selectedRoleId && (
              <Button
                variant="ghost"
                size="sm"
                onClick={() => regenerate.mutate(selectedRoleId)}
                disabled={regenerate.isPending}
              >
                <RefreshCw className="h-4 w-4" />
                {regenerate.isPending ? "Regenerating..." : "Regenerate"}
              </Button>
            )}
          </CardHeader>
          <CardContent className="flex flex-col gap-4">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="learning-target-role">Target role</Label>
              <Select
                id="learning-target-role"
                className="w-72"
                value={selectedRoleId ?? ""}
                onChange={(e) => setSelectedRoleId(e.target.value || null)}
              >
                {targetRoles.map((role) => (
                  <option key={role.id} value={role.id}>
                    {role.role_name}
                  </option>
                ))}
              </Select>
            </div>

            {recommendationsLoading && (
              <p className="text-sm text-muted-foreground">
                Generating recommendations — this can take a moment...
              </p>
            )}

            {recommendations?.status === "failed" && (
              <p role="alert" className="text-sm text-destructive">
                {recommendations.error_message ?? "Something went wrong generating recommendations."}
              </p>
            )}

            {recommendations?.status === "generated" &&
              (recommendations.recommendations?.length ?? 0) === 0 && (
                <p className="text-sm text-muted-foreground">
                  {gapForSelectedRole
                    ? "No missing skills for this role — nothing to recommend."
                    : "No skill gaps found for this role."}
                </p>
              )}

            {recommendations?.recommendations?.map((rec) => (
              <div key={rec.skill} className="flex flex-col gap-1.5 rounded-md border border-border p-4">
                <Badge variant="accent">{rec.skill}</Badge>
                <p className="text-sm text-muted-foreground">{rec.summary}</p>
                <ul className="ml-4 list-disc text-sm">
                  {rec.resources.map((resource) => (
                    <li key={resource}>{resource}</li>
                  ))}
                </ul>
              </div>
            ))}
          </CardContent>
        </Card>
      )}

      <Dialog
        open={dialogOpen}
        onClose={() => setDialogOpen(false)}
        title={editingId ? "Edit learning item" : "Add learning item"}
      >
        <form className="flex flex-col gap-4" onSubmit={handleSubmit}>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="li-title">Title</Label>
            <Input
              id="li-title"
              required
              value={form.title}
              onChange={(e) => setForm({ ...form, title: e.target.value })}
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="li-provider">Provider</Label>
            <Input
              id="li-provider"
              value={form.provider}
              onChange={(e) => setForm({ ...form, provider: e.target.value })}
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="li-url">URL</Label>
            <Input
              id="li-url"
              type="url"
              value={form.url}
              onChange={(e) => setForm({ ...form, url: e.target.value })}
            />
          </div>
          {editingId && (
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="li-status">Status</Label>
              <Select
                id="li-status"
                value={form.status}
                onChange={(e) => setForm({ ...form, status: e.target.value })}
              >
                <option value="planned">Planned</option>
                <option value="in_progress">In progress</option>
                <option value="completed">Completed</option>
              </Select>
            </div>
          )}
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="li-target-role">Target role (optional)</Label>
            <Select
              id="li-target-role"
              value={form.target_role_id}
              onChange={(e) => setForm({ ...form, target_role_id: e.target.value })}
            >
              <option value="">None</option>
              {targetRoles?.map((role) => (
                <option key={role.id} value={role.id}>
                  {role.role_name}
                </option>
              ))}
            </Select>
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="li-notes">Notes</Label>
            <RichTextEditor
              id="li-notes"
              defaultValue={form.notes}
              onChange={(html) => setForm({ ...form, notes: html })}
            />
          </div>
          <Button type="submit" disabled={isSaving}>
            {isSaving ? "Saving..." : editingId ? "Save changes" : "Add item"}
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
          if (deleteTarget) deleteItem.mutate(deleteTarget.id);
          setDeleteTarget(null);
        }}
        title="Delete learning item?"
        description={deleteTarget ? `Remove "${deleteTarget.title}"? This can't be undone.` : ""}
        isPending={deleteItem.isPending}
      />
    </div>
  );
}
