import { cn } from "@/lib/utils";

interface SwitchProps {
  checked: boolean;
  onCheckedChange: (checked: boolean) => void;
  disabled?: boolean;
  /** Accessible label — no visible text of its own, same convention as
   * MoveButtons (an icon-only control, described via aria-label rather
   * than a persistent on-screen caption). */
  label: string;
}

/**
 * Hand-rolled on/off switch — no Radix, matching this app's minimal-
 * dependency UI kit (see CLAUDE.md's "no Radix, no heavy UI kit"
 * convention). Powers the resume-inclusion toggle on every Career
 * Profile section and item (see CareerProfilePage.tsx's
 * `resumeIncluded`/`onToggleResumeIncluded` props and each section's own
 * per-item toggle) — "on" (the rainbow-gradient track, matching this
 * app's accent language for every other active/branded control) means
 * "included in a generated resume," off means excluded, per that
 * feature's design.
 */
export function Switch({ checked, onCheckedChange, disabled, label }: SwitchProps) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      aria-label={label}
      disabled={disabled}
      onClick={() => onCheckedChange(!checked)}
      className={cn(
        "relative inline-flex h-5 w-9 shrink-0 items-center rounded-full transition-colors disabled:cursor-not-allowed disabled:opacity-50",
        checked
          ? "bg-[linear-gradient(90deg,#a855f7_12.5%,#3b82f6_37.5%,#22c55e_58.33%,#fdba74_75%,#fca5a5_91.67%)]"
          : "bg-muted",
      )}
    >
      <span
        className={cn(
          "inline-block h-4 w-4 transform rounded-full bg-white shadow transition-transform",
          checked ? "translate-x-4" : "translate-x-0.5",
        )}
      />
    </button>
  );
}
