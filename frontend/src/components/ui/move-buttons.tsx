import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { ChevronDown, ChevronUp, type LucideIcon } from "lucide-react";

interface MoveButtonsProps {
  onMoveUp: () => void;
  onMoveDown: () => void;
  isFirst: boolean;
  isLast: boolean;
  disabled?: boolean;
  /** Distinguishes what's being moved when a page has more than one
   * MoveButtons pair in the same view (e.g. a whole page section's own
   * reorder controls vs. a group *within* that section's content) —
   * without this, two pairs both labeled bare "Move up"/"Move down" are
   * ambiguous to a screen reader and to anything selecting by
   * accessible name. Interpolated as `Move {label} up`/`Move {label}
   * down`; omit for the plain "Move up"/"Move down" every existing
   * (single-pair-per-view) caller already uses. */
  label?: string;
  /** "horizontal" (default, side-by-side — every existing caller as of
   * 2026-08-09) or "vertical" (stacked). */
  orientation?: "vertical" | "horizontal";
  /** Override the up/down icon components — defaults to ChevronUp/
   * ChevronDown (every existing caller). */
  upIcon?: LucideIcon;
  downIcon?: LucideIcon;
  /** Size/spacing override merged onto both inner Buttons — e.g.
   * shrinking a per-item row's MoveButtons to a square `w-7 p-0` icon
   * button (height already matches the shared Button `sm` default, see
   * `button-variants.ts`) rather than this component's own slightly
   * wider `px-1` shape. Omitted by every section-level (whole-card, not
   * per-item) usage, which already matches its neighboring Add/Edit/
   * Clear/Collapse buttons via that same shared default. */
  className?: string;
}

/**
 * Up/down arrows for reordering a list item, shared across every
 * career-profile section (Experience, Education, Certifications,
 * Highlights, Achievements, Career Goals, Recommendations) rather than
 * reimplemented per section — same up/down-arrow shape everywhere.
 *
 * Disables the "up" arrow on the first item and "down" on the last,
 * rather than letting the click no-op silently — the backend already
 * treats a boundary move as a no-op (see app/adapters/db/reorder.py),
 * but disabling here gives the user an immediate visual signal instead
 * of a click that appears to do nothing.
 */
export function MoveButtons({
  onMoveUp,
  onMoveDown,
  isFirst,
  isLast,
  disabled,
  label,
  orientation = "horizontal",
  upIcon: UpIcon = ChevronUp,
  downIcon: DownIcon = ChevronDown,
  className,
}: MoveButtonsProps) {
  return (
    <div className={orientation === "horizontal" ? "flex flex-row gap-1" : "flex flex-col gap-1"}>
      <Button
        variant="ghost"
        size="sm"
        onClick={onMoveUp}
        disabled={disabled || isFirst}
        aria-label={label ? `Move ${label} up` : "Move up"}
        className={cn("h-7 px-1", className)}
      >
        <UpIcon className="h-3.5 w-3.5" />
      </Button>
      <Button
        variant="ghost"
        size="sm"
        onClick={onMoveDown}
        disabled={disabled || isLast}
        aria-label={label ? `Move ${label} down` : "Move down"}
        className={cn("h-7 px-1", className)}
      >
        <DownIcon className="h-3.5 w-3.5" />
      </Button>
    </div>
  );
}
