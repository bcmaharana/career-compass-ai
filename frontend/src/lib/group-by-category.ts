import type { components } from "@/api/schema.gen";

type CoreCompetency = components["schemas"]["CoreCompetencyPayload"];

export interface CompetencyGroup {
  /** null = items with no category (or a blank/whitespace-only one) — always a trailing "Uncategorized" group, not a real, nameable category. */
  category: string | null;
  items: CoreCompetency[];
}

/**
 * Groups Core Competencies / My Skills entries by category — both edit
 * the same `CareerProfile.core_competencies` field (see CoreCompetency
 * in the backend domain), so this is shared rather than duplicated per
 * page.
 *
 * Category order follows each category's *first-encountered position*
 * in `items`, not alphabetical — this is what makes moveCategoryGroup's
 * up/down reordering below actually mean something. There's no
 * `Category` entity in the backend at all (categories are just a string
 * on each item, no id/display_order of their own — see
 * CoreCompetency), so "category order" has nowhere else to live except
 * the underlying flat array's order; alphabetical sorting would
 * silently override any manual reordering on every render.
 */
export function groupCompetenciesByCategory(items: CoreCompetency[]): CompetencyGroup[] {
  const order: string[] = [];
  const groups = new Map<string, CoreCompetency[]>();
  const uncategorized: CoreCompetency[] = [];

  for (const item of items) {
    const category = item.category?.trim();
    if (!category) {
      uncategorized.push(item);
      continue;
    }
    const existing = groups.get(category);
    if (existing) {
      existing.push(item);
    } else {
      groups.set(category, [item]);
      order.push(category);
    }
  }

  const result: CompetencyGroup[] = order.map((category) => ({
    category,
    items: groups.get(category) as CoreCompetency[],
  }));

  if (uncategorized.length > 0) {
    result.push({ category: null, items: uncategorized });
  }

  return result;
}

export interface CompetencyGroupWithMoveIndex extends CompetencyGroup {
  /** Position among categorized groups only (0-based) — null for the
   * Uncategorized group, meaning "not movable." Feed isFirst/isLast on
   * a MoveButtons pair with `moveIndex === 0` / `moveIndex === categorizedCount - 1`. */
  moveIndex: number | null;
}

/**
 * Same grouping as groupCompetenciesByCategory, plus each categorized
 * group's position among *only* the categorized groups — computed once
 * here rather than inline in JSX (both CoreCompetenciesSection.tsx and
 * MySkillsSection.tsx need the identical isFirst/isLast bookkeeping for
 * their per-category MoveButtons).
 */
export function groupCompetenciesByCategoryWithMoveIndex(items: CoreCompetency[]): {
  groups: CompetencyGroupWithMoveIndex[];
  categorizedCount: number;
} {
  let index = -1;
  const groups = groupCompetenciesByCategory(items).map((group) => {
    if (group.category === null) return { ...group, moveIndex: null };
    index += 1;
    return { ...group, moveIndex: index };
  });
  return { groups, categorizedCount: index + 1 };
}

/**
 * Swaps `category`'s whole item block with the adjacent categorized
 * group (the previous one for "up", the next one for "down") and
 * returns a new flat array in the new order — item order *within* each
 * group is untouched, only which block comes first changes. The
 * "Uncategorized" group (category: null) is excluded from this swap
 * and always stays last — it's a fallback bucket for items with no
 * category, not something a user named and would expect to reorder.
 * A no-op (returns `items` as-is) if there's nothing adjacent to swap
 * with in the requested direction — callers should also disable the
 * relevant button via isFirst/isLast rather than relying on this alone
 * (same convention as MoveButtons' other callers).
 */
export function moveCategoryGroup(
  items: CoreCompetency[],
  category: string,
  direction: "up" | "down",
): CoreCompetency[] {
  const groups = groupCompetenciesByCategory(items);
  const categorized = groups.filter((g): g is { category: string; items: CoreCompetency[] } =>
    g.category !== null,
  );
  const uncategorizedItems = groups.find((g) => g.category === null)?.items ?? [];

  const index = categorized.findIndex((g) => g.category === category);
  if (index === -1) return items;

  const targetIndex = direction === "up" ? index - 1 : index + 1;
  if (targetIndex < 0 || targetIndex >= categorized.length) return items;

  const reordered = [...categorized];
  const temp = reordered[index]!;
  reordered[index] = reordered[targetIndex]!;
  reordered[targetIndex] = temp;

  return [...reordered.flatMap((g) => g.items), ...uncategorizedItems];
}
