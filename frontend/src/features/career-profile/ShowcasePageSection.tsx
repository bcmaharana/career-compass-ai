import { useCurrentUser } from "@/api/queries/auth";
import { useInterviewTopics } from "@/api/queries/interview-prep";
import {
  useShowcasePage,
  useToggleShowcasePagePublic,
  useUpdateShowcasePage,
  useUploadShowcaseColumnImage,
} from "@/api/queries/showcase-page";
import type { components } from "@/api/schema.gen";
import { Button } from "@/components/ui/button";
import { ACTION_BUTTON_ROW_GAP } from "@/components/ui/button-variants";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { CopyButton } from "@/components/ui/copy-button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { MoveButtons } from "@/components/ui/move-buttons";
import { RichTextDisplay, RichTextEditor } from "@/components/ui/rich-text-editor";
import { Select } from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { getErrorMessage } from "@/lib/errors";
import { publicShowcasePageUrl } from "@/lib/public-sharing-url";
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
import { useEffect, useRef, useState } from "react";

type ShowcaseRow = components["schemas"]["ShowcaseBlockPayload"];
type ShowcaseColumn = components["schemas"]["ShowcaseColumnPayload"];
type ShowcaseColumnType = ShowcaseColumn["type"];

const COLUMN_TYPE_LABELS: Record<ShowcaseColumnType, string> = {
  rich_text: "Text",
  image: "Image",
  video_embed: "Video",
  article_link: "Article link",
  external_link: "External link",
};

