import { useCurrentUser } from "@/api/queries/auth";
import {
  useCreateInterviewTopic,
  useDeleteInterviewTopic,
  useInterviewTopics,
  useMoveInterviewTopic,
  useToggleTopicPublic,
  useUpdateInterviewTopic,
  useUploadTopicColumnImage,
} from "@/api/queries/interview-prep";
import type { components } from "@/api/schema.gen";
import { Button } from "@/components/ui/button";
import { ACTION_BUTTON_ROW_GAP } from "@/components/ui/button-variants";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { CopyButton } from "@/components/ui/copy-button";
import { Dialog } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { MoveButtons } from "@/components/ui/move-buttons";
import { RichTextDisplay, RichTextEditor } from "@/components/ui/rich-text-editor";
import { Select } from "@/components/ui/select";
import { DeleteScopeChoiceDialog } from "@/features/interview-prep/DeleteScopeChoiceDialog";
import { ScopeTagSelector, type ScopeOption } from "@/features/interview-prep/ScopeTagSelector";
import { TopicVisibilityToggle } from "@/features/interview-prep/TopicVisibilityToggle";
import { useUnsavedChangesGuard } from "@/hooks/useUnsavedChangesGuard";
import { groupInterviewTopicsBySection } from "@/lib/group-interview-topics-by-section";
import { getErrorMessage } from "@/lib/errors";
import { publicArticleUrl } from "@/lib/public-sharing-url";
import { cn } from "@/lib/utils";
import {
  ChevronDown,
  ChevronRight,
  ExternalLink,
  ImageOff,
  Pencil,
  Plus,
  Trash2,
  Upload,
  X,
} from "lucide-react";
import { type Dispatch, type FormEvent, type SetStateAction, useEffect, useRef, useState } from "react";

type InterviewTopic = components["schemas"]["InterviewTopicResponse"];
type TargetRole = components["schemas"]["TargetRoleResponse"];
type ArticleRow = components["schemas"]["ArticleBlockPayload"];
type ArticleColumn = components["schemas"]["ArticleColumnPayload"];
type ArticleColumnType = ArticleColumn["type"];

const COLUMN_TYPE_LABELS: Record<ArticleColumnType, string> = {
  rich_text: "Text",
  image: "Image",
  video_embed: "Video",
  article_link: "Article link",
  external_link: "External link",
};

function newColumn(type: ArticleColumnType): ArticleColumn {
  return {
    id: crypto.randomUUID(),
    type,
    label: COLUMN_TYPE_LABELS[type],
    html: type === "rich_text" ? "" : null,
    image_url: null,
    video_embed_url: null,
    article_topic_id: null,
    external_url: null,
  };
}

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

/** Merges Master + this scope's own Articles into one deduplicated list
 * an article_link column can point at — same "this user's topics
 * regardless of scope" merge ShowcasePageSection.tsx's own mergeTopics
 * already does (when scope is already Master, this is just a harmless
 * self-merge — useInterviewTopics(null) and useInterviewTopics(scope)
 * share the same query cache key in that case). */
function mergeTopicsForLinking(
  master: InterviewTopic[] | undefined,
  scoped: InterviewTopic[] | undefined,
): InterviewTopic[] {
  const byId = new Map<string, InterviewTopic>();
  for (const topic of [...(master ?? []), ...(scoped ?? [])]) {
    byId.set(topic.id, topic);
  }
  return [...byId.values()];
}

