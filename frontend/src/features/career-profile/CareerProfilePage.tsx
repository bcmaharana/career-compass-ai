import { useCareerProfile, useUpdateCareerProfile } from "@/api/queries/career-profile";
import { CareerGoalsSection } from "@/features/career-profile/CareerGoalsSection";
import { CareerHighlightsSection } from "@/features/career-profile/CareerHighlightsSection";
import { CertificationSection } from "@/features/career-profile/CertificationSection";
import { CoreCompetenciesSection } from "@/features/career-profile/CoreCompetenciesSection";
import { EducationSection } from "@/features/career-profile/EducationSection";
import { ExecutiveSummarySection } from "@/features/career-profile/ExecutiveSummarySection";
import { ExperienceSection } from "@/features/career-profile/ExperienceSection";
import { KeyAchievementsSection } from "@/features/career-profile/KeyAchievementsSection";
import { PeerEndorsementsSection } from "@/features/career-profile/PeerEndorsementsSection";
import { ProfileHeader } from "@/features/career-profile/ProfileHeader";
import { useMemo } from "react";
import type { ComponentType } from "react";
import type { SectionOrderProps } from "@/features/career-profile/section-order";

/**
 * Every section below Profile Header and Executive Summary is
 * user-reorderable (brief follow-up request) — those two always stay
 * first/second (Profile Header is the page-level sticky strip, Part
 * 2.4) and aren't part of this list. `key` is the persisted identifier
 * stored in `profile.section_order`; changing a component's position
 * here changes only the *default* order for profiles that haven't been
 * reordered yet, not the key, so a stored order stays valid even if
 * this list is reshuffled later.
 */
const SECTION_DEFS: { key: string; Component: ComponentType<SectionOrderProps> }[] = [
  { key: "core_competencies", Component: CoreCompetenciesSection },
  { key: "career_highlights", Component: CareerHighlightsSection },
  { key: "experience", Component: ExperienceSection },
  { key: "education", Component: EducationSection },
  { key: "certifications", Component: CertificationSection },
  { key: "key_achievements", Component: KeyAchievementsSection },
  { key: "career_goals", Component: CareerGoalsSection },
  { key: "recommendations", Component: PeerEndorsementsSection },
];

const DEFAULT_ORDER = SECTION_DEFS.map((s) => s.key);

/**
 * Merges a saved order with the current default: keeps the saved
 * relative order for keys that still exist, drops any stale/unknown
 * keys (e.g. from a future rename), and appends any default keys the
 * saved order doesn't have yet (e.g. a section added after the user
 * last reordered) — so neither a schema change nor a new section can
 * make a section silently vanish from the page.
 */
function resolveOrder(saved: string[] | null | undefined): string[] {
  if (!saved || saved.length === 0) return DEFAULT_ORDER;
  const known = saved.filter((key) => DEFAULT_ORDER.includes(key));
  const missing = DEFAULT_ORDER.filter((key) => !known.includes(key));
  return [...known, ...missing];
}

/**
 * Section order follows a resume-like flow by default: identity/summary
 * first, then experience-adjacent proof points (highlights, then the
 * full experience history), education and certifications, then forward
 * -looking (goals) and third-party validation (recommendations) last —
 * see resolveOrder above for how a user's saved reorder overrides this.
 * "Technical Skills" is deliberately not here — see Phase 3, Skill
 * Intelligence, which owns a real skill taxonomy rather than a plain
 * text list on this page.
 */
export function CareerProfilePage() {
  const { data: profile } = useCareerProfile();
  const updateProfile = useUpdateCareerProfile();

  const orderedKeys = useMemo(() => resolveOrder(profile?.section_order), [profile?.section_order]);

  function moveSection(key: string, direction: "up" | "down") {
    if (!profile) return;
    const index = orderedKeys.indexOf(key);
    const targetIndex = direction === "up" ? index - 1 : index + 1;
    if (targetIndex < 0 || targetIndex >= orderedKeys.length) return;

    const nextOrder = [...orderedKeys];
    [nextOrder[index], nextOrder[targetIndex]] = [nextOrder[targetIndex]!, nextOrder[index]!];

    // headline/summary/core_competencies are resent unchanged — the
    // backend overwrites headline/summary unconditionally on every call
    // (see CareerProfileService.update), so this must always include
    // their current values, the same pattern CoreCompetenciesSection
    // uses for its own saves.
    updateProfile.mutate({
      headline: profile.headline,
      summary: profile.summary,
      core_competencies: profile.core_competencies,
      section_order: nextOrder,
    });
  }

  return (
    <div className="-mt-8 grid gap-3">
      <ProfileHeader />
      <ExecutiveSummarySection />
      {orderedKeys.map((key, index) => {
        const def = SECTION_DEFS.find((s) => s.key === key);
        if (!def) return null;
        const { Component } = def;
        return (
          <Component
            key={key}
            onMoveUp={() => moveSection(key, "up")}
            onMoveDown={() => moveSection(key, "down")}
            isFirst={index === 0}
            isLast={index === orderedKeys.length - 1}
            moveDisabled={updateProfile.isPending}
            // ProfileHeader (white) then ExecutiveSummarySection
            // (tinted) come before this list, so the first reorderable
            // section alternates starting back at white, then tinted,
            // etc.
            cardBackground={index % 2 === 0 ? "card" : "background"}
          />
        );
      })}
    </div>
  );
}
