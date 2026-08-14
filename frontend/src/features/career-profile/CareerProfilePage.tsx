import {
  useCareerProfile,
  useClearCareerProfile,
  useTargetRoles,
  useUpdateCareerProfile,
} from "@/api/queries/career-profile";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
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
import { ProfileScopeProvider } from "@/features/career-profile/ProfileScopeContext";
import { ResumeDownloadBar } from "@/features/career-profile/ResumeDownloadBar";
import { Eraser } from "lucide-react";
import { useMemo, useState } from "react";
import type { ComponentType } from "react";
import { useSearchParams } from "react-router-dom";
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
  const [searchParams] = useSearchParams();
  const targetRoleId = searchParams.get("role");
  // Fed into every scope-dependent section's `key` below — see that
  // Component's key comment for why.
  const scopeKey = targetRoleId ?? "master";
  const { data: targetRoles } = useTargetRoles();
  const activeRole = targetRoleId ? targetRoles?.find((r) => r.id === targetRoleId) : null;

  const { data: profile } = useCareerProfile(targetRoleId);
  const updateProfile = useUpdateCareerProfile(targetRoleId);
  const clearProfile = useClearCareerProfile(targetRoleId);
  const [clearProfileOpen, setClearProfileOpen] = useState(false);

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

  // Same "always resend headline/summary" requirement as moveSection
  // above — the backend overwrites both unconditionally on every PATCH
  // (see CareerProfileService.update).
  function toggleSectionResume(key: string, checked: boolean) {
    if (!profile) return;
    updateProfile.mutate({
      headline: profile.headline,
      summary: profile.summary,
      core_competencies: profile.core_competencies,
      resume_section_toggles: { ...(profile.resume_section_toggles ?? {}), [key]: checked },
    });
  }

  return (
    <ProfileScopeProvider targetRoleId={targetRoleId}>
      <div className="-mt-6 grid gap-3">
        <div className="-mb-3 flex flex-col items-start gap-2 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-center gap-2">
            <span className="text-base font-semibold text-foreground md:text-lg">
              Career Profile:{" "}
              <span className="bg-[linear-gradient(90deg,#a855f7_12.5%,#3b82f6_37.5%,#22c55e_58.33%,#fdba74_75%,#fca5a5_91.67%)] bg-clip-text text-transparent">
                {activeRole ? activeRole.role_name : "Master"}
              </span>
            </span>
            {activeRole && <Badge variant="accent">{activeRole.tag}</Badge>}
          </div>
          <Button
            variant="ghost"
            size="sm"
            className="text-destructive hover:text-destructive"
            onClick={() => setClearProfileOpen(true)}
          >
            <Eraser className="h-4 w-4" />
            {activeRole ? "Clear This Target Role Profile" : "Clear Career Profile"}
          </Button>
        </div>
        {profile && (
          <ResumeDownloadBar key={`${scopeKey}-resume-download`} profile={profile} scope={targetRoleId} />
        )}
        <ProfileHeader key={`${scopeKey}-header`} />
        <ExecutiveSummarySection key={`${scopeKey}-summary`} />
        {orderedKeys.map((key, index) => {
          const def = SECTION_DEFS.find((s) => s.key === key);
          if (!def) return null;
          const { Component } = def;
          return (
            <Component
              // Scoped into the key, not just the section key, so
              // switching between the Master Profile and a Target Role
              // Profile fully remounts every section instead of leaving
              // in-progress local UI state (edit mode, open dialogs,
              // delete/clear confirmations) from the profile you just
              // left silently applied to the one you switched to — a
              // real bug reported live: leaving Core Competencies in
              // edit mode on a Target Role Profile and switching to
              // Master showed Master's Core Competencies already in
              // edit mode too, since nothing keyed these components by
              // scope before now. Same "key change unmounts/remounts
              // instead of clobbering state" pattern already used by
              // Resume Intelligence's review screen (key={resume.id}).
              key={`${scopeKey}-${key}`}
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
              resumeIncluded={profile?.resume_section_toggles?.[key] ?? true}
              onToggleResumeIncluded={(checked) => toggleSectionResume(key, checked)}
              resumeToggleDisabled={updateProfile.isPending}
            />
          );
        })}

        <ConfirmDialog
          open={clearProfileOpen}
          onCancel={() => setClearProfileOpen(false)}
          onConfirm={() => {
            clearProfile.mutate();
            setClearProfileOpen(false);
          }}
          title={
            activeRole
              ? `Clear the ${activeRole.role_name} Target Role Profile?`
              : "Clear your entire Career Profile?"
          }
          description={
            activeRole
              ? "This removes headline, summary, core competencies, and every experience, education, certification, career highlight, and key achievement entry on this Target Role Profile only — your Master Profile, career goals, and recommendations are untouched. This can't be undone."
              : "This removes your headline, summary, core competencies, and every entry in every section below — experience, education, certifications, career highlights, key achievements, career goals, and recommendations. Your profile photo is kept — delete it separately from the photo itself if you want it gone too. This can't be undone."
          }
          isPending={clearProfile.isPending}
          confirmLabel="Clear everything"
          confirmPendingLabel="Clearing..."
        />
      </div>
    </ProfileScopeProvider>
  );
}