export function InterviewTopicsSection({
  scope,
  targetRoles,
  expandedId,
  setExpandedId,
  sectionFilter,
  totalCount,
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
  // Deduplicated count across EVERY scope (Master + every Target
  // Role), from InterviewPrepPage's own useInterviewPrepSummary() —
  // shown alongside this scope's own count in the card title, e.g.
  // "Articles (2/8)". undefined while that query hasn't resolved yet.
  totalCount: number | undefined;
}) {
  const { data: topics, isLoading } = useInterviewTopics(scope);
  const addTopic = useCreateInterviewTopic(scope);
  const updateTopic = useUpdateInterviewTopic(scope);
  const deleteTopic = useDeleteInterviewTopic(scope);
  const moveTopic = useMoveInterviewTopic(scope);
  const togglePublic = useToggleTopicPublic(scope);
  const { data: currentUser } = useCurrentUser();
  // Article-link columns can point at any of this user's own Articles —
  // merged from Master and this scope, same "this user's topics
  // regardless of exactly which scope" set ShowcasePageSection.tsx's own
  // article_link column editor already uses.
  const { data: masterTopicsForLinking } = useInterviewTopics(null);
  const articleLinkOptions = mergeTopicsForLinking(masterTopicsForLinking, topics);

  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [form, setForm] = useState<FormState>({ name: "", section: "", scopeTargetRoleIds: [scope] });
  const [formSnapshot, setFormSnapshot] = useState<FormState>({
    name: "",
    section: "",
    scopeTargetRoleIds: [scope],
  });
  const [isEditMode, setIsEditMode] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<InterviewTopic | null>(null);

  const isDialogDirty = dialogOpen && JSON.stringify(form) !== JSON.stringify(formSnapshot);
  const { confirmDiscard, guardElement } = useUnsavedChangesGuard(isDialogDirty);

  async function handleDialogClose() {
    if (await confirmDiscard()) setDialogOpen(false);
  }

  const scopeOptions: ScopeOption[] = [
    { id: null, label: "Master (generic)" },
    ...targetRoles.map((r) => ({ id: r.id, label: r.role_name })),
  ];

  function toggleExpanded(id: string) {
    setExpandedId((prev) => (prev === id ? null : id));
  }

  function openAddDialog() {
    const initial = { name: "", section: "", scopeTargetRoleIds: [scope] };
    setEditingId(null);
    setForm(initial);
    setFormSnapshot(initial);
    setDialogOpen(true);
  }

  function openEditDialog(topic: InterviewTopic) {
    const initial = toFormState(topic);
    setEditingId(topic.id);
    setForm(initial);
    setFormSnapshot(initial);
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
            blocks: existing?.blocks ?? [],
            scope_target_role_ids: form.scopeTargetRoleIds,
          },
        })
        .then(() => setDialogOpen(false))
        .catch(() => {});
    } else {
      addTopic
        .mutateAsync({ name, section, scope_target_role_ids: form.scopeTargetRoleIds })
        .then((created) => {
          setDialogOpen(false);
          setExpandedId(created.id);
        })
        .catch(() => {});
    }
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
        <CardTitle>
          Articles{topics && totalCount !== undefined ? ` (${topics.length}/${totalCount})` : ""}
        </CardTitle>
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
            No articles yet — add one to start building your study notes.
          </p>
        )}
        {/* Only reachable if the sub-tab's own section was emptied out
            (e.g. its last topic was edited into a different section)
            while it stayed selected — the sub-tab strip itself doesn't
            auto-switch away, so this avoids a silently blank card body. */}
        {topics && topics.length > 0 && visibleGroups.length === 0 && (
          <p className="text-sm text-muted-foreground">No articles in this section.</p>
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
                  togglePublic={togglePublic}
                  handle={currentUser?.handle}
                  articleLinkOptions={articleLinkOptions}
                />
              );
            })}
          </div>
        ))}
      </CardContent>

      <Dialog
        open={dialogOpen}
        onClose={() => {
          void handleDialogClose();
        }}
        title={editingId ? "Edit article" : "Add article"}
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
                : "Add article"}
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
          title="Delete article?"
          description={
            deleteTarget
              ? `Remove "${deleteTarget.name}"? Any questions linked to it will be un-linked, not deleted. This can't be undone.`
              : ""
          }
          isPending={deleteTopic.isPending}
        />
      )}

      {guardElement}
    </Card>
  );
}

