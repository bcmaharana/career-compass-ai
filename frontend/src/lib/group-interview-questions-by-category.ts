import type { components } from "@/api/schema.gen";

type InterviewQuestion = components["schemas"]["InterviewQuestionResponse"];

export interface InterviewQuestionCategoryGroup {
  /** null = questions with no category set — always a trailing
   * "Uncategorized" group, not a real, nameable category. */
  category: string | null;
  questions: InterviewQuestion[];
}

/**
 * Groups Interview Questions by their `category` free-text label — same
 * "no separate entity, just a string on each item" grouping logic
 * `groupInterviewTopicsBySection` already established for Topics'
 * `section` field, mirrored here rather than generalized since the two
 * source types differ.
 *
 * Category order follows each category's *first-encountered position*
 * in `questions` (which is already server-ordered by display_order) —
 * there's no separate "category order" concept of its own, so this is
 * the only place category order can meaningfully come from.
 */
export function groupInterviewQuestionsByCategory(
  questions: InterviewQuestion[],
): InterviewQuestionCategoryGroup[] {
  const order: string[] = [];
  const groups = new Map<string, InterviewQuestion[]>();
  const uncategorized: InterviewQuestion[] = [];

  for (const question of questions) {
    const category = question.category?.trim();
    if (!category) {
      uncategorized.push(question);
      continue;
    }
    const existing = groups.get(category);
    if (existing) {
      existing.push(question);
    } else {
      groups.set(category, [question]);
      order.push(category);
    }
  }

  const result: InterviewQuestionCategoryGroup[] = order.map((category) => ({
    category,
    questions: groups.get(category) as InterviewQuestion[],
  }));

  if (uncategorized.length > 0) {
    result.push({ category: null, questions: uncategorized });
  }

  return result;
}
