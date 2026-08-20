import { create } from "zustand";

const STORAGE_KEY = "career-compass-active-target-role";

/** "master" is a real stored value (not just an absent key) so a
 * returning visit can tell "Master was chosen, deliberately" apart from
 * "nothing has ever been picked yet" — both currently behave the same
 * (activeTargetRoleId is null either way), but only the former should
 * ever *win* over some other page's own default (e.g. Opportunity
 * Intelligence/Learning Intelligence fall back to the user's first
 * target role when there's no stored preference at all, but should
 * respect an explicit "Master" choice by not doing that). */
function readStoredTargetRoleId(): string | null {
  if (typeof window === "undefined") return null;
  const saved = window.localStorage.getItem(STORAGE_KEY);
  return saved && saved !== "master" ? saved : null;
}

interface TargetRoleScopeState {
  activeTargetRoleId: string | null;
  /** Whether a preference has ever been explicitly recorded (Master or
   * a real role) — see readStoredTargetRoleId's docstring. */
  hasStoredPreference: boolean;
  setActiveTargetRoleId: (targetRoleId: string | null) => void;
}

/**
 * The Target Role currently "in focus" app-wide — set whenever the
 * person picks a role (or Master) from any role-aware page's own scope
 * control (Career Profile's Target Roles widget, or the "Current
 * Scope"/"Target role" selector on Interview Prep, Resume Intelligence,
 * Opportunity Intelligence, or Learning Intelligence). Read by AI
 * Career Coach (which has no selector of its own) to ground its
 * "profile at a glance" card and suggested prompts, and used as the
 * *default* scope on every other role-aware page's own bare landing —
 * still overridable per-page (Career Profile/Interview Prep/Resume
 * Intelligence keep their own `?role=` URL param, so a bookmark/shared
 * link still wins over this stored default).
 *
 * Persisted to ONE shared localStorage key rather than a key per page
 * (the previous per-page approach — see git history on
 * InterviewPrepPage.tsx/ResumeIntelligencePage.tsx) specifically so
 * "which role I was last working in" genuinely follows the person
 * across the whole app, not just within whichever single page they set
 * it on — direct 2026-08-20 request: picking a role on Career Profile
 * should carry into AI Career Coach, Resume Intelligence, Opportunity
 * Intelligence, Learning Intelligence, and Interview Prep alike, and
 * picking a *different* role on any of those pages should update the
 * shared default the same way.
 */
export const useTargetRoleScopeStore = create<TargetRoleScopeState>((set) => ({
  activeTargetRoleId: readStoredTargetRoleId(),
  hasStoredPreference:
    typeof window !== "undefined" && window.localStorage.getItem(STORAGE_KEY) !== null,
  setActiveTargetRoleId: (targetRoleId) => {
    window.localStorage.setItem(STORAGE_KEY, targetRoleId ?? "master");
    set({ activeTargetRoleId: targetRoleId, hasStoredPreference: true });
  },
}));

/**
 * Guards against the shared scope pointing at a Target Role that no
 * longer exists (deleted from another page/session since it was last
 * stored) — every consumer should resolve through this rather than
 * trusting `activeTargetRoleId` directly, so a stale id quietly falls
 * back to Master instead of driving a broken fetch.
 */
export function resolveValidTargetRoleId(
  targetRoleId: string | null,
  targetRoles: { id: string }[] | undefined,
): string | null {
  if (!targetRoleId) return null;
  return targetRoles?.some((role) => role.id === targetRoleId) ? targetRoleId : null;
}
