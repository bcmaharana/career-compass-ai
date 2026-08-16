import { apiClient } from "@/api/client";
import type { components } from "@/api/schema.gen";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

type JobListingsResponse = components["schemas"]["JobListingsResponse"];
type CareerPathResponse = components["schemas"]["CareerPathResponse"];
type JobSearchPreferenceResponse = components["schemas"]["JobSearchPreferenceResponse"];
type JobSearchPreferenceRequest = components["schemas"]["JobSearchPreferenceRequest"];

const KEYS = {
  jobs: (targetRoleId: string) => ["opportunities", "jobs", targetRoleId],
  careerPath: (targetRoleId: string) => ["opportunities", "career-path", targetRoleId],
  jobSearchPreference: ["opportunities", "job-search-preference"],
} as const;

export function useJobListings(targetRoleId: string | null) {
  return useQuery({
    queryKey: targetRoleId ? KEYS.jobs(targetRoleId) : ["opportunities", "jobs", "none"],
    queryFn: () =>
      apiClient.get<JobListingsResponse>(
        `/api/v1/opportunities/jobs?target_role_id=${targetRoleId}`,
      ),
    enabled: targetRoleId !== null,
  });
}

export function useCareerPath(targetRoleId: string | null) {
  return useQuery({
    queryKey: targetRoleId ? KEYS.careerPath(targetRoleId) : ["opportunities", "career-path", "none"],
    queryFn: () =>
      apiClient.get<CareerPathResponse>(
        `/api/v1/opportunities/career-path?target_role_id=${targetRoleId}`,
      ),
    enabled: targetRoleId !== null,
  });
}

export function useJobSearchPreference() {
  return useQuery({
    queryKey: KEYS.jobSearchPreference,
    queryFn: () =>
      apiClient.get<JobSearchPreferenceResponse>("/api/v1/opportunities/job-search-preference"),
  });
}

export function useUpdateJobSearchPreference() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: JobSearchPreferenceRequest) =>
      apiClient.patch<JobSearchPreferenceResponse>(
        "/api/v1/opportunities/job-search-preference",
        body,
      ),
    onSuccess: (data) => {
      queryClient.setQueryData(KEYS.jobSearchPreference, data);
      // A saved preference changes what get_for_target_role resolves as
      // the search location/filters — invalidate every cached job-listing
      // result so the next visit to the Opportunity Intelligence page
      // refetches under the new preference instead of showing stale
      // results silently.
      queryClient.invalidateQueries({ queryKey: ["opportunities", "jobs"] });
    },
  });
}
