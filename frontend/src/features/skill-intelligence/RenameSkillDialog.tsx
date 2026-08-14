import { Button } from "@/components/ui/button";
import { Dialog } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { getErrorMessage } from "@/lib/errors";
import { type FormEvent, useEffect, useState } from "react";

const NEW_CATEGORY_VALUE = "__new__";
const NO_CATEGORY_VALUE = "";

interface RenameSkillDialogProps {
  open: boolean;
  name: string;
  onNameChange: (value: string) => void;
  onSubmit: (event: FormEvent) => void;
  onClose: () => void;
  isPending: boolean;
  error?: unknown;
  // Optional: only Core Competencies and My Skills pass these (both edit
  // CareerProfile.core_competencies, which carries a per-item category —
  // see CoreCompetency in the backend domain). Target Role Skill
  // Requirements omits them since required_skills stays a plain string
  // list with no category concept.
  category?: string;
  onCategoryChange?: (value: string) => void;
  categoryOptions?: string[];
  // Both default to today's rename-only wording — Core Competencies and
  // My Skills pass "Add competency"/"Edit competency" since this same
  // dialog now also handles adding a brand-new item, not just renaming
  // an existing one.
  title?: string;
  submitLabel?: string;
  // Optional muted helper text under the name field — Core Competencies
  // and My Skills pass this only in "add" mode, to surface that the
  // field accepts several comma-separated names in one submission (see
  // buildCompetenciesFromAddInput).
  nameHint?: string;
}

/**
 * Generic add/rename dialog reused by My Skills, Core Competencies, and
 * Target Role Skill Requirements. Each of those is just a plain string
 * (or, for the first two, a {name, category} pair) in its own list — no
 * shared catalog since ADR-005 — so a submit here only ever affects the
 * one list it's called from.
 *
 * The category field is a <Select> of every known category plus a
 * "+ New category..." option that reveals a free-text input — not a
 * native <input list>+<datalist>. A datalist filters its own suggestion
 * popup against the input's *current* text, so pre-filling the field
 * with the item's current category (an exact match) made the browser
 * only ever offer that one match back — a real bug, not just a rough
 * edge, caught by re-reading how <datalist> filtering actually works,
 * not by trying it and guessing.
 */
export function RenameSkillDialog({
  open,
  name,
  onNameChange,
  onSubmit,
  onClose,
  isPending,
  error,
  category,
  onCategoryChange,
  categoryOptions,
  title = "Rename skill",
  submitLabel = "Save",
  nameHint,
}: RenameSkillDialogProps) {
  const showCategory = onCategoryChange !== undefined;
  const options = categoryOptions ?? [];
  const currentCategory = category ?? "";

  // Whether the free-text "new category" input is showing instead of
  // the <Select>. Reset every time the dialog opens (for whichever item
  // it's opening for) rather than persisting across opens — otherwise a
  // previous "adding a new category" state could leak into the next
  // item, even though that item's category is already a known option.
  const [addingNewCategory, setAddingNewCategory] = useState(false);
  useEffect(() => {
    if (open) setAddingNewCategory(false);
  }, [open, name]);

  const selectValue = addingNewCategory
    ? NEW_CATEGORY_VALUE
    : options.includes(currentCategory)
      ? currentCategory
      : NO_CATEGORY_VALUE;

  function handleCategorySelectChange(value: string) {
    if (value === NEW_CATEGORY_VALUE) {
      setAddingNewCategory(true);
      onCategoryChange?.("");
      return;
    }
    setAddingNewCategory(false);
    onCategoryChange?.(value);
  }

  return (
    <Dialog open={open} onClose={onClose} title={title}>
      <form className="flex flex-col gap-4" onSubmit={onSubmit}>
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="rename-skill-name">Skill name</Label>
          <Input
            id="rename-skill-name"
            autoFocus
            required
            value={name}
            onChange={(e) => onNameChange(e.target.value)}
          />
          {nameHint && <p className="text-xs text-muted-foreground">{nameHint}</p>}
        </div>
        {showCategory && (
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="rename-skill-category">Category (optional)</Label>
            <Select
              id="rename-skill-category"
              value={selectValue}
              onChange={(e) => handleCategorySelectChange(e.target.value)}
            >
              <option value={NO_CATEGORY_VALUE}>No category</option>
              {options.map((option) => (
                <option key={option} value={option}>
                  {option}
                </option>
              ))}
              <option value={NEW_CATEGORY_VALUE}>+ New category...</option>
            </Select>
            {addingNewCategory && (
              <Input
                autoFocus
                value={currentCategory}
                onChange={(e) => onCategoryChange?.(e.target.value)}
                placeholder="e.g. Agile & Scaling"
                aria-label="New category name"
              />
            )}
          </div>
        )}
        <Button type="submit" disabled={isPending || !name.trim()}>
          {isPending ? "Saving..." : submitLabel}
        </Button>
        {error != null && (
          <p role="alert" className="text-sm text-destructive">
            {getErrorMessage(error)}
          </p>
        )}
      </form>
    </Dialog>
  );
}