type RemoveTarget =
  | { kind: "row"; row: ArticleRow }
  | { kind: "column"; rowId: string; column: ArticleColumn };

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
  togglePublic,
  handle,
  articleLinkOptions,
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
  togglePublic: ReturnType<typeof useToggleTopicPublic>;
  handle: string | null | undefined;
  articleLinkOptions: InterviewTopic[];
}) {
  const updateTopic = useUpdateInterviewTopic(scope);
  const [removeTarget, setRemoveTarget] = useState<RemoveTarget | null>(null);
  // The column id of a block just added — handed down to that specific
  // ArticleColumnCard once it mounts so it can scroll itself into view
  // and open its own editor immediately, same fix already applied to
  // Showcase Page's identical block editor (direct 2026-08-24 report:
  // "when I add a block it always goes to the end").
  const [focusColumnId, setFocusColumnId] = useState<string | null>(null);

  function commit(blocks: ArticleRow[], focusOnColumnId?: string) {
    // Set BEFORE calling mutate, not inside onSuccess — react-query calls
    // the hook-level onSuccess (which writes the new blocks into the
    // query cache, the thing that actually mounts the new column) and
    // this call's own onSuccess as two separate microtask-chained
    // callbacks, not one batched React update; setting it here instead
    // means it's already correct by the time the new column's first
    // render happens, rather than racing to catch up one render late
    // (real bug caught live: the mount-only focus effect below always
    // saw shouldFocus=false with the onSuccess-based version).
    if (focusOnColumnId) setFocusColumnId(focusOnColumnId);
    updateTopic.mutate({
      id: topic.id,
      body: {
        name: topic.name,
        section: topic.section,
        blocks,
        scope_target_role_ids: topic.scope_target_role_ids,
      },
    });
  }

  function addRow(type: ArticleColumnType) {
    const column = newColumn(type);
    commit([...topic.blocks, { id: crypto.randomUUID(), columns: [column] }], column.id);
  }

  function insertRowAfter(afterRowId: string, type: ArticleColumnType) {
    const column = newColumn(type);
    const rows = topic.blocks;
    const index = rows.findIndex((r) => r.id === afterRowId);
    const next = [...rows];
    next.splice(index + 1, 0, { id: crypto.randomUUID(), columns: [column] });
    commit(next, column.id);
  }

  function addColumn(rowId: string, type: ArticleColumnType) {
    const column = newColumn(type);
    commit(
      topic.blocks.map((row) => (row.id === rowId ? { ...row, columns: [...row.columns, column] } : row)),
      column.id,
    );
  }

  function saveColumn(rowId: string, updated: ArticleColumn) {
    commit(
      topic.blocks.map((row) =>
        row.id === rowId
          ? { ...row, columns: row.columns.map((c) => (c.id === updated.id ? updated : c)) }
          : row,
      ),
    );
  }

  function confirmRemove() {
    if (!removeTarget) return;
    if (removeTarget.kind === "row") {
      commit(topic.blocks.filter((row) => row.id !== removeTarget.row.id));
    } else {
      commit(
        topic.blocks.map((row) =>
          row.id === removeTarget.rowId
            ? { ...row, columns: row.columns.filter((c) => c.id !== removeTarget.column.id) }
            : row,
        ),
      );
    }
    setRemoveTarget(null);
  }

  function moveRow(rowId: string, direction: "up" | "down") {
    const rows = topic.blocks;
    const index = rows.findIndex((r) => r.id === rowId);
    const targetIndex = direction === "up" ? index - 1 : index + 1;
    if (index === -1 || targetIndex < 0 || targetIndex >= rows.length) return;
    const next = [...rows];
    [next[index], next[targetIndex]] = [next[targetIndex]!, next[index]!];
    commit(next);
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
        <div className="flex shrink-0 items-center gap-2">
          <div
            className={cn("flex items-center", ACTION_BUTTON_ROW_GAP)}
            onClick={(e) => e.stopPropagation()}
          >
            {/* Public/private + copy-link are always visible, unlike
                Edit/Delete below — visibility is a viewer-facing state
                a reader should be able to check/toggle at a glance, not
                an editing action gated behind entering edit mode
                (direct 2026-08-24 request). */}
            <TopicVisibilityToggle
              checked={topic.is_public}
              onCheckedChange={(checked) =>
                togglePublic.mutate({ id: topic.id, body: { is_public: checked } })
              }
              disabled={togglePublic.isPending}
              label={topic.name}
            />
            {topic.is_public && topic.share_key && (
              <CopyButton
                text={publicArticleUrl(handle, topic.share_key)}
                label="Copy link"
                variant="ghost"
              />
            )}
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
          </div>
          {isOpen ? (
            <ChevronDown className="h-4 w-4 shrink-0 text-muted-foreground" />
          ) : (
            <ChevronRight className="h-4 w-4 shrink-0 text-muted-foreground" />
          )}
        </div>
      </div>

      {isOpen && (
        <div className="flex flex-col gap-3 border-t border-border p-3">
          <div className="flex items-center justify-between gap-2">
            <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              Content
            </p>
            <ArticleBlockTypeMenu triggerLabel="Add block" onSelect={addRow} disabled={updateTopic.isPending} />
          </div>

          {topic.blocks.length === 0 && (
            <p className="text-sm text-muted-foreground">
              No content yet — use "Add block" above to start building this article.
            </p>
          )}

          <div className="flex flex-col gap-3">
            {topic.blocks.map((row, index) => (
              <ArticleRowCard
                key={row.id}
                row={row}
                index={index}
                total={topic.blocks.length}
                topicId={topic.id}
                scope={scope}
                articleLinkOptions={articleLinkOptions}
                onMove={(direction) => moveRow(row.id, direction)}
                onAddColumn={(type) => addColumn(row.id, type)}
                onInsertBelow={(type) => insertRowAfter(row.id, type)}
                onRemoveRow={() => setRemoveTarget({ kind: "row", row })}
                onRemoveColumn={(column) => setRemoveTarget({ kind: "column", rowId: row.id, column })}
                onSaveColumn={(column) => saveColumn(row.id, column)}
                isSaving={updateTopic.isPending}
                focusColumnId={focusColumnId}
                onFocusHandled={() => setFocusColumnId(null)}
              />
            ))}
          </div>

          {updateTopic.isError && (
            <p role="alert" className="text-sm text-destructive">
              {getErrorMessage(updateTopic.error)}
            </p>
          )}
        </div>
      )}

      <ConfirmDialog
        open={removeTarget !== null}
        onCancel={() => setRemoveTarget(null)}
        onConfirm={confirmRemove}
        title={removeTarget?.kind === "row" ? "Remove this block?" : "Remove this column?"}
        description={
          removeTarget === null
            ? ""
            : removeTarget.kind === "row"
              ? `Remove the "${removeTarget.row.columns.map((c) => c.label).join(", ")}" block${
                  removeTarget.row.columns.length > 1 ? " and all its columns" : ""
                }? This can't be undone.`
              : `Remove the "${removeTarget.column.label}" column? This can't be undone.`
        }
        isPending={updateTopic.isPending}
      />
    </div>
  );
}

