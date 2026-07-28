import { apiClient } from "@/api/client";
import { useQuery } from "@tanstack/react-query";
import type { components } from "@/api/schema.gen";

type HealthResponse = components["schemas"]["HealthResponse"];

/**
 * Example query hook, wired against the one real endpoint Phase 0 ships
 * (GET /api/v1/health). This is the pattern every future feature module's
 * queries should follow: one hook per operation, typed against the
 * generated schema, feature code never touches apiClient directly.
 */
export function useHealthCheck() {
  return useQuery({
    queryKey: ["health"],
    queryFn: () => apiClient.get<HealthResponse>("/api/v1/health"),
    staleTime: 30_000,
  });
}
