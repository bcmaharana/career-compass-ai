import { apiClient } from "@/api/client";
import type { components } from "@/api/schema.gen";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

type JobApplicationRequest = components["schemas"]["JobApplicationRequest"];
type JobApplicationUpdateRequest = components["schemas"]["JobApplicationUpdateRequest"];
type JobApplicationResponse = components["schemas"]["JobApplicationResponse"];
type InterviewRoundRequest = components["schemas"]["InterviewRoundRequest"];
type JobApplicationSummaryResponse = components["schemas"]["JobApplicationSummaryResponse"];

const KEYS = {
  applications: ["job-applications"] as const,
  trackedProviderIds: ["job-applications", "tracked-provider-ids"] as const,
  summary: ["job-applications", "summary"] as const,
};

export function useJobApplications() {
  return useQuery({
    queryKey: KEYS.applications,
    queryFn: () => apiClient.get<JobApplicationResponse[]>("/api/v1/job-applications"),
  });
}

/** Backs the Job Listing page's per-row "Already tracking" badge. */
export function useTrackedProviderIds() {
  return useQuery({
    queryKey: KEYS.trackedProviderIds,
    queryFn: () => apiClient.get<string[]>("/api/v1/job-applications/tracked-provider-ids"),
  });
}

/** Backs the Dashboard's Job Applications card (status breakdown, next
 * interview, stuck-too-long nudge) — live-computed server-side. */
export function useJobApplicationsSummary() {
  return useQuery({
    queryKey: KEYS.summary,
    queryFn: () =>
      apiClient.get<JobApplicationSummaryResponse>("/api/v1/job-applications/summary"),
  });
}

function invalidateApplicationLists(queryClient: ReturnType<typeof useQueryClient>) {
  queryClient.invalidateQueries({ queryKey: KEYS.applications });
  queryClient.invalidateQueries({ queryKey: KEYS.trackedProviderIds });
  queryClient.invalidateQueries({ queryKey: KEYS.summary });
}

export function useCreateJobApplication() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: JobApplicationRequest) =>
      apiClient.post<JobApplicationResponse>("/api/v1/job-applications", body),
    onSuccess: () => invalidateApplicationLists(queryClient),
  });
}

export function useUpdateJobApplication() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, body }: { id: string; body: JobApplicationUpdateRequest }) =>
      apiClient.patch<JobApplicationResponse>(`/api/v1/job-applications/${id}`, body),
    onSuccess: () => invalidateApplicationLists(queryClient),
  });
}

export function useUnlinkJobApplicationSession() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) =>
      apiClient.post<JobApplicationResponse>(`/api/v1/job-applications/${id}/unlink-session`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: KEYS.applications }),
  });
}

export function useDeleteJobApplication() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => apiClient.delete<void>(`/api/v1/job-applications/${id}`),
    onSuccess: () => invalidateApplicationLists(queryClient),
  });
}

export function useCreateInterviewRound() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      applicationId,
      body,
    }: {
      applicationId: string;
      body: InterviewRoundRequest;
    }) =>
      apiClient.post(`/api/v1/job-applications/${applicationId}/interview-rounds`, body),
    onSuccess: () => invalidateApplicationLists(queryClient),
  });
}

export function useUpdateInterviewRound() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, body }: { id: string; body: InterviewRoundRequest }) =>
      apiClient.patch(`/api/v1/interview-rounds/${id}`, body),
    onSuccess: () => invalidateApplicationLists(queryClient),
  });
}

export function useDeleteInterviewRound() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => apiClient.delete<void>(`/api/v1/interview-rounds/${id}`),
    onSuccess: () => invalidateApplicationLists(queryClient),
  });
}

export function useMoveInterviewRound() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, direction }: { id: string; direction: "up" | "down" }) =>
      apiClient.post<void>(`/api/v1/interview-rounds/${id}/move`, { direction }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: KEYS.applications }),
  });
}
