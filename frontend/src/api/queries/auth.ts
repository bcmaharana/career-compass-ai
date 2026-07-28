import { apiClient } from "@/api/client";
import type { components } from "@/api/schema.gen";
import { useAuthStore } from "@/stores/auth-store";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

type LoginRequest = components["schemas"]["LoginRequest"];
type LoginResponse = components["schemas"]["LoginResponse"];
type CurrentUserResponse = components["schemas"]["CurrentUserResponse"];
type UpdateCurrentUserRequest = components["schemas"]["UpdateCurrentUserRequest"];

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
    onSuccess: (data) => {
      setSession(data.access_token, {
        id: data.user_id,
        email: data.email,
        fullName: data.full_name,
        firstName: data.first_name,
        lastName: data.last_name,
        salutation: data.salutation,
        tenantId: data.tenant_id,
        lastLoginAt: data.last_login_at,
      });
    },
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
