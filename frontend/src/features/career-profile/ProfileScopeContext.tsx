import { ProfileScopeContext } from "@/features/career-profile/profile-scope";
import type { ReactNode } from "react";

/**
 * Sourced from the `?role=` URL search param (see CareerProfilePage.tsx)
 * rather than component state, so the current scope is shareable/
 * bookmarkable and survives a page refresh — the same reasoning this
 * app's Settings sub-nav already uses real routes instead of in-page tab
 * state.
 *
 * Every section component below Profile Header reads its scope via
 * `useProfileScope()` (profile-scope.ts) rather than receiving it as a
 * prop, since sections already call their own data hooks directly with
 * no prop-drilling today (see CareerProfilePage.tsx's SECTION_DEFS loop)
 * — threading a new prop through every section's own signature would be
 * a much larger, more error-prone change than one context read per
 * section.
 */
export function ProfileScopeProvider({
  targetRoleId,
  children,
}: {
  targetRoleId: string | null;
  children: ReactNode;
}) {
  return (
    <ProfileScopeContext.Provider value={targetRoleId}>{children}</ProfileScopeContext.Provider>
  );
}
