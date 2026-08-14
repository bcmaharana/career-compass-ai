import { Switch } from "@/components/ui/switch";

interface ResumeIncludeToggleProps {
  checked: boolean;
  onCheckedChange: (checked: boolean) => void;
  disabled?: boolean;
  /** What this toggles, for the accessible label only — e.g. "Career
   * Highlights section" or the item's own title. Interpolated as
   * `Include {label} in resume`. */
  label: string;
}

/**
 * The bare Switch used both at the section level
 * (CareerProfilePage.tsx's `resumeIncluded`/`onToggleResumeIncluded`,
 * one per SECTION_DEFS entry) and at the per-item level (every card
 * inside a section, plus each Core Competency chip) — one shared
 * wrapper so the hover tooltip and accessible label stay identical
 * everywhere this feature's toggle appears, per the resume-inclusion
 * toggle feature: "On" (default) means the section/item is included
 * when a resume is generated; "Off" excludes it. See
 * ResumeExportService on the backend for where this flag is actually
 * consumed. `self-center` since it always sits first in an
 * `items-start` action row (see every career-profile section's header/
 * item markup) alongside taller text buttons — without it, the switch
 * would sit top-aligned instead of centered against its siblings.
 */
export function ResumeIncludeToggle({
  checked,
  onCheckedChange,
  disabled,
  label,
}: ResumeIncludeToggleProps) {
  return (
    <span
      className="flex items-center self-center"
      title={
        checked
          ? "Toggle off to exclude this from the resume"
          : "Toggle on to include this in the resume"
      }
    >
      <Switch
        checked={checked}
        onCheckedChange={onCheckedChange}
        disabled={disabled}
        label={`Include ${label} in resume`}
      />
    </span>
  );
}
