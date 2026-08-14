/**
 * Shared by every reorderable Career Profile section (all of them except
 * ProfileHeader, which is always first) — CareerProfilePage.tsx owns the
 * actual order and passes these down so each section's own MoveButtons
 * can trigger a page-level reorder rather than reordering itself.
 *
 * `cardBackground` is here for the same reason: which of the two
 * alternating shades a section's outer Card uses has to follow its
 * *current* render position, not be hardcoded per component — sections
 * are user-reorderable now, so a fixed "Experience is always white"
 * assumption breaks the moment someone actually reorders the page.
 */
export interface SectionOrderProps {
  onMoveUp: () => void;
  onMoveDown: () => void;
  isFirst: boolean;
  isLast: boolean;
  moveDisabled?: boolean;
  cardBackground: "card" | "background";
  /** Whole-section resume-inclusion toggle (CareerProfile.resume_section_toggles)
   * — see ResumeIncludeToggle.tsx. Defaults to true (included) when the
   * profile has never set a preference for this section. */
  resumeIncluded: boolean;
  onToggleResumeIncluded: (checked: boolean) => void;
  resumeToggleDisabled?: boolean;
}

/**
 * The item-row alternation inside a section has to start on the
 * opposite shade from that section's own outer Card (see the brief
 * follow-up: "if the outer card is white, the first inner card
 * shouldn't be white too") — this derives that from the same
 * `cardBackground` every section already receives, so both stay
 * correct together after a reorder instead of two separate hardcoded
 * patterns drifting out of sync.
 */
export function itemAlternateClass(cardBackground: "card" | "background", index: number): string {
  return cardBackground === "background"
    ? index % 2 === 0
      ? "bg-card"
      : "bg-[hsl(var(--center-bg))]"
    : index % 2 === 0
      ? "bg-background"
      : "bg-card";
}
