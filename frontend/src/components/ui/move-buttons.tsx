import { Button } from "@/components/ui/button";
import { ChevronDown, ChevronUp } from "lucide-react";

interface MoveButtonsProps {
  onMoveUp: () => void;
  onMoveDown: () => void;
  isFirst: boolean;
  isLast: boolean;
  disabled?: boolean;
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
export function MoveButtons({ onMoveUp, onMoveDown, isFirst, isLast, disabled }: MoveButtonsProps) {
  return (
    <div className="flex flex-col">
      <Button
        variant="ghost"
        size="sm"
        onClick={onMoveUp}
        disabled={disabled || isFirst}
        aria-label="Move up"
        className="h-6 px-1"
      >
        <ChevronUp className="h-4 w-4" />
      </Button>
      <Button
        variant="ghost"
        size="sm"
        onClick={onMoveDown}
        disabled={disabled || isLast}
        aria-label="Move down"
        className="h-6 px-1"
      >
        <ChevronDown className="h-4 w-4" />
      </Button>
    </div>
  );
}
