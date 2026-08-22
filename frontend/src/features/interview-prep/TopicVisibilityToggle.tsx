import { Switch } from "@/components/ui/switch";

/**
 * Thin Switch wrapper for a Topic's public/private ("Article" when
 * framed externally) toggle — mirrors ResumeIncludeToggle.tsx's exact
 * shape (hover tooltip explaining both states, `self-center` against
 * its taller sibling buttons) so this feature's toggle reads
 * consistently with the app's other Switch-based toggle.
 */
export function TopicVisibilityToggle({
  checked,
  onCheckedChange,
  disabled,
  label,
}: {
  checked: boolean;
  onCheckedChange: (checked: boolean) => void;
  disabled?: boolean;
  label: string;
}) {
  return (
    <span
      className="flex items-center self-center"
      title={
        checked
          ? "Toggle off to make this private again"
          : "Toggle on to make this public and get a shareable link"
      }
    >
      <Switch
        checked={checked}
        onCheckedChange={onCheckedChange}
        disabled={disabled}
        label={`Make ${label} public`}
      />
    </span>
  );
}
