import {
  useAddPeerEndorsement,
  useDeletePeerEndorsement,
  useMovePeerEndorsement,
  usePeerEndorsements,
  useUpdatePeerEndorsement,
} from "@/api/queries/career-profile";
import type { components } from "@/api/schema.gen";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { CollapseToggle } from "@/components/ui/collapse-toggle";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { Dialog } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { MoveButtons } from "@/components/ui/move-buttons";
import { Textarea } from "@/components/ui/textarea";
import { itemAlternateClass, type SectionOrderProps } from "@/features/career-profile/section-order";
import { getErrorMessage } from "@/lib/errors";
import { cn } from "@/lib/utils";
import { Pencil, Plus, Quote, Trash2 } from "lucide-react";
import { type FormEvent, useState } from "react";

type PeerEndorsement = components["schemas"]["PeerEndorsementResponse"];

interface FormState {
  recommender_name: string;
  recommender_title: string;
  relationship: string;
  content: string;
}

const EMPTY_FORM: FormState = {
  recommender_name: "",
  recommender_title: "",
  relationship: "",
  content: "",
};

function toFormState(endorsement: PeerEndorsement): FormState {
  return {
    recommender_name: endorsement.recommender_name,
    recommender_title: endorsement.recommender_title ?? "",
    relationship: endorsement.relationship ?? "",
    content: endorsement.content,
  };
}

/**
 * Self-managed for now: the profile owner pastes in a testimonial they
 * received elsewhere (email, LinkedIn, etc.) rather than inviting the
 * recommender to submit it directly through the platform. See the
 * Phase 2 follow-up decision — a full invite-and-submit flow, and/or
 * AI-generated recommendations, are candidates for a later phase.
 */
export function PeerEndorsementsSection({
  onMoveUp,
  onMoveDown,
  isFirst,
  isLast,
  moveDisabled,
  cardBackground,
}: SectionOrderProps) {
  const { data: endorsements, isLoading } = usePeerEndorsements();
  const addEndorsement = useAddPeerEndorsement();
  const updateEndorsement = useUpdatePeerEndorsement();
  const deleteEndorsement = useDeletePeerEndorsement();
  const moveEndorsement = useMovePeerEndorsement();

  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [form, setForm] = useState<FormState>(EMPTY_FORM);
  const [isOpen, setIsOpen] = useState(true);
  const [deleteTarget, setDeleteTarget] = useState<PeerEndorsement | null>(null);

  function openAddDialog() {
    setEditingId(null);
    setForm(EMPTY_FORM);
    setDialogOpen(true);
  }

  function openEditDialog(endorsement: PeerEndorsement) {
    setEditingId(endorsement.id);
    setForm(toFormState(endorsement));
    setDialogOpen(true);
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const body = {
      recommender_name: form.recommender_name,
      recommender_title: form.recommender_title || null,
      relationship: form.relationship || null,
      content: form.content,
    };
    const mutation = editingId
      ? updateEndorsement.mutateAsync({ id: editingId, body })
      : addEndorsement.mutateAsync(body);
    mutation.then(() => setDialogOpen(false)).catch(() => {});
  }

  const isSaving = addEndorsement.isPending || updateEndorsement.isPending;
  const saveError = addEndorsement.error ?? updateEndorsement.error;

  return (
    <Card className={cardBackground === "background" ? "bg-background" : undefined}>
      <CardHeader className="flex-row items-center justify-between space-y-0">
        <div>
          <CardTitle>Recommendations</CardTitle>
          <CardDescription>Testimonials from colleagues and managers</CardDescription>
        </div>
        <div className="flex items-center gap-1">
          <Button variant="outline" size="sm" onClick={openAddDialog}>
            <Plus className="h-4 w-4" />
            Add
          </Button>
          <CollapseToggle
            isOpen={isOpen}
            onToggle={() => setIsOpen(!isOpen)}
            label="Recommendations"
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
        {endorsements?.length === 0 && (
          <p className="text-sm text-muted-foreground">
            No recommendations added yet — add a testimonial you've received from a colleague or
            manager.
          </p>
        )}
        {endorsements?.map((endorsement, index) => (
          <div
            key={endorsement.id}
            className={cn(
              "flex items-start justify-between gap-4 rounded-md border border-border p-4",
              itemAlternateClass(cardBackground, index),
            )}
          >
            <MoveButtons
              onMoveUp={() => moveEndorsement.mutate({ id: endorsement.id, direction: "up" })}
              onMoveDown={() => moveEndorsement.mutate({ id: endorsement.id, direction: "down" })}
              isFirst={index === 0}
              isLast={index === endorsements.length - 1}
              disabled={moveEndorsement.isPending}
            />
            <div className="flex-1">
              <Quote className="h-4 w-4 text-accent" />
              <p className="mt-1 text-sm italic">&ldquo;{endorsement.content}&rdquo;</p>
              <p className="mt-2 text-sm font-medium">{endorsement.recommender_name}</p>
              <p className="text-xs text-muted-foreground">
                {[endorsement.recommender_title, endorsement.relationship]
                  .filter(Boolean)
                  .join(" · ")}
              </p>
            </div>
            <div className="flex shrink-0 gap-1">
              <Button variant="ghost" size="sm" onClick={() => openEditDialog(endorsement)}>
                <Pencil className="h-4 w-4" />
              </Button>
              <Button variant="ghost" size="sm" onClick={() => setDeleteTarget(endorsement)}>
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
        title={editingId ? "Edit recommendation" : "Add recommendation"}
      >
        <form className="flex flex-col gap-4" onSubmit={handleSubmit}>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="rec-name">Recommender name</Label>
            <Input
              id="rec-name"
              required
              value={form.recommender_name}
              onChange={(e) => setForm({ ...form, recommender_name: e.target.value })}
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="rec-title">Recommender title</Label>
            <Input
              id="rec-title"
              value={form.recommender_title}
              onChange={(e) => setForm({ ...form, recommender_title: e.target.value })}
              placeholder="e.g. VP Engineering"
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="rec-relationship">Relationship</Label>
            <Input
              id="rec-relationship"
              value={form.relationship}
              onChange={(e) => setForm({ ...form, relationship: e.target.value })}
              placeholder="e.g. Former manager"
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="rec-content">Recommendation</Label>
            <Textarea
              id="rec-content"
              required
              value={form.content}
              onChange={(e) => setForm({ ...form, content: e.target.value })}
              rows={4}
            />
          </div>
          <Button type="submit" disabled={isSaving}>
            {isSaving ? "Saving..." : editingId ? "Save changes" : "Add recommendation"}
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
          if (deleteTarget) deleteEndorsement.mutate(deleteTarget.id);
          setDeleteTarget(null);
        }}
        title="Delete recommendation?"
        description={
          deleteTarget
            ? `Remove the recommendation from "${deleteTarget.recommender_name}"? This can't be undone.`
            : ""
        }
        isPending={deleteEndorsement.isPending}
      />
    </Card>
  );
}
