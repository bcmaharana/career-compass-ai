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
      uploadToken,
      signal,
    }: {
      file: File;
      targetRoleId: string | null;
      // Correlates this upload with a later cancelUpload() call — see
      // useCancelUpload below for why this is what makes Cancel a real,
      // reliable server-side stop rather than just abandoning the fetch.
      uploadToken: string;
      signal?: AbortSignal;
    }) =>
      apiClient.uploadFile<ResumeResponse>(
        "/api/v1/resume-intelligence/upload",
        file,
        "file",
        {
          ...(targetRoleId ? { target_role_id: targetRoleId } : {}),
          upload_token: uploadToken,
        },
        signal,
      ),
    onSuccess: (data) => {
      queryClient.setQueryData(KEYS.detail(data.id), data);
      queryClient.invalidateQueries({ queryKey: KEYS.list });
    },
  });
}

/**
 * Tells the backend to actually cancel a still-running extraction,
 * looked up by the same upload_token the upload request was sent with —
 * separate from (and more reliable than) aborting the browser's own
 * fetch, which by itself does nothing to stop the server-side coroutine.
 * See the backend's `/resume-intelligence/upload/{upload_token}/cancel`
 * docstring for why this exists instead of relying on the server
 * detecting the client's disconnect (verified live not to work in this
 * dev environment's Docker Desktop networking).
 */
export function useCancelUpload() {
  return useMutation({
    mutationFn: (uploadToken: string) =>
      apiClient.post<void>(`/api/v1/resume-intelligence/upload/${uploadToken}/cancel`),
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
