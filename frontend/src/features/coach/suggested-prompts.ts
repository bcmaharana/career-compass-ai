import type { components } from "@/api/schema.gen";

type CareerProfile = components["schemas"]["CareerProfileResponse"];
type TargetRole = components["schemas"]["TargetRoleResponse"];
type GapAnalysisResponse = components["schemas"]["GapAnalysisResponse"];

export interface SuggestedPrompt {
  label: string;
  prompt: string;
}

const GENERIC_PROMPTS: SuggestedPrompt[] = [
  {
    label: "Plan my next quarter",
    prompt: "What should I focus on in my career over the next three months?",
  },
  {
    label: "Prepare for a review",
    prompt: "Help me prepare talking points for my next performance review.",
  },
  {
    label: "Strengthen my story",
    prompt: "How do I talk about my career so far in a way that's compelling to a hiring manager?",
  },
  {
    label: "Ask a good question",
    prompt: "What's one good question I should ask my manager in my next 1:1 to advance my career?",
  },
];

/**
 * Conversation starters woven from the person's actual profile data
 * (target roles, gap analysis, headline, skills) rather than the LLM's
 * own guesswork — the chat backend (career_coach_chat prompt, see
 * chat_service.py) only ever receives conversation history plus the
 * literal message text, so grounding happens here: the prompt text
 * itself carries the real role name / skill names into the request.
 * Falls back to GENERIC_PROMPTS to fill out to MAX_PROMPTS when the
 * profile doesn't have enough to draw from yet.
 */
const MAX_PROMPTS = 4;

export function buildSuggestedPrompts(
  profile: CareerProfile | undefined,
  targetRoles: TargetRole[] | undefined,
  gapAnalysis: GapAnalysisResponse | undefined,
): SuggestedPrompt[] {
  const personalized: SuggestedPrompt[] = [];

  const gapsByRole = new Map((gapAnalysis?.target_role_gaps ?? []).map((g) => [g.target_role_id, g]));

  for (const role of targetRoles ?? []) {
    const gap = gapsByRole.get(role.id);
    if (gap && gap.missing_skills.length > 0) {
      const skills = gap.missing_skills.slice(0, 5).join(", ");
      personalized.push({
        label: `Close gaps for ${role.role_name}`,
        prompt: `I'm targeting the ${role.role_name} role and I'm missing these skills: ${skills}. Help me build a plan to close these gaps.`,
      });
    } else {
      personalized.push({
        label: `Plan my path to ${role.role_name}`,
        prompt: `I'm targeting the ${role.role_name} role. Based on that, what should I be doing now to get there?`,
      });
    }
    if (personalized.length >= 2) break;
  }

  if (personalized.length < MAX_PROMPTS && profile?.headline) {
    personalized.push({
      label: "Improve my headline",
      prompt: `My current career profile headline is "${profile.headline}". How can I make it stronger?`,
    });
  }

  if (personalized.length < MAX_PROMPTS && (profile?.core_competencies?.length ?? 0) > 0) {
    const skills = (profile?.core_competencies ?? []).slice(0, 8).join(", ");
    personalized.push({
      label: "Where my skills fit",
      prompt: `Here are the skills I currently track: ${skills}. What career paths or roles fit this skill set well?`,
    });
  }

  const combined = [...personalized];
  for (const generic of GENERIC_PROMPTS) {
    if (combined.length >= MAX_PROMPTS) break;
    combined.push(generic);
  }

  return combined.slice(0, MAX_PROMPTS);
}
