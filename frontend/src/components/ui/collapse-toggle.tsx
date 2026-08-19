import { Button } from "@/components/ui/button";
import { Eye, EyeOff } from "lucide-react";

interface CollapseToggleProps {
  isOpen: boolean;
  onToggle: () => void;
  /** Section name, for the accessible label only (e.g. "Career Goals"). */
  label: string;
  /** Optional size/spacing override merged onto the inner Button (e.g.
   * Interview Prep's Topic/Question rows shrinking it below the shared
   * `size="sm"` default so the icon itself isn't the tallest thing in an
   * otherwise-tightened row). Omitted everywhere else, so every existing
   * usage is unaffected. */
  className?: string;
}

/**
 * Hide/show icon for a collapsible section (Career Profile page, UI
 * enhancement brief Part 2.1) — shared across every section (Profile
 * Header, Experience, Education, Certifications, Career Goals,
 * Highlights, Achievements, Recommendations) rather than reimplemented
 * per section. Deliberately Eye/EyeOff rather than a chevron: this page
 * already uses ChevronUp/ChevronDown for item reordering (see
 * MoveButtons), and reusing that shape here for a different action would
 * read as the same control doing two unrelated things.
 */
export function CollapseToggle({ isOpen, onToggle, label, className }: CollapseToggleProps) {
  return (
    <Button
      type="button"
      variant="ghost"
      size="sm"
      onClick={onToggle}
      aria-expanded={isOpen}
      aria-label={isOpen ? `Hide ${label}` : `Show ${label}`}
      className={className}
    >
      {isOpen ? <EyeOff className="h-3.5 w-3.5" /> : <Eye className="h-3.5 w-3.5" />}
    </Button>
  );
}
