import { apiClient } from "@/api/client";
import type { components } from "@/api/schema.gen";
import { useAuthStore } from "@/stores/auth-store";
import type { AuthenticatedUser } from "@/stores/auth-store";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

type LoginRequest = components["schemas"]["LoginRequest"];
type PhoneLoginRequest = components["schemas"]["PhoneLoginRequest"];
type LoginResponse = components["schemas"]["LoginResponse"];
type CurrentUserResponse = components["schemas"]["CurrentUserResponse"];
type UpdateCurrentUserRequest = components["schemas"]["UpdateCurrentUserRequest"];
type RequestPasswordResetRequest = components["schemas"]["RequestPasswordResetRequest"];
type RequestPasswordResetResponse = components["schemas"]["RequestPasswordResetResponse"];
type ResetPasswordRequest = components["schemas"]["ResetPasswordRequest"];
type ResetPasswordResponse = components["schemas"]["ResetPasswordResponse"];
type PersonalSignupRequest = components["schemas"]["PersonalSignupRequest"];
type OrganizationSignupRequest = components["schemas"]["OrganizationSignupRequest"];
type SignupRequestResponse = components["schemas"]["SignupRequestResponse"];
type VerifySignupRequest = components["schemas"]["VerifySignupRequest"];

function toAuthenticatedUser(data: LoginResponse): AuthenticatedUser {
  return {
    id: data.user_id,
    email: data.email,
    fullName: data.full_name,
    firstName: data.first_name,
    lastName: data.last_name,
    salutation: data.salutation,
    tenantId: data.tenant_id,
    lastLoginAt: data.last_login_at,
  };
}

/**
 * Login mutation. On success, stores the token and user summary in the
 * auth store — every other authenticated request then picks up the
 * token automatically via apiClient's Authorization header injection
 * (see api/client.ts).
 */
export function useLogin() {
  const setSession = useAuthStore((state) => state.setSession);

  return useMutation({
    mutationFn: (credentials: LoginRequest) =>
      apiClient.post<LoginResponse>("/api/v1/identity/login", credentials),
    onSuccess: (data) => setSession(data.access_token, toAuthenticatedUser(data)),
  });
}

/**
 * Phone login's second step — the frontend has already completed the
 * actual OTP exchange with Firebase directly (see
 * PhoneLoginForm.tsx/lib/firebase.ts) by this point; this just hands the
 * resulting Firebase ID token to the backend, which verifies it and
 * returns the exact same LoginResponse shape useLogin does, so session
 * handling afterward is identical either way.
 */
export function usePhoneLogin() {
  const setSession = useAuthStore((state) => state.setSession);

  return useMutation({
    mutationFn: (body: PhoneLoginRequest) =>
      apiClient.post<LoginResponse>("/api/v1/identity/login/phone", body),
    onSuccess: (data) => setSession(data.access_token, toAuthenticatedUser(data)),
  });
}

/**
 * "Forgot password" request — always resolves successfully regardless
 * of whether the subdomain/email combination is real (see
 * RequestPasswordResetService's docstring on the backend); the page
 * component must not infer anything from the response beyond
 * "the request completed," never from its content.
 */
export function useRequestPasswordReset() {
  return useMutation({
    mutationFn: (body: RequestPasswordResetRequest) =>
      apiClient.post<RequestPasswordResetResponse>(
        "/api/v1/identity/password-reset/request",
        body,
      ),
  });
}

/**
 * Confirms a password reset using the token from the emailed link.
 * Unlike the request step above, this can genuinely fail (invalid,
 * expired, or already-used token) — the page component surfaces
 * `.error` the same way LoginPage does.
 */
export function useResetPassword() {
  return useMutation({
    mutationFn: (body: ResetPasswordRequest) =>
      apiClient.post<ResetPasswordResponse>("/api/v1/identity/password-reset/confirm", body),
  });
}

/**
 * Personal (individual, no-organization) signup — request step only.
 * Nothing is created yet: this just triggers a verification email.
 * The account only actually exists once useVerifySignup() confirms the
 * emailed link, which is also what logs the person in — there's no
 * separate login step after signup completes.
 */
export function useRequestPersonalSignup() {
  return useMutation({
    mutationFn: (body: PersonalSignupRequest) =>
      apiClient.post<SignupRequestResponse>("/api/v1/identity/signup/personal", body),
  });
}

/**
 * Enterprise (organization) signup — request step, same two-phase
 * shape as useRequestPersonalSignup, just with the user-chosen
 * tenant_name/subdomain/organization_name carried through.
 */
export function useRequestOrganizationSignup() {
  return useMutation({
    mutationFn: (body: OrganizationSignupRequest) =>
      apiClient.post<SignupRequestResponse>("/api/v1/identity/signup/organization", body),
  });
}

/**
 * Confirms a signup using the token from the emailed verification
 * link — this is what actually creates the Tenant/Organization/User
 * for the first time, and immediately logs the person in (the response
 * is a real LoginResponse), so VerifyEmailPage never needs a separate
 * useLogin() call after this succeeds.
 */
export function useVerifySignup() {
  const setSession = useAuthStore((state) => state.setSession);

  return useMutation({
    mutationFn: (body: VerifySignupRequest) =>
      apiClient.post<LoginResponse>("/api/v1/identity/signup/verify", body),
    onSuccess: (data) => setSession(data.access_token, toAuthenticatedUser(data)),
  });
}

/**
 * Fetches the authenticated user's profile from the backend. Useful for
 * validating a stored token is still good (e.g. on app load) and for
 * displaying the current user's info in the app shell.
 */
export function useCurrentUser() {
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);

  return useQuery({
    queryKey: ["current-user"],
    queryFn: () => apiClient.get<CurrentUserResponse>("/api/v1/identity/me"),
    enabled: isAuthenticated,
    retry: false,
  });
}

/**
 * Settings > Profile save. Writes the confirmed server response into
 * both the query cache (so a re-visit of the page shows it instantly)
 * and the auth store's user summary (so the Right Nav's greeting, which
 * reads from the store directly rather than this query, updates without
 * needing a fresh login) — same "write confirmed response, don't just
 * invalidate" convention every other mutation in this app follows.
 */
export function useUpdateCurrentUser() {
  const queryClient = useQueryClient();
  const updateUserProfile = useAuthStore((state) => state.updateUserProfile);

  return useMutation({
    mutationFn: (body: UpdateCurrentUserRequest) =>
      apiClient.patch<CurrentUserResponse>("/api/v1/identity/me", body),
    onSuccess: (data) => {
      queryClient.setQueryData(["current-user"], data);
      updateUserProfile({
        fullName: data.full_name,
        firstName: data.first_name,
        lastName: data.last_name,
        salutation: data.salutation,
      });
    },
  });
}

/**
 * Real, permanent "delete my account" — the whole tenant is gone after
 * this succeeds, not just this user's own data (see
 * DeleteAccountService's docstring on the backend for why "delete my
 * account" and "delete my tenant" are the same operation in this app
 * today). Deliberately does not clear the session itself — the caller
 * (SettingsAccountPage) does that explicitly after a successful delete,
 * same as AppShell's own sign-out handler, so both flows clear session
 * state the same way rather than this hook reaching into the store on
 * every caller's behalf.
 */
export function useDeleteAccount() {
  return useMutation({
    mutationFn: () => apiClient.delete<void>("/api/v1/identity/me"),
  });
}
