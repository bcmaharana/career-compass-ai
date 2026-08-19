import {
  useCreateInterviewTopic,
  useDeleteInterviewTopic,
  useDeleteTopicImage,
  useInterviewTopics,
  useMoveInterviewTopic,
  useUpdateInterviewTopic,
  useUploadTopicImage,
} from "@/api/queries/interview-prep";
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
import { RichTextDisplay, RichTextEditor } from "@/components/ui/rich-text-editor";
import { DeleteScopeChoiceDialog } from "@/features/interview-prep/DeleteScopeChoiceDialog";
import { ScopeTagSelector, type ScopeOption } from "@/features/interview-prep/ScopeTagSelector";
import { groupInterviewTopicsBySection } from "@/lib/group-interview-topics-by-section";
import { getErrorMessage } from "@/lib/errors";
import { cn } from "@/lib/utils";
import { ImageOff, Pencil, Plus, Trash2, Upload, X } from "lucide-react";
import { type Dispatch, type FormEvent, type SetStateAction, useRef, useState } from "react";

type InterviewTopic = components["schemas"]["InterviewTopicResponse"];
type ReferenceLink = components["schemas"]["ReferenceLinkPayload"];
type TargetRole = components["schemas"]["TargetRoleResponse"];

interface FormState {
  name: string;
  section: string;
  scopeTargetRoleIds: (string | null)[];
}

function toFormState(topic: InterviewTopic): FormState {
  return {
    name: topic.name,
    section: topic.section ?? "",
    scopeTargetRoleIds: topic.scope_target_role_ids,
  };
}

/** Scope label for a delete-choice dialog's "Remove from X only" —
 * "Master" for null, the role's name otherwise. */
function scopeLabelFor(targetRoleId: string | null, targetRoles: TargetRole[]): string {
  if (targetRoleId === null) return "Master";
  return targetRoles.find((r) => r.id === targetRoleId)?.role_name ?? "this role";
}

