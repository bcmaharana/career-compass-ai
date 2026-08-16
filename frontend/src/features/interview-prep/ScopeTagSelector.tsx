import { Label } from "@/components/ui/label";

export interface ScopeOption {
  /** null = Master (generic). */
  id: string | null;
  label: string;
}

/**
 * Multi-select for which scopes a Topic/Question is tagged into and
 * visible under — Master and/or one or more Target Roles, requested
 * directly by the user: "Each question or topic can be tagged with one
 * or more roles... Correcting in one place will update in others
 * automatically." A tagged item is the SAME row surfaced under every
 * checked scope, not a copy. Deliberately a flat, freely-editable set
 * (not a "home scope is pinned" model) — the user's explicit choice —
 * so every option here, including the scope the item was created
 * under, can be unchecked.
 *
 * Plain checkboxes rather than a real multi-select component — matches
 * this app's "no heavy UI kit" convention (see Switch/RichTextEditor's
 * own hand-rolled precedent) and there's no existing checkbox-group
 * primitive to build on top of.
 */
export function ScopeTagSelector({
  id,
  options,
  selected,
  onChange,
}: {
  id: string;
  options: ScopeOption[];
  selected: (string | null)[];
  onChange: (next: (string | null)[]) => void;
}) {
  function toggle(optionId: string | null) {
    onChange(
      selected.includes(optionId)
        ? selected.filter((s) => s !== optionId)
        : [...selected, optionId],
    );
  }

  return (
    <div className="flex flex-col gap-1.5">
      <Label htmlFor={id}>Scopes</Label>
      <div id={id} className="flex flex-col gap-1.5 rounded-md border border-border p-2.5">
        {options.map((option) => (
          <label
            key={option.id ?? "master"}
            className="flex cursor-pointer items-center gap-2 text-sm"
          >
            <input
              type="checkbox"
              checked={selected.includes(option.id)}
              onChange={() => toggle(option.id)}
              className="h-4 w-4 rounded border-border accent-accent"
            />
            {option.label}
          </label>
        ))}
      </div>
    </div>
  );
}
