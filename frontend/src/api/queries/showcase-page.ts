import { apiClient } from "@/api/client";
import type { components } from "@/api/schema.gen";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

type ShowcasePageResponse = components["schemas"]["ShowcasePageResponse"];
type ShowcasePageUpdateRequest = components["schemas"]["ShowcasePageUpdateRequest"];
type TogglePublicRequest = components["schemas"]["TogglePublicRequest"];

const KEYS = {
  page: (targetRoleId: string) => ["showcase-page", targetRoleId] as const,
};

/** GET is itself a get-or-create on the backend (ShowcasePageService.get_or_create)
 * — the first fetch for a role seeds the page from that role's resume
 * data, every fetch after that returns the same, already-independent
 * row. `enabled` guards against firing before a real target role id is
 * known (this section only ever renders once one is), same convention
 * every other scope-dependent query hook in this app already follows. */
export function useShowcasePage(targetRoleId: string | null) {
  return useQuery({
    queryKey: KEYS.page(targetRoleId ?? ""),
    queryFn: () =>
      apiClient.get<ShowcasePageResponse>(`/api/v1/showcase-pages/${targetRoleId}`),
    enabled: !!targetRoleId,
  });
}

export function useUpdateShowcasePage(targetRoleId: string | null) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: ShowcasePageUpdateRequest) =>
      apiClient.patch<ShowcasePageResponse>(`/api/v1/showcase-pages/${targetRoleId}`, body),
    onSuccess: (data) => {
      if (targetRoleId) queryClient.setQueryData(KEYS.page(targetRoleId), data);
    },
  });
}

/** Turning ON invalidates the current-user query too — the first time
 * ANY resource is ever made public, the backend lazily assigns the
 * viewer a default handle, which the copy-link UI needs fresh, not
 * whatever was cached at login (same reasoning as
 * useToggleTopicPublic in api/queries/interview-prep.ts). */
export function useToggleShowcasePagePublic(targetRoleId: string | null) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: TogglePublicRequest) =>
      apiClient.post<ShowcasePageResponse>(
        `/api/v1/showcase-pages/${targetRoleId}/toggle-public`,
        body,
      ),
    onSuccess: (data, body) => {
      if (targetRoleId) queryClient.setQueryData(KEYS.page(targetRoleId), data);
      if (body.is_public) {
        queryClient.invalidateQueries({ queryKey: ["current-user"] });
      }
    },
  });
}

export function useUploadShowcaseColumnImage(targetRoleId: string | null) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ columnId, file }: { columnId: string; file: File }) =>
      apiClient.uploadFile<ShowcasePageResponse>(
        `/api/v1/showcase-pages/${targetRoleId}/columns/${columnId}/image`,
        file,
      ),
    onSuccess: (data) => {
      if (targetRoleId) queryClient.setQueryData(KEYS.page(targetRoleId), data);
    },
  });
}

export function useUploadShowcaseBackgroundImage(targetRoleId: string | null) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (file: File) =>
      apiClient.uploadFile<ShowcasePageResponse>(
        `/api/v1/showcase-pages/${targetRoleId}/background-image`,
        file,
      ),
    onSuccess: (data) => {
      if (targetRoleId) queryClient.setQueryData(KEYS.page(targetRoleId), data);
    },
  });
}

export function useRemoveShowcaseBackgroundImage(targetRoleId: string | null) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () =>
      apiClient.delete<ShowcasePageResponse>(
        `/api/v1/showcase-pages/${targetRoleId}/background-image`,
      ),
    onSuccess: (data) => {
      if (targetRoleId) queryClient.setQueryData(KEYS.page(targetRoleId), data);
    },
  });
}

export function useUploadShowcaseResume(targetRoleId: string | null) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (file: File) =>
      apiClient.uploadFile<ShowcasePageResponse>(
        `/api/v1/showcase-pages/${targetRoleId}/resume`,
        file,
      ),
    onSuccess: (data) => {
      if (targetRoleId) queryClient.setQueryData(KEYS.page(targetRoleId), data);
    },
  });
}

export function useRemoveShowcaseResume(targetRoleId: string | null) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () =>
      apiClient.delete<ShowcasePageResponse>(`/api/v1/showcase-pages/${targetRoleId}/resume`),
    onSuccess: (data) => {
      if (targetRoleId) queryClient.setQueryData(KEYS.page(targetRoleId), data);
    },
  });
}