export function InterviewTopicsSection({
  scope,
  targetRoles,
  expandedId,
  setExpandedId,
  sectionFilter,
}: {
  scope: string | null;
  targetRoles: TargetRole[];
  // Accordion state, lifted up to InterviewPrepPage so the page's Table
  // of Contents can force a specific topic open (and scroll to it)
  // without going through this component's own toggle semantics — a TOC
  // click on an already-open topic must never close it, unlike a click
  // on the card itself.
  expandedId: string | null;
  setExpandedId: Dispatch<SetStateAction<string | null>>;
  // Which section's sub-tab is active, lifted up to InterviewPrepPage so
  // its sub-tab strip and Table of Contents stay in sync with what this
  // card actually renders — `"all"` shows every group, `null` shows only
  // topics with no section set (the same null-means-ungrouped convention
  // groupInterviewTopicsBySection already uses), any other string shows
  // only that one section's topics.
  sectionFilter: string | null;
}) {
  const { data: topics, isLoading } = useInterviewTopics(scope);
  const addTopic = useCreateInterviewTopic(scope);
  const updateTopic = useUpdateInterviewTopic(scope);
  const deleteTopic = useDeleteInterviewTopic(scope);
  const moveTopic = useMoveInterviewTopic(scope);
  const uploadImage = useUploadTopicImage(scope);
  const deleteImage = useDeleteTopicImage(scope);

  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [form, setForm] = useState<FormState>({ name: "", section: "", scopeTargetRoleIds: [scope] });
  const [isEditMode, setIsEditMode] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<InterviewTopic | null>(null);
  const [imageError, setImageError] = useState<string | null>(null);
  const fileInputRefs = useRef<Map<string, HTMLInputElement>>(new Map());

  const scopeOptions: ScopeOption[] = [
    { id: null, label: "Master (generic)" },
    ...targetRoles.map((r) => ({ id: r.id, label: r.role_name })),
  ];

  function toggleExpanded(id: string) {
    setExpandedId((prev) => (prev === id ? null : id));
  }

  function openAddDialog() {
    setEditingId(null);
    setForm({ name: "", section: "", scopeTargetRoleIds: [scope] });
    setDialogOpen(true);
  }

  function openEditDialog(topic: InterviewTopic) {
    setEditingId(topic.id);
    setForm(toFormState(topic));
    setDialogOpen(true);
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const name = form.name;
    const section = form.section.trim() || null;
    if (editingId) {
      const existing = topics?.find((t) => t.id === editingId);
      updateTopic
        .mutateAsync({
          id: editingId,
          body: {
            name,
            section,
            discussion: existing?.discussion ?? null,
            reference_links: existing?.reference_links ?? [],
            scope_target_role_ids: form.scopeTargetRoleIds,
          },
        })
        .then(() => setDialogOpen(false))
        .catch(() => {});
    } else {
      addTopic
        .mutateAsync({ name, section, discussion: null, scope_target_role_ids: form.scopeTargetRoleIds })
        .then((created) => {
          setDialogOpen(false);
          setExpandedId(created.id);
        })
        .catch(() => {});
    }
  }

  function handleFileChange(topicId: string, event: React.ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;
    setImageError(null);
    uploadImage.mutate(
      { id: topicId, file },
      { onError: (error) => setImageError(getErrorMessage(error)) },
    );
  }

  const sectionOptions = Array.from(
    new Set((topics ?? []).map((t) => t.section?.trim()).filter((s): s is string => !!s)),
  );
  const groups = groupInterviewTopicsBySection(topics ?? []);
  const visibleGroups =
    sectionFilter === "all" ? groups : groups.filter((group) => group.section === sectionFilter);

  return (
    <Card>
      <CardHeader className="flex-row items-center justify-between space-y-0">
        <CardTitle>Topics</CardTitle>
        <div className={cn("flex items-center", ACTION_BUTTON_ROW_GAP)}>
          <Button variant="ghost" size="sm" onClick={openAddDialog}>
            <Plus className="h-3.5 w-3.5" />
            Add
          </Button>
          <Button variant="ghost" size="sm" onClick={() => setIsEditMode((v) => !v)}>
            {isEditMode ? "Done" : "Edit"}
          </Button>
        </div>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        {isLoading && <p className="text-sm text-muted-foreground">Loading...</p>}
        {topics?.length === 0 && (
          <p className="text-sm text-muted-foreground">
            No topics yet — add one to start building your study notes.
          </p>
        )}
        {/* Only reachable if the sub-tab's own section was emptied out
            (e.g. its last topic was edited into a different section)
            while it stayed selected — the sub-tab strip itself doesn't
            auto-switch away, so this avoids a silently blank card body. */}
        {topics && topics.length > 0 && visibleGroups.length === 0 && (
          <p className="text-sm text-muted-foreground">No topics in this section.</p>
        )}
        {imageError && (
          <p role="alert" className="text-sm text-destructive">
            {imageError}
          </p>
        )}

        {visibleGroups.map((group) => (
          <div key={group.section ?? "__ungrouped"} className="flex flex-col gap-2">
            {group.section && (
              <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                {group.section}
              </p>
            )}
            {group.topics.map((topic) => {
              const allInScope = topics ?? [];
              const scopeIndex = allInScope.findIndex((t) => t.id === topic.id);
              return (
                <TopicCard
                  key={topic.id}
                  topic={topic}
                  scopeIndex={scopeIndex}
                  total={allInScope.length}
                  isEditMode={isEditMode}
                  isOpen={expandedId === topic.id}
                  onToggleOpen={() => toggleExpanded(topic.id)}
                  onEdit={() => openEditDialog(topic)}
                  onDelete={() => setDeleteTarget(topic)}
                  onMove={(direction) => moveTopic.mutate({ id: topic.id, direction })}
                  moveDisabled={moveTopic.isPending}
                  scope={scope}
                  uploadImage={uploadImage}
                  deleteImage={deleteImage}
                  onFileChange={handleFileChange}
                  fileInputRefs={fileInputRefs}
                />
              );
            })}
          </div>
        ))}
      </CardContent>

      <Dialog
        open={dialogOpen}
        onClose={() => setDialogOpen(false)}
        title={editingId ? "Edit topic" : "Add topic"}
      >
        <form className="flex flex-col gap-4" onSubmit={handleSubmit}>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="topic-name">Name</Label>
            <Input
              id="topic-name"
              required
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="topic-section">Section (optional)</Label>
            <Input
              id="topic-section"
              list="interview-topic-sections"
              value={form.section}
              onChange={(e) => setForm({ ...form, section: e.target.value })}
              placeholder="e.g. Technical, Behavioral"
            />
            <datalist id="interview-topic-sections">
              {sectionOptions.map((option) => (
                <option key={option} value={option} />
              ))}
            </datalist>
          </div>
          <ScopeTagSelector
            id="topic-scopes"
            options={scopeOptions}
            selected={form.scopeTargetRoleIds}
            onChange={(next) => setForm({ ...form, scopeTargetRoleIds: next })}
          />
          {form.scopeTargetRoleIds.length === 0 && (
            <p role="alert" className="text-sm text-destructive">
              Select at least one scope.
            </p>
          )}
          <Button
            type="submit"
            disabled={
              addTopic.isPending || updateTopic.isPending || form.scopeTargetRoleIds.length === 0
            }
          >
            {addTopic.isPending || updateTopic.isPending
              ? "Saving..."
              : editingId
                ? "Save changes"
                : "Add topic"}
          </Button>
          {(addTopic.error ?? updateTopic.error) && (
            <p role="alert" className="text-sm text-destructive">
              {getErrorMessage(addTopic.error ?? updateTopic.error)}
            </p>
          )}
        </form>
      </Dialog>

      {deleteTarget && deleteTarget.scope_target_role_ids.length > 1 ? (
        <DeleteScopeChoiceDialog
          open={deleteTarget !== null}
          onCancel={() => setDeleteTarget(null)}
          onRemoveFromScope={() => {
            deleteTopic.mutate({ id: deleteTarget.id, deleteEverywhere: false });
            setDeleteTarget(null);
          }}
          onDeleteEverywhere={() => {
            deleteTopic.mutate({ id: deleteTarget.id, deleteEverywhere: true });
            setDeleteTarget(null);
          }}
          itemLabel={deleteTarget.name}
          scopeLabel={scopeLabelFor(scope, targetRoles)}
          isPending={deleteTopic.isPending}
        />
      ) : (
        <ConfirmDialog
          open={deleteTarget !== null}
          onCancel={() => setDeleteTarget(null)}
          onConfirm={() => {
            if (deleteTarget) deleteTopic.mutate({ id: deleteTarget.id, deleteEverywhere: true });
            setDeleteTarget(null);
          }}
          title="Delete topic?"
          description={
            deleteTarget
              ? `Remove "${deleteTarget.name}"? Any questions linked to it will be un-linked, not deleted. This can't be undone.`
              : ""
          }
          isPending={deleteTopic.isPending}
        />
      )}
    </Card>
  );
}

