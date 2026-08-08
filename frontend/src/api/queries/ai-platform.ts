import { apiClient } from "@/api/client";
import type { components } from "@/api/schema.gen";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

type ModelSelectionResponse = components["schemas"]["ModelSelectionResponse"];
type SetModelPreferenceRequest = components["schemas"]["SetModelPreferenceRequest"];

const MODEL_SELECTION_QUERY_KEY = ["ai-model-selection"];

/**
 * The catalog of selectable AI models plus which one is currently in
 * effect for this user (their own override, or the platform default).
 */
export function useModelSelection() {
  return useQuery({
    queryKey: MODEL_SELECTION_QUERY_KEY,
    queryFn: () => apiClient.get<ModelSelectionResponse>("/api/v1/ai-platform/models"),
  });
}

/**
 * Settings > AI Model save. Writes the confirmed server response
 * straight into the query cache rather than invalidating — same
 * convention as every other mutation in this app (see
 * useUpdateCurrentUser), so there's no stale-data window on save.
 */
export function useSetModelPreference() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (body: SetModelPreferenceRequest) =>
      apiClient.patch<ModelSelectionResponse>("/api/v1/ai-platform/model-preference", body),
    onSuccess: (data) => {
      queryClient.setQueryData(MODEL_SELECTION_QUERY_KEY, data);
    },
  });
}
