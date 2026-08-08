import { apiClient } from "@/api/client";
import type { components } from "@/api/schema.gen";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

type ResumeResponse = components["schemas"]["ResumeResponse"];
type ResumeSummary = components["schemas"]["ResumeSummary"];
type ResumeMergeRequest = components["schemas"]["ResumeMergeRequest"];
type ResumeMergeResponse = components["schemas"]["ResumeMergeResponse"];

const KEYS = {
  list: ["resume-intelligence", "list"],
  detail: (id: string) => ["resume-intelligence", "detail", id],
} as const;

/** A real upload history now — every resume stays listed until
 * explicitly deleted, since a person may keep multiple versions, each
 * tailored to a different target role. */
export function useResumeList() {
  return useQuery({
    queryKey: KEYS.list,
    queryFn: () => apiClient.get<ResumeSummary[]>("/api/v1/resume-intelligence"),
  });
}

export function useResume(resumeId: string | null) {
  return useQuery({
    queryKey: resumeId ? KEYS.detail(resumeId) : ["resume-intelligence", "detail", "none"],
    queryFn: () => apiClient.get<ResumeResponse>(`/api/v1/resume-intelligence/${resumeId}`),
    enabled: resumeId !== null,
  });
}

export function useUploadResume() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      file,
      targetRoleId,
      signal,
    }: {
      file: File;
      targetRoleId: string | null;
      signal?: AbortSignal;
    }) =>
      apiClient.uploadFile<ResumeResponse>(
        "/api/v1/resume-intelligence/upload",
        file,
        "file",
        targetRoleId ? { target_role_id: targetRoleId } : undefined,
        signal,
      ),
    onSuccess: (data) => {
      queryClient.setQueryData(KEYS.detail(data.id), data);
      queryClient.invalidateQueries({ queryKey: KEYS.list });
    },
  });
}

export function useMergeResume() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: ResumeMergeRequest) =>
      apiClient.post<ResumeMergeResponse>("/api/v1/resume-intelligence/merge", body),
    // A merge only ever adds to Career Profile data, never edits the
    // resume draft itself — invalidate every career-profile query key a
    // merge can touch, plus Gap Analysis (derives from core_competencies,
    // same cross-cutting invalidation career-profile.ts's own mutations
    // already do whenever core_competencies changes).
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["career-profile"] });
      queryClient.invalidateQueries({ queryKey: ["skills", "gap-analysis"] });
    },
  });
}

export function useDiscardResume() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (resumeId: string) =>
      apiClient.delete<void>(`/api/v1/resume-intelligence/${resumeId}`),
    onSuccess: (_data, resumeId) => {
      queryClient.removeQueries({ queryKey: KEYS.detail(resumeId) });
      queryClient.invalidateQueries({ queryKey: KEYS.list });
    },
  });
}
