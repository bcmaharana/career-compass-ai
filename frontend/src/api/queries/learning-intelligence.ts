import { apiClient } from "@/api/client";
import type { components } from "@/api/schema.gen";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

type LearningItemResponse = components["schemas"]["LearningItemResponse"];
type LearningItemRequest = components["schemas"]["LearningItemRequest"];
type LearningItemUpdateRequest = components["schemas"]["LearningItemUpdateRequest"];
type LearningRecommendationResponse = components["schemas"]["LearningRecommendationResponse"];

const KEYS = {
  items: ["learning", "items"],
  recommendations: (targetRoleId: string) => ["learning", "recommendations", targetRoleId],
} as const;

export function useLearningItems() {
  return useQuery({
    queryKey: KEYS.items,
    queryFn: () => apiClient.get<LearningItemResponse[]>("/api/v1/learning/items"),
  });
}

export function useAddLearningItem() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: LearningItemRequest) =>
      apiClient.post<LearningItemResponse>("/api/v1/learning/items", body),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: KEYS.items }),
  });
}

export function useUpdateLearningItem() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, body }: { id: string; body: LearningItemUpdateRequest }) =>
      apiClient.patch<LearningItemResponse>(`/api/v1/learning/items/${id}`, body),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: KEYS.items }),
  });
}

export function useDeleteLearningItem() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => apiClient.delete<void>(`/api/v1/learning/items/${id}`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: KEYS.items }),
  });
}

export function useMoveLearningItem() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, direction }: { id: string; direction: "up" | "down" }) =>
      apiClient.post<LearningItemResponse[]>(`/api/v1/learning/items/${id}/move`, { direction }),
    onSuccess: (data) => queryClient.setQueryData(KEYS.items, data),
  });
}

export function useLearningRecommendations(targetRoleId: string | null) {
  return useQuery({
    queryKey: targetRoleId
      ? KEYS.recommendations(targetRoleId)
      : ["learning", "recommendations", "none"],
    queryFn: () =>
      apiClient.get<LearningRecommendationResponse>(
        `/api/v1/learning/recommendations?target_role_id=${targetRoleId}`,
      ),
    enabled: targetRoleId !== null,
  });
}

export function useRegenerateLearningRecommendations() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (targetRoleId: string) =>
      apiClient.post<LearningRecommendationResponse>(
        `/api/v1/learning/recommendations/regenerate?target_role_id=${targetRoleId}`,
      ),
    onSuccess: (data, targetRoleId) =>
      queryClient.setQueryData(KEYS.recommendations(targetRoleId), data),
  });
}