/** A trigger button that opens a small popover menu of block/column
 * types — selecting one fires `onSelect` immediately. Mirrors Showcase
 * Page's own BlockTypeMenu exactly (see ShowcasePageSection.tsx) — kept
 * as a separate local copy rather than a shared component, since the
 * two domains' column type unions, while identical in shape today, are
 * independently-defined API types. */
function ArticleBlockTypeMenu({
  triggerLabel,
  onSelect,
  disabled,
  variant = "outline",
}: {
  triggerLabel: string;
  onSelect: (type: ArticleColumnType) => void;
  disabled?: boolean;
  variant?: "outline" | "ghost";
}) {
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    function handlePointerDown(event: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        setOpen(false);
      }
    }
    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") setOpen(false);
    }
    document.addEventListener("mousedown", handlePointerDown);
    document.addEventListener("keydown", handleKeyDown);
    return () => {
      document.removeEventListener("mousedown", handlePointerDown);
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, [open]);

  return (
    <div className="relative" ref={containerRef}>
      <Button
        type="button"
        variant={variant}
        size="sm"
        onClick={() => setOpen((o) => !o)}
        disabled={disabled}
        aria-haspopup="menu"
        aria-expanded={open}
      >
        <Plus className="h-3.5 w-3.5" />
        {triggerLabel}
      </Button>
      {open && (
        <div
          role="menu"
          className="absolute right-0 top-full z-30 mt-1 w-44 overflow-hidden rounded-md border border-border bg-card shadow-md"
        >
          {Object.entries(COLUMN_TYPE_LABELS).map(([value, label]) => (
            <button
              key={value}
              type="button"
              role="menuitem"
              className="block w-full px-3 py-2 text-left text-sm hover:bg-muted"
              onClick={() => {
                onSelect(value as ArticleColumnType);
                setOpen(false);
              }}
            >
              {label}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

function ArticleRowCard({
  row,
  index,
  total,
  topicId,
  scope,
  articleLinkOptions,
  onMove,
  onAddColumn,
  onInsertBelow,
  onRemoveRow,
  onRemoveColumn,
  onSaveColumn,
  isSaving,
  focusColumnId,
  onFocusHandled,
}: {
  row: ArticleRow;
  index: number;
  total: number;
  topicId: string;
  scope: string | null;
  articleLinkOptions: InterviewTopic[];
  onMove: (direction: "up" | "down") => void;
  onAddColumn: (type: ArticleColumnType) => void;
  onInsertBelow: (type: ArticleColumnType) => void;
  onRemoveRow: () => void;
  onRemoveColumn: (column: ArticleColumn) => void;
  onSaveColumn: (column: ArticleColumn) => void;
  isSaving: boolean;
  focusColumnId: string | null;
  onFocusHandled: () => void;
}) {
  return (
    <div
      className={cn("rounded-md border border-border", index % 2 === 0 ? "bg-card" : "bg-muted")}
    >
      <div className="flex items-center justify-between gap-3 px-3 py-2">
        <div className="flex items-center gap-2">
          <MoveButtons
            onMoveUp={() => onMove("up")}
            onMoveDown={() => onMove("down")}
            isFirst={index === 0}
            isLast={index === total - 1}
            disabled={isSaving}
            className="h-7 w-7 p-0"
          />
          <span className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
            {row.columns.length > 1 ? `${row.columns.length} columns` : "Block"}
          </span>
        </div>
        <div className={cn("flex items-center", ACTION_BUTTON_ROW_GAP)}>
          <ArticleBlockTypeMenu triggerLabel="Add column" onSelect={onAddColumn} disabled={isSaving} />
          <Button
            variant="ghost"
            size="sm"
            className="h-7 w-7 p-0"
            onClick={onRemoveRow}
            aria-label="Remove block"
          >
            <Trash2 className="h-3.5 w-3.5" />
          </Button>
        </div>
      </div>

      <div className="flex flex-col gap-3 border-t border-border p-3 md:flex-row">
        {row.columns.map((column) => (
          <ArticleColumnCard
            key={column.id}
            column={column}
            topicId={topicId}
            scope={scope}
            articleLinkOptions={articleLinkOptions}
            canRemoveIndividually={row.columns.length > 1}
            onRemove={() => onRemoveColumn(column)}
            onSave={onSaveColumn}
            isSaving={isSaving}
            shouldFocus={focusColumnId === column.id}
            onFocusHandled={onFocusHandled}
          />
        ))}
      </div>

      {/* Insert a new block right where you're working, rather than only
          ever being able to add at the very end of the article. */}
      <div className="flex justify-center border-t border-border px-3 py-1">
        <ArticleBlockTypeMenu
          triggerLabel="Add block below"
          onSelect={onInsertBelow}
          disabled={isSaving}
          variant="ghost"
        />
      </div>
    </div>
  );
}

function ArticleColumnCard({
  column,
  topicId,
  scope,
  articleLinkOptions,
  canRemoveIndividually,
  onRemove,
  onSave,
  isSaving,
  shouldFocus,
  onFocusHandled,
}: {
  column: ArticleColumn;
  topicId: string;
  scope: string | null;
  articleLinkOptions: InterviewTopic[];
  canRemoveIndividually: boolean;
  onRemove: () => void;
  onSave: (updated: ArticleColumn) => void;
  isSaving: boolean;
  shouldFocus: boolean;
  onFocusHandled: () => void;
}) {
  const uploadImage = useUploadTopicColumnImage(scope);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const [isEditing, setIsEditing] = useState(false);
  const [draft, setDraft] = useState<ArticleColumn>(column);

  // `column` never changes while isEditing is true (see the effect
  // below, which only re-seeds draft once editing stops) — so it's
  // safe to use directly as the "before" snapshot for dirty-checking,
  // no separate captured-at-edit-start state needed.
  const isColumnDirty = isEditing && JSON.stringify(draft) !== JSON.stringify(column);
  const { confirmDiscard: confirmDiscardColumn, guardElement: columnGuardElement } =
    useUnsavedChangesGuard(isColumnDirty);

  // Re-seeds the draft only when the column identity changes or edit
  // mode is freshly entered — not reactively on every background
  // refetch, matching this app's "initialize once, don't clobber
  // in-progress edits" convention.
  useEffect(() => {
    if (!isEditing) setDraft(column);
  }, [column, isEditing]);

  // Runs once, only for a freshly-added column (this component only
  // ever mounts once per column id) — scrolls it into view and opens
  // its own editor immediately, same fix as Showcase Page's identical
  // block editor.
  useEffect(() => {
    if (!shouldFocus) return;
    containerRef.current?.scrollIntoView({ behavior: "smooth", block: "center" });
    if (column.type !== "image") {
      setDraft(column);
      setIsEditing(true);
    }
    onFocusHandled();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function startEditing() {
    setDraft(column);
    setIsEditing(true);
  }

  function save() {
    onSave(draft);
    setIsEditing(false);
  }

  function handleFileChange(event: React.ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (file) uploadImage.mutate({ id: topicId, columnId: column.id, file });
  }

  return (
    <div
      ref={containerRef}
      className="min-w-0 flex-1 basis-0 rounded-md border border-border bg-background"
    >
      <div className="flex items-center justify-between gap-2 px-3 py-2">
        <div className="flex min-w-0 items-center gap-2">
          <span className="shrink-0 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
            {COLUMN_TYPE_LABELS[column.type]}
          </span>
          <p className="truncate text-sm font-medium">{column.label}</p>
        </div>
        <div className={cn("flex shrink-0 items-center", ACTION_BUTTON_ROW_GAP)}>
          {!isEditing && column.type !== "image" && (
            <Button variant="ghost" size="sm" className="h-7 w-7 p-0" onClick={startEditing}>
              <Pencil className="h-3.5 w-3.5" />
            </Button>
          )}
          {canRemoveIndividually && (
            <Button
              variant="ghost"
              size="sm"
              className="h-7 w-7 p-0"
              onClick={onRemove}
              aria-label="Remove column"
            >
              <X className="h-3.5 w-3.5" />
            </Button>
          )}
        </div>
      </div>

      <div className="flex flex-col gap-3 border-t border-border p-3">
        {isEditing ? (
          <div className="flex flex-col gap-3">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor={`article-column-label-${column.id}`}>Label</Label>
              <Input
                id={`article-column-label-${column.id}`}
                value={draft.label}
                onChange={(e) => setDraft({ ...draft, label: e.target.value })}
                maxLength={100}
              />
            </div>

            {draft.type === "rich_text" && (
              <RichTextEditor
                defaultValue={draft.html}
                onChange={(html) => setDraft({ ...draft, html })}
                placeholder="Notes to help you understand this article..."
                autoFocus
              />
            )}

            {draft.type === "video_embed" && (
              <div className="flex flex-col gap-1.5">
                <Label htmlFor={`article-column-video-${column.id}`}>Embed URL</Label>
                <Input
                  id={`article-column-video-${column.id}`}
                  type="url"
                  placeholder="https://www.youtube.com/embed/..."
                  value={draft.video_embed_url ?? ""}
                  onChange={(e) => setDraft({ ...draft, video_embed_url: e.target.value })}
                />
              </div>
            )}

            {draft.type === "external_link" && (
              <div className="flex flex-col gap-1.5">
                <Label htmlFor={`article-column-url-${column.id}`}>URL</Label>
                <Input
                  id={`article-column-url-${column.id}`}
                  type="url"
                  placeholder="https://..."
                  value={draft.external_url ?? ""}
                  onChange={(e) => setDraft({ ...draft, external_url: e.target.value })}
                />
              </div>
            )}

            {draft.type === "article_link" && (
              <div className="flex flex-col gap-1.5">
                <Label htmlFor={`article-column-link-${column.id}`}>Article</Label>
                <Select
                  id={`article-column-link-${column.id}`}
                  value={draft.article_topic_id ?? ""}
                  onChange={(e) => setDraft({ ...draft, article_topic_id: e.target.value || null })}
                >
                  <option value="">Choose an article...</option>
                  {articleLinkOptions
                    .filter((t) => t.id !== topicId)
                    .map((t) => (
                      <option key={t.id} value={t.id}>
                        {t.name}
                        {!t.is_public ? " (currently private)" : ""}
                      </option>
                    ))}
                </Select>
                <p className="text-xs text-muted-foreground">
                  Only renders as a real link on the public page while that article is itself
                  public — otherwise it shows as plain text.
                </p>
              </div>
            )}

            <div className={cn("flex", ACTION_BUTTON_ROW_GAP)}>
              <Button variant="outline" size="sm" onClick={save} disabled={isSaving}>
                {isSaving ? "Saving..." : "Save"}
              </Button>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => {
                  void (async () => {
                    if (await confirmDiscardColumn()) setIsEditing(false);
                  })();
                }}
              >
                Cancel
              </Button>
            </div>
          </div>
        ) : (
          <ArticleColumnPreview column={column} />
        )}

        {column.type === "image" && (
          <div className="flex flex-col gap-2">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor={`article-column-label-${column.id}`}>Label</Label>
              <Input
                id={`article-column-label-${column.id}`}
                value={column.label}
                onChange={(e) => onSave({ ...column, label: e.target.value })}
                onBlur={(e) => onSave({ ...column, label: e.target.value })}
                maxLength={100}
              />
            </div>
            {column.image_url ? (
              <img
                src={column.image_url}
                alt=""
                className="max-h-[60vh] w-full rounded-md border border-border object-contain"
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
                onClick={() => fileInputRef.current?.click()}
                disabled={uploadImage.isPending}
              >
                <Upload className="h-3.5 w-3.5" />
                {uploadImage.isPending
                  ? "Uploading..."
                  : column.image_url
                    ? "Replace image"
                    : "Add image"}
              </Button>
              <input
                ref={fileInputRef}
                type="file"
                accept="image/jpeg,image/png,image/webp"
                className="hidden"
                onChange={handleFileChange}
              />
            </div>
            {uploadImage.isError && (
              <p role="alert" className="text-sm text-destructive">
                {getErrorMessage(uploadImage.error)}
              </p>
            )}
          </div>
        )}
      </div>
      {columnGuardElement}
    </div>
  );
}

function ArticleColumnPreview({ column }: { column: ArticleColumn }) {
  switch (column.type) {
    case "rich_text":
      return column.html ? (
        <RichTextDisplay html={column.html} className="max-h-48 overflow-y-auto scrollbar-hide" />
      ) : (
        <p className="text-sm text-muted-foreground">No content yet — click Edit to add some.</p>
      );
    case "video_embed":
      return column.video_embed_url ? (
        <p className="truncate text-sm text-muted-foreground">{column.video_embed_url}</p>
      ) : (
        <p className="text-sm text-muted-foreground">No embed URL yet — click Edit to add one.</p>
      );
    case "external_link":
      return column.external_url ? (
        <a
          href={column.external_url}
          target="_blank"
          rel="noreferrer"
          className="flex items-center gap-1 text-sm font-medium text-accent underline underline-offset-2 hover:text-accent/80"
        >
          <ExternalLink className="h-3.5 w-3.5" />
          {column.external_url}
        </a>
      ) : (
        <p className="text-sm text-muted-foreground">No URL yet — click Edit to add one.</p>
      );
    case "article_link":
      return column.article_topic_id ? (
        <p className="text-sm text-muted-foreground">Links to an Article.</p>
      ) : (
        <p className="text-sm text-muted-foreground">No article chosen yet — click Edit to pick one.</p>
      );
    case "image":
      return null;
  }
}
