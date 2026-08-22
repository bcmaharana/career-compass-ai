import { useCurrentUser } from "@/api/queries/auth";
import { useInterviewTopics } from "@/api/queries/interview-prep";
import {
  useShowcasePage,
  useToggleShowcasePagePublic,
  useUpdateShowcasePage,
  useUploadShowcaseBlockImage,
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
} from "lucide-react";
import { useEffect, useRef, useState } from "react";

type ShowcaseBlock = components["schemas"]["ShowcaseBlockPayload"];
type ShowcaseBlockType = ShowcaseBlock["type"];

const BLOCK_TYPE_LABELS: Record<ShowcaseBlockType, string> = {
  rich_text: "Text",
  image: "Image",
  video_embed: "Video",
  article_link: "Article link",
  external_link: "External link",
};

function newBlock(type: ShowcaseBlockType, label: string): ShowcaseBlock {
  return {
    id: crypto.randomUUID(),
    type,
    label,
    html: type === "rich_text" ? "" : null,
    image_url: null,
    video_embed_url: null,
    article_topic_id: null,
    external_url: null,
  };
}

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
 * Every structural change (add/remove/reorder block, edit a block's
 * saved content) immediately PATCHes the whole `blocks` array — the
 * same "whole list as one JSON blob, replaced atomically" shape
 * CoreCompetencies/resume_section_toggles already use on the backend.
 * Each block's own content editor uses a local edit-mode-with-Save
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
  // Article-link blocks can point at any of this user's own Interview
  // Prep Topics — merged from Master and this role's own scope (the
  // two scopes this page's own Table of Contents already treats as
  // "this user's topics" elsewhere in the app; there's no single
  // "every topic regardless of scope" endpoint to fetch from instead).
  const { data: masterTopics } = useInterviewTopics(null);
  const { data: roleTopics } = useInterviewTopics(targetRoleId);
  const topicOptions = mergeTopics(masterTopics, roleTopics);

  const [addType, setAddType] = useState<ShowcaseBlockType>("rich_text");
  const [removeTarget, setRemoveTarget] = useState<ShowcaseBlock | null>(null);

  if (!page) {
    return null;
  }

  function commit(blocks: ShowcaseBlock[]) {
    updatePage.mutate({ blocks });
  }

  function addBlock() {
    commit([...page!.blocks, newBlock(addType, BLOCK_TYPE_LABELS[addType])]);
  }

  function saveBlock(updated: ShowcaseBlock) {
    commit(page!.blocks.map((b) => (b.id === updated.id ? updated : b)));
  }

  function removeBlock() {
    if (!removeTarget) return;
    commit(page!.blocks.filter((b) => b.id !== removeTarget.id));
    setRemoveTarget(null);
  }

  function moveBlock(blockId: string, direction: "up" | "down") {
    const blocks = page!.blocks;
    const index = blocks.findIndex((b) => b.id === blockId);
    const targetIndex = direction === "up" ? index - 1 : index + 1;
    if (index === -1 || targetIndex < 0 || targetIndex >= blocks.length) return;
    const next = [...blocks];
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
        className="flex-row cursor-pointer select-none items-start justify-between space-y-0"
      >
        <CardTitle>Showcase Page</CardTitle>
        <div className="flex items-center gap-2">
          <div
            className={cn("flex items-center", ACTION_BUTTON_ROW_GAP)}
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
            content, then fully yours to edit. Reorder, relabel, or replace anything below.
          </p>

          {page.blocks.length === 0 && (
            <p className="text-sm text-muted-foreground">No blocks yet — add one below.</p>
          )}

          <div className="flex flex-col gap-2">
            {page.blocks.map((block, index) => (
              <ShowcaseBlockRow
                key={block.id}
                block={block}
                index={index}
                total={page.blocks.length}
                targetRoleId={targetRoleId}
                topicOptions={topicOptions}
                onMove={(direction) => moveBlock(block.id, direction)}
                onRemove={() => setRemoveTarget(block)}
                onSave={saveBlock}
                isSaving={updatePage.isPending}
              />
            ))}
          </div>

          <div className={cn("flex items-center", ACTION_BUTTON_ROW_GAP)}>
            <Select
              aria-label="Block type to add"
              value={addType}
              onChange={(e) => setAddType(e.target.value as ShowcaseBlockType)}
              className="h-9 w-auto"
            >
              {Object.entries(BLOCK_TYPE_LABELS).map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </Select>
            <Button variant="outline" size="sm" onClick={addBlock} disabled={updatePage.isPending}>
              <Plus className="h-3.5 w-3.5" />
              Add block
            </Button>
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
        onConfirm={removeBlock}
        title="Remove this block?"
        description={
          removeTarget ? `Remove the "${removeTarget.label}" block? This can't be undone.` : ""
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

function ShowcaseBlockRow({
  block,
  index,
  total,
  targetRoleId,
  topicOptions,
  onMove,
  onRemove,
  onSave,
  isSaving,
}: {
  block: ShowcaseBlock;
  index: number;
  total: number;
  targetRoleId: string;
  topicOptions: components["schemas"]["InterviewTopicResponse"][];
  onMove: (direction: "up" | "down") => void;
  onRemove: () => void;
  onSave: (updated: ShowcaseBlock) => void;
  isSaving: boolean;
}) {
  const uploadImage = useUploadShowcaseBlockImage(targetRoleId);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [isEditing, setIsEditing] = useState(false);
  const [draft, setDraft] = useState<ShowcaseBlock>(block);

  // Re-seeds the draft only when the block identity changes or edit
  // mode is freshly entered — not reactively on every background
  // refetch, matching this app's "initialize once, don't clobber
  // in-progress edits" convention.
  useEffect(() => {
    if (!isEditing) setDraft(block);
  }, [block, isEditing]);

  function startEditing() {
    setDraft(block);
    setIsEditing(true);
  }

  function save() {
    onSave(draft);
    setIsEditing(false);
  }

  function handleFileChange(event: React.ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (file) uploadImage.mutate({ blockId: block.id, file });
  }

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
            {BLOCK_TYPE_LABELS[block.type]}
          </span>
          <p className="text-sm font-medium">{block.label}</p>
        </div>
        <div className={cn("flex items-center", ACTION_BUTTON_ROW_GAP)}>
          {!isEditing && block.type !== "image" && (
            <Button variant="ghost" size="sm" className="h-7 w-7 p-0" onClick={startEditing}>
              <Pencil className="h-3.5 w-3.5" />
            </Button>
          )}
          <Button variant="ghost" size="sm" className="h-7 w-7 p-0" onClick={onRemove}>
            <Trash2 className="h-3.5 w-3.5" />
          </Button>
        </div>
      </div>

      <div className="flex flex-col gap-3 border-t border-border p-3">
        {isEditing ? (
          <div className="flex flex-col gap-3">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor={`block-label-${block.id}`}>Label</Label>
              <Input
                id={`block-label-${block.id}`}
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
                <Label htmlFor={`block-video-${block.id}`}>Embed URL</Label>
                <Input
                  id={`block-video-${block.id}`}
                  type="url"
                  placeholder="https://www.youtube.com/embed/..."
                  value={draft.video_embed_url ?? ""}
                  onChange={(e) => setDraft({ ...draft, video_embed_url: e.target.value })}
                />
              </div>
            )}

            {draft.type === "external_link" && (
              <div className="flex flex-col gap-1.5">
                <Label htmlFor={`block-url-${block.id}`}>URL</Label>
                <Input
                  id={`block-url-${block.id}`}
                  type="url"
                  placeholder="https://..."
                  value={draft.external_url ?? ""}
                  onChange={(e) => setDraft({ ...draft, external_url: e.target.value })}
                />
              </div>
            )}

            {draft.type === "article_link" && (
              <div className="flex flex-col gap-1.5">
                <Label htmlFor={`block-article-${block.id}`}>Article</Label>
                <Select
                  id={`block-article-${block.id}`}
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
          <BlockPreview block={block} />
        )}

        {block.type === "image" && (
          <div className="flex flex-col gap-2">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor={`block-label-${block.id}`}>Label</Label>
              <Input
                id={`block-label-${block.id}`}
                value={block.label}
                onChange={(e) => onSave({ ...block, label: e.target.value })}
                onBlur={(e) => onSave({ ...block, label: e.target.value })}
                maxLength={100}
              />
            </div>
            {block.image_url ? (
              <img
                src={block.image_url}
                alt=""
                className="max-h-[60vh] w-full max-w-xl rounded-md border border-border object-contain"
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
                  : block.image_url
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

function BlockPreview({ block }: { block: ShowcaseBlock }) {
  switch (block.type) {
    case "rich_text":
      return block.html ? (
        <RichTextDisplay html={block.html} className="max-h-48 overflow-y-auto scrollbar-hide" />
      ) : (
        <p className="text-sm text-muted-foreground">No content yet — click Edit to add some.</p>
      );
    case "video_embed":
      return block.video_embed_url ? (
        <p className="truncate text-sm text-muted-foreground">{block.video_embed_url}</p>
      ) : (
        <p className="text-sm text-muted-foreground">No embed URL yet — click Edit to add one.</p>
      );
    case "external_link":
      return block.external_url ? (
        <a
          href={block.external_url}
          target="_blank"
          rel="noreferrer"
          className="flex items-center gap-1 text-sm font-medium text-accent underline underline-offset-2 hover:text-accent/80"
        >
          <ExternalLink className="h-3.5 w-3.5" />
          {block.external_url}
        </a>
      ) : (
        <p className="text-sm text-muted-foreground">No URL yet — click Edit to add one.</p>
      );
    case "article_link":
      return block.article_topic_id ? (
        <p className="text-sm text-muted-foreground">Links to an Article.</p>
      ) : (
        <p className="text-sm text-muted-foreground">No article chosen yet — click Edit to pick one.</p>
      );
    case "image":
      return null;
  }
}
