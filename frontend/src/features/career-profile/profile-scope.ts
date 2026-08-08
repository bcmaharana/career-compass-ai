import { createContext, useContext } from "react";

/**
 * The single "which profile am I looking at" axis for the Career Profile
 * page — null means the Master Profile, a real id means that Target Role
 * Profile (a fully independent set of Experience/Education/etc., not a
 * filtered view of Master). See ProfileScopeContext.tsx for the provider
 * (split into its own file so this one stays hook/context-only — mixing
 * component and non-component exports in one file breaks Fast Refresh).
 */
export const ProfileScopeContext = createContext<string | null>(null);

export function useProfileScope(): string | null {
  return useContext(ProfileScopeContext);
}
