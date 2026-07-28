import { apiClient } from "@/api/client";
import type { components } from "@/api/schema.gen";
import { useQuery } from "@tanstack/react-query";

type GapAnalysisResponse = components["schemas"]["GapAnalysisResponse"];

const KEYS = {
  gapAnalysis: ["skills", "gap-analysis"],
} as const;

export function useGapAnalysis() {
  return useQuery({
    queryKey: KEYS.gapAnalysis,
    queryFn: () => apiClient.get<GapAnalysisResponse>("/api/v1/skills/gap-analysis"),
  });
}