function TopicCard({
  topic,
  scopeIndex,
  total,
  isEditMode,
  isOpen,
  onToggleOpen,
  onEdit,
  onDelete,
  onMove,
  moveDisabled,
  scope,
  uploadImage,
  deleteImage,
  onFileChange,
  fileInputRefs,
}: {
  topic: InterviewTopic;
  scopeIndex: number;
  total: number;
  isEditMode: boolean;
  isOpen: boolean;
  onToggleOpen: () => void;
  onEdit: () => void;
  onDelete: () => void;
  onMove: (direction: "up" | "down") => void;
  moveDisabled: boolean;
  scope: string | null;
  uploadImage: ReturnType<typeof useUploadTopicImage>;
  deleteImage: ReturnType<typeof useDeleteTopicImage>;
  onFileChange: (topicId: string, event: React.ChangeEvent<HTMLInputElement>) => void;
  fileInputRefs: React.MutableRefObject<Map<string, HTMLInputElement>>;
}) {
  const updateTopic = useUpdateInterviewTopic(scope);

  // Discussion gets its own sub-card, mirroring InterviewQuestionsSection's
  // Answer sub-card: readonly display + Edit button by default, swapping
  // to a RichTextEditor + Save/Cancel only while actively editing. Draft
  // is seeded fresh each time editing starts (not kept in sync
  // reactively), same "initialize once at the moment edit opens"
  // convention every other edit form in this app already follows.
  const [isEditingDiscussion, setIsEditingDiscussion] = useState(false);
  const [discussionDraft, setDiscussionDraft] = useState(topic.discussion ?? "");

  function startEditingDiscussion() {
    setDiscussionDraft(topic.discussion ?? "");
    setIsEditingDiscussion(true);
  }

  function saveDiscussion() {
    updateTopic.mutate(
      {
        id: topic.id,
        body: {
          name: topic.name,
          section: topic.section,
          discussion: discussionDraft || null,
          reference_links: topic.reference_links,
          scope_target_role_ids: topic.scope_target_role_ids,
        },
      },
      { onSuccess: () => setIsEditingDiscussion(false) },
    );
  }

  // Reference Links, mirroring InterviewQuestionsSection's own inline
  // add/remove UX exactly — same quick-add-without-a-dialog form, and
  // the same confirm-before-delete convention this app uses everywhere
  // else, applied here after a real user report caught the "x" button
  // deleting immediately with no confirmation on Questions' own list.
  const [linkUrl, setLinkUrl] = useState("");
  const [linkLabel, setLinkLabel] = useState("");
  const [deleteLinkIndex, setDeleteLinkIndex] = useState<number | null>(null);

  function addLink(event: FormEvent) {
    event.preventDefault();
    if (!linkUrl.trim() || !linkLabel.trim()) return;
    const nextLinks: ReferenceLink[] = [
      ...topic.reference_links,
      { url: linkUrl.trim(), label: linkLabel.trim() },
    ];
    updateTopic.mutate({
      id: topic.id,
      body: {
        name: topic.name,
        section: topic.section,
        discussion: topic.discussion,
        reference_links: nextLinks,
        scope_target_role_ids: topic.scope_target_role_ids,
      },
    });
    setLinkUrl("");
    setLinkLabel("");
  }

  function confirmRemoveLink() {
    if (deleteLinkIndex === null) return;
    const nextLinks = topic.reference_links.filter((_, i) => i !== deleteLinkIndex);
    updateTopic.mutate({
      id: topic.id,
      body: {
        name: topic.name,
        section: topic.section,
        discussion: topic.discussion,
        reference_links: nextLinks,
        scope_target_role_ids: topic.scope_target_role_ids,
      },
    });
    setDeleteLinkIndex(null);
  }

  return (
    <div
      id={`interview-topic-${topic.id}`}
      className={cn(
        "rounded-md border border-border",
        scopeIndex % 2 === 0 ? "bg-card" : "bg-muted",
      )}
    >
      <div className="flex cursor-pointer items-start justify-between gap-3 px-3 py-2" onClick={onToggleOpen}>
        <div className="flex items-center gap-2">
          {isEditMode && (
            <div onClick={(e) => e.stopPropagation()}>
              <MoveButtons
                onMoveUp={() => onMove("up")}
                onMoveDown={() => onMove("down")}
                isFirst={scopeIndex === 0}
                isLast={scopeIndex === total - 1}
                disabled={moveDisabled}
                className="h-7 w-7 p-0"
              />
            </div>
          )}
          <p className="text-sm font-medium">{topic.name}</p>
        </div>
        <div
          className={cn("flex shrink-0 items-center", ACTION_BUTTON_ROW_GAP)}
          onClick={(e) => e.stopPropagation()}
        >
          {isEditMode && (
            <>
              <Button variant="ghost" size="sm" className="h-7 w-7 p-0" onClick={onEdit}>
                <Pencil className="h-3.5 w-3.5" />
              </Button>
              <Button variant="ghost" size="sm" className="h-7 w-7 p-0" onClick={onDelete}>
                <Trash2 className="h-3.5 w-3.5" />
              </Button>
            </>
          )}
          <CollapseToggle
            isOpen={isOpen}
            onToggle={onToggleOpen}
            label={topic.name}
            className="h-7 w-7 p-0"
          />
        </div>
      </div>

      {isOpen && (
        <div className="flex flex-col gap-3 border-t border-border p-3">
          <div className="flex flex-col gap-2 rounded-md border border-border bg-background p-3">
            <div className="flex items-center justify-between gap-2">
              <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                Discussion
              </p>
              {!isEditingDiscussion && (
                <Button variant="ghost" size="sm" onClick={startEditingDiscussion}>
                  <Pencil className="h-3.5 w-3.5" />
                  Edit
                </Button>
              )}
            </div>
            {isEditingDiscussion ? (
              <>
                <RichTextEditor
                  defaultValue={discussionDraft}
                  onChange={setDiscussionDraft}
                  placeholder="Notes to help you understand this topic..."
                  autoFocus
                />
                <div className={cn("flex", ACTION_BUTTON_ROW_GAP)}>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={saveDiscussion}
                    disabled={updateTopic.isPending}
                  >
                    {updateTopic.isPending ? "Saving..." : "Save discussion"}
                  </Button>
                  <Button variant="ghost" size="sm" onClick={() => setIsEditingDiscussion(false)}>
                    Cancel
                  </Button>
                </div>
              </>
            ) : topic.discussion ? (
              <RichTextDisplay html={topic.discussion} className="max-h-48 overflow-y-auto scrollbar-hide" />
            ) : (
              <p className="text-sm text-muted-foreground">
                No discussion yet — click Edit to add one.
              </p>
            )}
          </div>

          <div className="flex flex-col gap-2 rounded-md border border-border bg-background p-3">
            <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Image</p>
            {topic.image_url ? (
              <img
                src={topic.image_url}
                alt=""
                className="max-h-[75vh] w-full max-w-2xl rounded-md border border-border object-contain"
              />
            ) : (
              <div className="flex h-24 w-24 items-center justify-center rounded-md border border-dashed border-border text-muted-foreground">
                <ImageOff className="h-6 w-6" />
              </div>
            )}
            <div className={cn("flex items-center", ACTION_BUTTON_ROW_GAP)}>
              <Button
                variant="outline"
                size="sm"
                onClick={() => fileInputRefs.current.get(topic.id)?.click()}
                disabled={uploadImage.isPending}
              >
                <Upload className="h-3.5 w-3.5" />
                {uploadImage.isPending ? "Uploading..." : topic.image_url ? "Replace image" : "Add image"}
              </Button>
              {topic.image_url && (
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => deleteImage.mutate(topic.id)}
                  disabled={deleteImage.isPending}
                >
                  Remove image
                </Button>
              )}
              <input
                ref={(el) => {
                  if (el) fileInputRefs.current.set(topic.id, el);
                  else fileInputRefs.current.delete(topic.id);
                }}
                type="file"
                accept="image/jpeg,image/png,image/webp"
                className="hidden"
                onChange={(e) => onFileChange(topic.id, e)}
              />
            </div>
          </div>

          <div className="flex flex-col gap-2">
            <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              Reference Links
            </p>
            {topic.reference_links.length > 0 && (
              <ul className="flex flex-col gap-1">
                {topic.reference_links.map((link, i) => (
                  <li key={`${link.url}-${i}`} className="flex items-center gap-2">
                    <a
                      href={link.url}
                      target="_blank"
                      rel="noreferrer"
                      className="text-sm font-medium text-accent underline underline-offset-2 hover:text-accent/80"
                    >
                      {link.label}
                    </a>
                    <button
                      type="button"
                      onClick={() => setDeleteLinkIndex(i)}
                      aria-label={`Remove link "${link.label}"`}
                      className="text-muted-foreground hover:text-destructive"
                    >
                      <X className="h-3.5 w-3.5" />
                    </button>
                  </li>
                ))}
              </ul>
            )}
            <form className="flex flex-wrap items-center gap-2" onSubmit={addLink}>
              <Input
                value={linkLabel}
                onChange={(e) => setLinkLabel(e.target.value)}
                placeholder="Label"
                className="w-40"
              />
              <Input
                value={linkUrl}
                onChange={(e) => setLinkUrl(e.target.value)}
                placeholder="https://..."
                type="url"
                className="w-64"
              />
              <Button type="submit" variant="ghost" size="sm" disabled={updateTopic.isPending}>
                <Plus className="h-3.5 w-3.5" />
                Add link
              </Button>
            </form>
          </div>
        </div>
      )}

      <ConfirmDialog
        open={deleteLinkIndex !== null}
        onCancel={() => setDeleteLinkIndex(null)}
        onConfirm={confirmRemoveLink}
        title="Remove reference link?"
        description={
          deleteLinkIndex !== null
            ? `Remove "${topic.reference_links[deleteLinkIndex]?.label}"? This can't be undone.`
            : ""
        }
        isPending={updateTopic.isPending}
      />
    </div>
  );
}
