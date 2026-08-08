import type { components } from "@/api/schema.gen";
import { Button } from "@/components/ui/button";
import { Dialog } from "@/components/ui/dialog";

type CareerProfileSummaryResponse = components["schemas"]["CareerProfileSummaryResponse"];

function describeSummary(summary: CareerProfileSummaryResponse): string {
  const parts: string[] = [];
  if (summary.experience_count > 0) parts.push(`${summary.experience_count} experience entries`);
  if (summary.education_count > 0) parts.push(`${summary.education_count} education entries`);
  if (summary.certification_count > 0) parts.push(`${summary.certification_count} certifications`);
  if (summary.career_highlight_count > 0)
    parts.push(`${summary.career_highlight_count} career highlights`);
  if (summary.key_achievement_count > 0)
    parts.push(`${summary.key_achievement_count} key achievements`);
  if (summary.competency_count > 0) parts.push(`${summary.competency_count} skills`);
  if (summary.has_summary) parts.push("a summary");
  if (summary.has_headline) parts.push("a headline");
  if (parts.length === 0) return "no existing data";
  if (parts.length === 1) return parts[0]!;
  return `${parts.slice(0, -1).join(", ")}, and ${parts[parts.length - 1]}`;
}

interface OverrideMergeDialogProps {
  open: boolean;
  onCancel: () => void;
  onMerge: () => void;
  onOverride: () => void;
  scopeLabel: string;
  summary: CareerProfileSummaryResponse | undefined;
  isMerging: boolean;
  isOverriding: boolean;
}

/**
 * Shown before a resume merge only when the destination profile (Master,
 * or a Target Role Profile — see scopeLabel) already has data — the
 * direct fix for the original complaint that drove this feature: merge
 * used to silently blend into whatever was already there, across
 * sessions, with zero warning. Not an extension of ConfirmDialog (that
 * component is hard-typed to exactly one confirm action, used at 9+ other
 * call sites) — this is a genuinely 3-way choice, built as its own small
 * dialog per this codebase's existing small-purpose-built-dialog
 * convention.
 *
 * "Override" clears the destination profile first, then runs the normal
 * merge (still deduped) on a clean slate. "Merge" runs the normal merge
 * directly — already deduped against whatever's there, just without the
 * warning. Neither path introduces new backend logic; both reuse the
 * existing clear and merge endpoints as-is.
 */
export function OverrideMergeDialog({
  open,
  onCancel,
  onMerge,
  onOverride,
  scopeLabel,
  summary,
  isMerging,
  isOverriding,
}: OverrideMergeDialogProps) {
  const isPending = isMerging || isOverriding;

  return (
    <Dialog open={open} onClose={onCancel} title={`${scopeLabel} already has data`}>
      <div className="flex flex-col gap-4">
        <p className="text-sm text-muted-foreground">
          {scopeLabel} already has {summary ? describeSummary(summary) : "existing data"}. How do
          you want to add this resume's selected items?
        </p>
        <div className="flex flex-col gap-2">
          <Button type="button" onClick={onMerge} disabled={isPending}>
            {isMerging ? "Merging..." : "Merge — add on top of what's there"}
          </Button>
          <Button type="button" variant="destructive" onClick={onOverride} disabled={isPending}>
            {isOverriding ? "Clearing and merging..." : `Override — clear ${scopeLabel} first`}
          </Button>
          <Button type="button" variant="ghost" onClick={onCancel} disabled={isPending}>
            Cancel
          </Button>
        </div>
        <p className="text-xs text-muted-foreground">
          Either way, items are still deduplicated against what's already there — Merge just adds
          anything new; Override starts this profile from a clean slate first.
        </p>
      </div>
    </Dialog>
  );
}
