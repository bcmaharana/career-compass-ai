import type { components } from "@/api/schema.gen";

type InterviewTopic = components["schemas"]["InterviewTopicResponse"];

export interface InterviewTopicSectionGroup {
  /** null = topics with no section set — always a trailing "Ungrouped"
   * group, not a real, nameable section. */
  section: string | null;
  topics: InterviewTopic[];
}

/**
 * Groups Interview Topics by their `section` free-text label — same
 * "no separate entity, just a string on each item" grouping logic
 * `groupCompetenciesByCategory` (lib/group-by-category.ts) already
 * established for Core Competencies, reimplemented here rather than
 * reused directly since that helper is typed specifically to
 * CoreCompetencyPayload.
 *
 * Section order follows each section's *first-encountered position* in
 * `topics` (which is already server-ordered by display_order) — there's
 * no separate "section order" concept of its own, so this is the only
 * place section order can meaningfully come from.
 */
export function groupInterviewTopicsBySection(
  topics: InterviewTopic[],
): InterviewTopicSectionGroup[] {
  const order: string[] = [];
  const groups = new Map<string, InterviewTopic[]>();
  const ungrouped: InterviewTopic[] = [];

  for (const topic of topics) {
    const section = topic.section?.trim();
    if (!section) {
      ungrouped.push(topic);
      continue;
    }
    const existing = groups.get(section);
    if (existing) {
      existing.push(topic);
    } else {
      groups.set(section, [topic]);
      order.push(section);
    }
  }

  const result: InterviewTopicSectionGroup[] = order.map((section) => ({
    section,
    topics: groups.get(section) as InterviewTopic[],
  }));

  if (ungrouped.length > 0) {
    result.push({ section: null, topics: ungrouped });
  }

  return result;
}
