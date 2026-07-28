import { create } from "zustand";

/**
 * Authentication placeholder store.
 *
 * Holds client-side session state only (access token, current user
 * summary). Deliberately a thin Zustand store, not a data-fetching layer
 * — actual login/logout calls belong in api/queries/auth.ts once Phase 1
 * ships the backend's InternalJWTProvider endpoints. Isolating token
 * storage here (rather than scattering it across feature modules) is
 * what lets a future SSO/OIDC switch touch one file instead of every
 * feature (see docs/adr/ADR-003-authentication-strategy.md).
 *
 * Token is kept in memory only, not localStorage — refresh-on-reload will
 * be handled by a silent-refresh call against the backend once Phase 1's
 * refresh-token endpoint exists, not by persisting the access token
 * client-side.
 */

export interface AuthenticatedUser {
  id: string;
  email: string;
  fullName: string;
  firstName: string;
  lastName: string;
  salutation: string | null;
  tenantId: string;
  /** The user's *previous* login time (ISO 8601) — null on a first-ever
   * login. Captured once at login and never refreshed mid-session (see
   * useLogin), so "Last logged in" stays a stable "before this session"
   * value rather than drifting to "now" partway through. */
  lastLoginAt: string | null;
}

interface AuthState {
  accessToken: string | null;
  user: AuthenticatedUser | null;
  isAuthenticated: boolean;
  setSession: (accessToken: string, user: AuthenticatedUser) => void;
  updateAccessToken: (accessToken: string) => void;
  updateUserProfile: (
    fields: Pick<AuthenticatedUser, "fullName" | "firstName" | "lastName" | "salutation">,
  ) => void;
  clearSession: () => void;
}

export const useAuthStore = create<AuthState>((set) => ({
  accessToken: null,
  user: null,
  isAuthenticated: false,
  setSession: (accessToken, user) => set({ accessToken, user, isAuthenticated: true }),
  // Used for the sliding-session refresh (see api/client.ts) — swaps in
  // a freshly-issued token without touching `user`, since a refresh
  // doesn't change who's logged in, just how much longer they stay so.
  updateAccessToken: (accessToken) => set({ accessToken }),
  // Used after a Settings > Profile save, so the Right Nav's greeting
  // reflects the new name immediately — no re-login required. Doesn't
  // touch accessToken/isAuthenticated, only the display fields.
  updateUserProfile: (fields) =>
    set((state) => (state.user ? { user: { ...state.user, ...fields } } : state)),
  clearSession: () => set({ accessToken: null, user: null, isAuthenticated: false }),
}));
