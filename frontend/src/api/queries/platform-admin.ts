import { apiClient } from "@/api/client";
import type { components } from "@/api/schema.gen";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

type MyPlatformAdminResponse = components["schemas"]["MyPlatformAdminResponse"];
type PlatformSettingResponse = components["schemas"]["PlatformSettingResponse"];
type UpdatePlatformSettingRequest = components["schemas"]["UpdatePlatformSettingRequest"];
type PlatformAdminGrantResponse = components["schemas"]["PlatformAdminGrantResponse"];
type GrantPlatformAdminRequest = components["schemas"]["GrantPlatformAdminRequest"];
type UpdatePlatformAdminRequest = components["schemas"]["UpdatePlatformAdminRequest"];

const MY_GRANT_QUERY_KEY = ["platform-admin-me"];
const SETTINGS_QUERY_KEY = ["platform-admin-settings"];
const ADMINS_QUERY_KEY = ["platform-admin-admins"];

/**
 * The caller's own platform-admin grant, if any — empty permission_codes
 * for anyone who isn't a platform admin at all. Used both to gate the
 * Settings sub-nav entry (AccountPanelContent.tsx) and to gate this
 * page's own content — a 403 from the write endpoints is the real
 * enforcement either way, this is purely a "don't show a page that will
 * just 403" UX nicety.
 */
export function usePlatformAdminMe() {
  return useQuery({
    queryKey: MY_GRANT_QUERY_KEY,
    queryFn: () => apiClient.get<MyPlatformAdminResponse>("/api/v1/platform-admin/me"),
  });
}

export function usePlatformSettings(enabled: boolean) {
  return useQuery({
    queryKey: SETTINGS_QUERY_KEY,
    queryFn: () => apiClient.get<PlatformSettingResponse[]>("/api/v1/platform-admin/settings"),
    enabled,
  });
}

export function useUpdatePlatformSetting() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ key, body }: { key: string; body: UpdatePlatformSettingRequest }) =>
      apiClient.patch<PlatformSettingResponse>(
        `/api/v1/platform-admin/settings/${encodeURIComponent(key)}`,
        body,
      ),
    onSuccess: (updated) => {
      queryClient.setQueryData<PlatformSettingResponse[]>(SETTINGS_QUERY_KEY, (current) =>
        current?.map((s) => (s.key === updated.key ? updated : s)),
      );
    },
  });
}

export function usePlatformAdmins(enabled: boolean) {
  return useQuery({
    queryKey: ADMINS_QUERY_KEY,
    queryFn: () => apiClient.get<PlatformAdminGrantResponse[]>("/api/v1/platform-admin/admins"),
    enabled,
  });
}

export function useGrantPlatformAdmin() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (body: GrantPlatformAdminRequest) =>
      apiClient.post<PlatformAdminGrantResponse>("/api/v1/platform-admin/admins", body),
    onSuccess: (grant) => {
      queryClient.setQueryData<PlatformAdminGrantResponse[]>(ADMINS_QUERY_KEY, (current) => {
        if (!current) return [grant];
        const withoutExisting = current.filter((g) => g.id !== grant.id);
        return [...withoutExisting, grant];
      });
    },
  });
}

export function useUpdatePlatformAdmin() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, body }: { id: string; body: UpdatePlatformAdminRequest }) =>
      apiClient.patch<PlatformAdminGrantResponse>(`/api/v1/platform-admin/admins/${id}`, body),
    onSuccess: (updated) => {
      queryClient.setQueryData<PlatformAdminGrantResponse[]>(ADMINS_QUERY_KEY, (current) =>
        current?.map((g) => (g.id === updated.id ? updated : g)),
      );
    },
  });
}

export function useRevokePlatformAdmin() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: string) => apiClient.delete<void>(`/api/v1/platform-admin/admins/${id}`),
    onSuccess: (_, id) => {
      queryClient.setQueryData<PlatformAdminGrantResponse[]>(ADMINS_QUERY_KEY, (current) =>
        current?.filter((g) => g.id !== id),
      );
    },
  });
}
