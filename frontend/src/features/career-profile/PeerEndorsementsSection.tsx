import {
  useAddPeerEndorsement,
  useClearPeerEndorsements,
  useDeletePeerEndorsement,
  useMovePeerEndorsement,
  usePeerEndorsements,
  useUpdatePeerEndorsement,
} from "@/api/queries/career-profile";
import type { components } from "@/api/schema.gen";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ACTION_BUTTON_ROW_GAP } from "@/components/ui/button-variants";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
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
import { getErrorMessage } from "@/lib/errors";
import { cn } from "@/lib/utils";
import { Eraser, Pencil, Plus, Quote, Trash2 } from "lucide-react";
import { type FormEvent, useState } from "react";

type PeerEndorsement = components["schemas"]["PeerEndorsementResponse"];

interface FormState {
  recommender_name: string;
  recommender_title: string;
  relationship: string;
  content: string;
  include_in_resume: boolean;
}

const EMPTY_FORM: FormState = {
  recommender_name: "",
  recommender_title: "",
  relationship: "",
  content: "",
  include_in_resume: true,
};

function toFormState(endorsement: PeerEndorsement): FormState {
  return {
    recommender_name: endorsement.recommender_name,
    recommender_title: endorsement.recommender_title ?? "",
    relationship: endorsement.relationship ?? "",
    content: endorsement.content,
    include_in_resume: endorsement.include_in_resume,
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
  resumeIncluded,
  onToggleResumeIncluded,
  resumeToggleDisabled,
}: SectionOrderProps) {
  const { data: endorsements, isLoading } = usePeerEndorsements();
  const addEndorsement = useAddPeerEndorsement();
  const updateEndorsement = useUpdatePeerEndorsement();
  const deleteEndorsement = useDeletePeerEndorsement();
  const clearEndorsements = useClearPeerEndorsements();
  const moveEndorsement = useMovePeerEndorsement();
  // Peer Endorsements stay Master-only regardless of which profile is
  // being viewed — see CareerGoalsSection's identical note.
  const isTargetRoleView = useProfileScope() !== null;

  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [form, setForm] = useState<FormState>(EMPTY_FORM);
  const [isOpen, setIsOpen] = useState(false);
  const [isEditMode, setIsEditMode] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<PeerEndorsement | null>(null);
  const [clearSectionOpen, setClearSectionOpen] = useState(false);

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
      include_in_resume: form.include_in_resume,
    };
    const mutation = editingId
      ? updateEndorsement.mutateAsync({ id: editingId, body })
      : addEndorsement.mutateAsync(body);
    mutation
      .then(() => {
        setDialogOpen(false);
        if (!editingId) setIsOpen(true);
      })
      .catch(() => {});
  }

  function toggleItemResume(endorsement: PeerEndorsement, include: boolean) {
    updateEndorsement.mutate({
      id: endorsement.id,
      body: {
        recommender_name: endorsement.recommender_name,
        recommender_title: endorsement.recommender_title,
        relationship: endorsement.relationship,
        content: endorsement.content,
        include_in_resume: include,
      },
    });
  }

  const isSaving = addEndorsement.isPending || updateEndorsement.isPending;
  const saveError = addEndorsement.error ?? updateEndorsement.error;

  return (
    <Card className={cardBackground === "background" ? "bg-background" : undefined}>
      <CardHeader className="flex-row items-start justify-between space-y-0">
        <div>
          <div className="flex items-center gap-2">
            <CardTitle>Recommendations</CardTitle>
            {isTargetRoleView && <Badge variant="default">Master profile</Badge>}
          </div>
          <CardDescription>Testimonials from colleagues and managers</CardDescription>
        </div>
        <div className={cn("flex items-start", ACTION_BUTTON_ROW_GAP)}>
          <ResumeIncludeToggle
            checked={resumeIncluded}
            onCheckedChange={onToggleResumeIncluded}
            disabled={resumeToggleDisabled}
            label="the Recommendations section"
          />
          <Button variant="ghost" size="sm" onClick={openAddDialog}>
            <Plus className="h-4 w-4" />
            Add
          </Button>
          <Button variant="ghost" size="sm" onClick={() => setIsEditMode((v) => !v)}>
            {isEditMode ? "Done" : "Edit"}
          </Button>
          {!!endorsements?.length && (
            <Button variant="ghost" size="sm" onClick={() => setClearSectionOpen(true)}>
              <Eraser className="h-4 w-4" />
              Clear
            </Button>
          )}
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
            {isEditMode && (
              <MoveButtons
                onMoveUp={() => moveEndorsement.mutate({ id: endorsement.id, direction: "up" })}
                onMoveDown={() => moveEndorsement.mutate({ id: endorsement.id, direction: "down" })}
                isFirst={index === 0}
                isLast={index === endorsements.length - 1}
                disabled={moveEndorsement.isPending}
              />
            )}
            <div className="flex-1">
              <Quote className="h-4 w-4 text-accent" />
              <div className="mt-1 text-sm italic">
                <span>&ldquo;</span>
                <RichTextDisplay html={endorsement.content} className="inline-block align-baseline" />
                <span>&rdquo;</span>
              </div>
              <p className="mt-2 text-sm font-medium">{endorsement.recommender_name}</p>
              <p className="text-xs text-muted-foreground">
                {[endorsement.recommender_title, endorsement.relationship]
                  .filter(Boolean)
                  .join(" · ")}
              </p>
            </div>
            <div className={cn("flex shrink-0", ACTION_BUTTON_ROW_GAP)}>
              <ResumeIncludeToggle
                checked={endorsement.include_in_resume}
                onCheckedChange={(checked) => toggleItemResume(endorsement, checked)}
                disabled={updateEndorsement.isPending}
                label={`the recommendation from "${endorsement.recommender_name}"`}
              />
              {isEditMode && (
                <>
                  <Button variant="ghost" size="sm" onClick={() => openEditDialog(endorsement)}>
                    <Pencil className="h-4 w-4" />
                  </Button>
                  <Button variant="ghost" size="sm" onClick={() => setDeleteTarget(endorsement)}>
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
            <RichTextEditor
              id="rec-content"
              defaultValue={form.content}
              onChange={(html) => setForm({ ...form, content: html })}
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

      <ConfirmDialog
        open={clearSectionOpen}
        onCancel={() => setClearSectionOpen(false)}
        onConfirm={() => {
          clearEndorsements.mutate();
          setClearSectionOpen(false);
        }}
        title="Clear Recommendations?"
        description="Remove every recommendation from your profile? This can't be undone."
        isPending={clearEndorsements.isPending}
        confirmLabel="Clear"
        confirmPendingLabel="Clearing..."
      />
    </Card>
  );
}