function newColumn(type: ShowcaseColumnType): ShowcaseColumn {
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

type RemoveTarget =
  | { kind: "row"; row: ShowcaseRow }
  | { kind: "column"; rowId: string; column: ShowcaseColumn };

/**
 * Per-Target-Role, freeform block-based public page — seeded once from
 * the role's generated resume content, then fully independent (block
 * content/labels/order can all diverge from the profile that seeded
 * them, same "one-time copy, not a sync" precedent Master -> Target
 * Role Profile already established). Only rendered when a real Target
 * Role is the active scope (see CareerProfilePage.tsx) — a Showcase
 * Page has no Master-profile equivalent, matching the backend's
 * `target_role_id` being always-required, never optional.
 *
 * Each "block" is really a ROW that can hold one or more COLUMNS,
 * rendered side by side (equal width) on desktop and stacked vertically
 * on mobile (`md:flex-row`) — a row created before multi-column support
 * existed is simply a 1-column row, and "+ Add column" on any existing
 * row (including one of those) appends another, converting it in place;
 * there's no separate "make this row multi-column" step. No cap on
 * column count, per direct user confirmation.
 *
 * Every structural change (add/remove/reorder a row, add/remove a
 * column, edit a column's saved content) immediately PATCHes the whole
 * `blocks` array — the same "whole list as one JSON blob, replaced
 * atomically" shape CoreCompetencies/resume_section_toggles already use
 * on the backend. Add/remove column is deliberately frontend-only (a
 * computed array sent through the existing update() PATCH) rather than
 * dedicated endpoints, matching that same whole-array-replace
 * convention rather than introducing a second one.
 *
 * Each column's own content editor uses a local edit-mode-with-Save
 * toggle (mirrors Interview Prep's Discussion sub-card) rather than
 * saving on every keystroke, since a PATCH-per-keystroke would be both
 * wasteful and risk the same cursor-reset bug class already documented
 * for RichTextEditor elsewhere in this app.
 */
export function ShowcasePageSection({
  targetRoleId,
  roleTag,
  isOpen,
  onToggleOpen,
}: {
  targetRoleId: string;
  roleTag: string;
  isOpen: boolean;
  onToggleOpen: () => void;
}) {
  const { data: page } = useShowcasePage(targetRoleId);
  const updatePage = useUpdateShowcasePage(targetRoleId);
  const togglePublic = useToggleShowcasePagePublic(targetRoleId);
  const { data: currentUser } = useCurrentUser();
  // Article-link columns can point at any of this user's own Interview
  // Prep Topics — merged from Master and this role's own scope (the
  // two scopes this page's own Table of Contents already treats as
  // "this user's topics" elsewhere in the app; there's no single
  // "every topic regardless of scope" endpoint to fetch from instead).
  const { data: masterTopics } = useInterviewTopics(null);
  const { data: roleTopics } = useInterviewTopics(targetRoleId);
  const topicOptions = mergeTopics(masterTopics, roleTopics);

  const [removeTarget, setRemoveTarget] = useState<RemoveTarget | null>(null);
  // The column id of a block just added (either via the header's "+ Add
  // block", which appends at the end, or a row's own "+ Add block
  // below") — handed down to that specific ShowcaseColumnCard once it
  // mounts so it can scroll itself into view and open its own editor
  // immediately, instead of leaving a newly-added block sitting off
  // -screen wherever the list happens to end (direct 2026-08-24 report:
  // "when I add a block it always goes to the end").
  const [focusColumnId, setFocusColumnId] = useState<string | null>(null);

  if (!page) {
    return null;
  }

  function commit(blocks: ShowcaseRow[], focusOnColumnId?: string) {
    // Set BEFORE calling mutate, not inside onSuccess — react-query calls
    // the hook-level onSuccess (which writes the new blocks into the
    // query cache, the thing that actually mounts the new column) and
    // this call's own onSuccess as two separate microtask-chained
    // callbacks, not one batched React update; setting it here instead
    // means it's already correct by the time the new column's first
    // render happens, rather than racing to catch up one render late
    // (real bug caught live building Articles' identical editor: the
    // mount-only focus effect below always saw shouldFocus=false with
    // the onSuccess-based version).
    if (focusOnColumnId) setFocusColumnId(focusOnColumnId);
    updatePage.mutate({ blocks });
  }

  function addRow(type: ShowcaseColumnType) {
    const column = newColumn(type);
    commit([...page!.blocks, { id: crypto.randomUUID(), columns: [column] }], column.id);
  }

  function insertRowAfter(afterRowId: string, type: ShowcaseColumnType) {
    const column = newColumn(type);
    const rows = page!.blocks;
    const index = rows.findIndex((r) => r.id === afterRowId);
    const next = [...rows];
    next.splice(index + 1, 0, { id: crypto.randomUUID(), columns: [column] });
    commit(next, column.id);
  }

  function addColumn(rowId: string, type: ShowcaseColumnType) {
    const column = newColumn(type);
    commit(
      page!.blocks.map((row) =>
        row.id === rowId ? { ...row, columns: [...row.columns, column] } : row,
      ),
      column.id,
    );
  }

  function saveColumn(rowId: string, updated: ShowcaseColumn) {
    commit(
      page!.blocks.map((row) =>
        row.id === rowId
          ? { ...row, columns: row.columns.map((c) => (c.id === updated.id ? updated : c)) }
          : row,
      ),
    );
  }

  function confirmRemove() {
    if (!removeTarget) return;
    if (removeTarget.kind === "row") {
      commit(page!.blocks.filter((row) => row.id !== removeTarget.row.id));
    } else {
      commit(
        page!.blocks.map((row) =>
          row.id === removeTarget.rowId
            ? { ...row, columns: row.columns.filter((c) => c.id !== removeTarget.column.id) }
            : row,
        ),
      );
    }
    setRemoveTarget(null);
  }

  function moveRow(rowId: string, direction: "up" | "down") {
    const rows = page!.blocks;
    const index = rows.findIndex((r) => r.id === rowId);
    const targetIndex = direction === "up" ? index - 1 : index + 1;
    if (index === -1 || targetIndex < 0 || targetIndex >= rows.length) return;
    const next = [...rows];
    [next[index], next[targetIndex]] = [next[targetIndex]!, next[index]!];
    commit(next);
  }

  const publicUrl =
    page.is_public && page.share_key
      ? publicShowcasePageUrl(currentUser?.handle, roleTag, page.share_key)
      : null;

  return (
    <Card className="bg-background">
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
        // Sticky, not just fixed-at-the-top-of-the-card: a Showcase Page
        // can grow to many blocks, and "+ Add block" living only below
        // the list (its original position) meant scrolling all the way
        // back down to reach it once the list got long (direct
        // 2026-08-24 report). Pinning the whole header — same sticky
        // top-0 z-10 pattern ProfileHeader.tsx already established for
        // this page's scroll container — keeps both the Add control and
        // the public/private toggle reachable regardless of scroll
        // position, without needing viewport-fixed positioning that
        // would have to know about the Left/Right Nav's own widths.
        // bg-background (matching this Card's own override below) keeps
        // it opaque against blocks scrolling underneath.
        className="sticky top-0 z-10 flex-row cursor-pointer select-none items-start justify-between space-y-0 bg-background"
      >
        <CardTitle>Showcase Page</CardTitle>
        <div className="flex items-center gap-2">
          <div
            className={cn("flex flex-wrap items-center justify-end", ACTION_BUTTON_ROW_GAP)}
            onClick={(e) => e.stopPropagation()}
          >
            <span
              className="flex items-center self-center"
              title={
                page.is_public
                  ? "Toggle off to make this private again"
                  : "Toggle on to make this public and get a shareable link"
              }
            >
              <Switch
                checked={page.is_public}
                onCheckedChange={(checked) => togglePublic.mutate({ is_public: checked })}
                disabled={togglePublic.isPending}
                label="Make Showcase Page public"
              />
            </span>
            {publicUrl && <CopyButton text={publicUrl} label="Copy link" variant="ghost" />}
            {isOpen && (
              <BlockTypeMenu
                triggerLabel="Add block"
                onSelect={addRow}
                disabled={updatePage.isPending}
              />
            )}
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
          <p className="text-sm text-muted-foreground">
            A freeform, shareable page for this role — seeded once from your generated resume
            content, then fully yours to edit. Each block is a row that can hold one or more
            side-by-side columns — use "+ Add column" on any row to turn it into a multi-column
            layout.
          </p>

          {page.blocks.length === 0 && (
            <p className="text-sm text-muted-foreground">
              No blocks yet — add one from the "Add block" control above.
            </p>
          )}

          <div className="flex flex-col gap-3">
            {page.blocks.map((row, index) => (
              <ShowcaseRowCard
                key={row.id}
                row={row}
                index={index}
                total={page.blocks.length}
                targetRoleId={targetRoleId}
                topicOptions={topicOptions}
                onMove={(direction) => moveRow(row.id, direction)}
                onAddColumn={(type) => addColumn(row.id, type)}
                onInsertBelow={(type) => insertRowAfter(row.id, type)}
                onRemoveRow={() => setRemoveTarget({ kind: "row", row })}
                onRemoveColumn={(column) => setRemoveTarget({ kind: "column", rowId: row.id, column })}
                onSaveColumn={(column) => saveColumn(row.id, column)}
                isSaving={updatePage.isPending}
                focusColumnId={focusColumnId}
                onFocusHandled={() => setFocusColumnId(null)}
              />
            ))}
          </div>

          {updatePage.isError && (
            <p role="alert" className="text-sm text-destructive">
              {getErrorMessage(updatePage.error)}
            </p>
          )}
          {togglePublic.isError && (
            <p role="alert" className="text-sm text-destructive">
              {getErrorMessage(togglePublic.error)}
            </p>
          )}
        </CardContent>
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
        isPending={updatePage.isPending}
      />
    </Card>
  );
}

function mergeTopics(
  master: components["schemas"]["InterviewTopicResponse"][] | undefined,
  role: components["schemas"]["InterviewTopicResponse"][] | undefined,
): components["schemas"]["InterviewTopicResponse"][] {
  const byId = new Map<string, components["schemas"]["InterviewTopicResponse"]>();
  for (const topic of [...(master ?? []), ...(role ?? [])]) {
    byId.set(topic.id, topic);
  }
  return [...byId.values()];
}

/**
 * A trigger button that opens a small popover menu of block/column
 * types — selecting one fires `onSelect` immediately (no separate
 * confirm step), replacing what used to be a two-step Select+Button
 * flow. No heavy dropdown-menu library exists in this app (matching
 * the hand-rolled-primitives convention elsewhere), so this is a plain
 * absolutely-positioned panel closed on outside click or Escape.
 */
function BlockTypeMenu({
  triggerLabel,
  onSelect,
  disabled,
  variant = "outline",
}: {
  triggerLabel: string;
  onSelect: (type: ShowcaseColumnType) => void;
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
                onSelect(value as ShowcaseColumnType);
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

function ShowcaseRowCard({
  row,
  index,
  total,
  targetRoleId,
  topicOptions,
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
  row: ShowcaseRow;
  index: number;
  total: number;
  targetRoleId: string;
  topicOptions: components["schemas"]["InterviewTopicResponse"][];
  onMove: (direction: "up" | "down") => void;
  onAddColumn: (type: ShowcaseColumnType) => void;
  onInsertBelow: (type: ShowcaseColumnType) => void;
  onRemoveRow: () => void;
  onRemoveColumn: (column: ShowcaseColumn) => void;
  onSaveColumn: (column: ShowcaseColumn) => void;
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
          <BlockTypeMenu triggerLabel="Add column" onSelect={onAddColumn} disabled={isSaving} />
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
          <ShowcaseColumnCard
            key={column.id}
            column={column}
            targetRoleId={targetRoleId}
            topicOptions={topicOptions}
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
          ever being able to add at the very end of the page (direct
          2026-08-24 report). */}
      <div className="flex justify-center border-t border-border px-3 py-1">
        <BlockTypeMenu
          triggerLabel="Add block below"
          onSelect={onInsertBelow}
          disabled={isSaving}
          variant="ghost"
        />
      </div>
    </div>
  );
}

function ShowcaseColumnCard({
  column,
  targetRoleId,
  topicOptions,
  canRemoveIndividually,
  onRemove,
  onSave,
  isSaving,
  shouldFocus,
  onFocusHandled,
}: {
  column: ShowcaseColumn;
  targetRoleId: string;
  topicOptions: components["schemas"]["InterviewTopicResponse"][];
  canRemoveIndividually: boolean;
  onRemove: () => void;
  onSave: (updated: ShowcaseColumn) => void;
  isSaving: boolean;
  /** True for exactly the column that was just created (by any of the
   * "Add block"/"Add block below"/"Add column" controls) — scrolls
   * itself into view and opens its own editor on mount, once. */
  shouldFocus: boolean;
  onFocusHandled: () => void;
}) {
  const uploadImage = useUploadShowcaseColumnImage(targetRoleId);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const [isEditing, setIsEditing] = useState(false);
  const [draft, setDraft] = useState<ShowcaseColumn>(column);

  // Re-seeds the draft only when the column identity changes or edit
  // mode is freshly entered — not reactively on every background
  // refetch, matching this app's "initialize once, don't clobber
  // in-progress edits" convention.
  useEffect(() => {
    if (!isEditing) setDraft(column);
  }, [column, isEditing]);

  // Runs once, only for the column that was just added (this component
  // only ever mounts once per column id, thanks to the `key={column.id}`
  // in ShowcaseRowCard) — brings a freshly-added block into view and
  // straight into edit mode instead of leaving the person to go hunting
  // for whatever they just added. Image columns have no edit-mode
  // toggle (their label/upload controls are always visible), so only
  // the scroll applies there.
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
    if (file) uploadImage.mutate({ columnId: column.id, file });
  }

  return (
    <div ref={containerRef} className="min-w-0 flex-1 basis-0 rounded-md border border-border bg-background">
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
              <Label htmlFor={`column-label-${column.id}`}>Label</Label>
              <Input
                id={`column-label-${column.id}`}
                value={draft.label}
                onChange={(e) => setDraft({ ...draft, label: e.target.value })}
                maxLength={100}
              />
            </div>

            {draft.type === "rich_text" && (
              <RichTextEditor
                defaultValue={draft.html}
                onChange={(html) => setDraft({ ...draft, html })}
                placeholder="Write something..."
                autoFocus
              />
            )}

            {draft.type === "video_embed" && (
              <div className="flex flex-col gap-1.5">
                <Label htmlFor={`column-video-${column.id}`}>Embed URL</Label>
                <Input
                  id={`column-video-${column.id}`}
                  type="url"
                  placeholder="https://www.youtube.com/embed/..."
                  value={draft.video_embed_url ?? ""}
                  onChange={(e) => setDraft({ ...draft, video_embed_url: e.target.value })}
                />
              </div>
            )}

            {draft.type === "external_link" && (
              <div className="flex flex-col gap-1.5">
                <Label htmlFor={`column-url-${column.id}`}>URL</Label>
                <Input
                  id={`column-url-${column.id}`}
                  type="url"
                  placeholder="https://..."
                  value={draft.external_url ?? ""}
                  onChange={(e) => setDraft({ ...draft, external_url: e.target.value })}
                />
              </div>
            )}

            {draft.type === "article_link" && (
              <div className="flex flex-col gap-1.5">
                <Label htmlFor={`column-article-${column.id}`}>Article</Label>
                <Select
                  id={`column-article-${column.id}`}
                  value={draft.article_topic_id ?? ""}
                  onChange={(e) => setDraft({ ...draft, article_topic_id: e.target.value || null })}
                >
                  <option value="">Choose an article...</option>
                  {topicOptions.map((topic) => (
                    <option key={topic.id} value={topic.id}>
                      {topic.name}
                      {!topic.is_public ? " (currently private)" : ""}
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
              <Button variant="ghost" size="sm" onClick={() => setIsEditing(false)}>
                Cancel
              </Button>
            </div>
          </div>
        ) : (
          <ColumnPreview column={column} />
        )}

        {column.type === "image" && (
          <div className="flex flex-col gap-2">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor={`column-label-${column.id}`}>Label</Label>
              <Input
                id={`column-label-${column.id}`}
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
    </div>
  );
}

function ColumnPreview({ column }: { column: ShowcaseColumn }) {
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
