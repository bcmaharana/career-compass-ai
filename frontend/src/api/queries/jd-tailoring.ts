import { apiClient } from "@/api/client";
import type { components } from "@/api/schema.gen";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

type StartFromListingRequest = components["schemas"]["StartFromListingRequest"];
type StartCustomRequest = components["schemas"]["StartCustomRequest"];
type StartSessionResponse = components["schemas"]["StartSessionResponse"];
type JdExtractionRequest = components["schemas"]["JdExtractionRequest"];
type JdExtractionResponse = components["schemas"]["JdExtractionResponse"];
type JdTailoringSessionResponse = components["schemas"]["JdTailoringSessionResponse"];
type JdTailoringMessageResponse = components["schemas"]["JdTailoringMessageResponse"];
type SendMessageRequest = components["schemas"]["SendMessageRequest"];
type SendMessageResponse = components["schemas"]["SendMessageResponse"];
type DeleteMessageResponse = components["schemas"]["DeleteMessageResponse"];

const KEYS = {
  sessions: ["jd-tailoring", "sessions"] as const,
  messages: (sessionId: string) => ["jd-tailoring", "sessions", sessionId, "messages"] as const,
};

/**
 * Starting a session from a Job Listing row also auto-creates a linked
 * Job Application server-side (see JdTailoringIntakeService) — both the
 * jd-tailoring session-history list and the job-applications list are
 * stale after this succeeds.
 */
export function useStartSessionFromListing() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: StartFromListingRequest) =>
      apiClient.post<StartSessionResponse>("/api/v1/jd-tailoring/sessions/from-listing", body),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: KEYS.sessions });
      queryClient.invalidateQueries({ queryKey: ["job-applications"] });
    },
  });
}

/**
 * "Add Your Own JD" — always independent of whatever listing row is
 * selected on the page behind it. Also auto-creates a linked Job
 * Application (see JdTailoringIntakeService.start_custom) using the
 * company/role_title the caller resolved (AI extraction + manual
 * gap-fill) — no provider_id exists for a pasted JD, so unlike
 * start-from-listing there's nothing to dedupe against.
 */
export function useStartCustomSession() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: StartCustomRequest) =>
      apiClient.post<StartSessionResponse>("/api/v1/jd-tailoring/sessions/custom", body),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: KEYS.sessions });
      queryClient.invalidateQueries({ queryKey: ["job-applications"] });
    },
  });
}

/** One-shot Company/Role Title extraction from pasted JD text — no persistence. */
export function useExtractJd() {
  return useMutation({
    mutationFn: (body: JdExtractionRequest) =>
      apiClient.post<JdExtractionResponse>("/api/v1/jd-tailoring/extract", body),
  });
}

/** Session history list, most recently created first (see the backend's list_for_user). */
export function useJdTailoringSessions() {
  return useQuery({
    queryKey: KEYS.sessions,
    queryFn: () => apiClient.get<JdTailoringSessionResponse[]>("/api/v1/jd-tailoring/sessions"),
  });
}

export function useJdTailoringMessages(sessionId: string | null) {
  return useQuery({
    queryKey: sessionId ? KEYS.messages(sessionId) : ["jd-tailoring", "sessions", "none"],
    queryFn: () =>
      apiClient.get<JdTailoringMessageResponse[]>(
        `/api/v1/jd-tailoring/sessions/${sessionId}/messages`,
      ),
    enabled: sessionId !== null,
  });
}

export function useSendJdTailoringMessage(sessionId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: SendMessageRequest) =>
      apiClient.post<SendMessageResponse>(
        `/api/v1/jd-tailoring/sessions/${sessionId}/messages`,
        body,
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: KEYS.messages(sessionId) });
    },
  });
}

/**
 * Generates a JD-tailored resume (Word or PDF) for a session — its own
 * artifact, never overwriting the profile's canonical resume (see
 * TailoredResumeService's key prefix). Never rejects on a generation
 * failure (the backend returns a normal 200 with
 * tailored_resume_status="failed" instead — same contract
 * InterviewAnswerService's generate/regenerate has), so the caller
 * reads the returned session's status rather than an onError handler.
 * Writes the confirmed response directly into the sessions cache
 * (setQueryData, not just invalidate) so the fresh download URLs and
 * status show immediately, matching this app's established
 * "mutations write confirmed server state directly into the cache"
 * convention.
 */
export function useGenerateTailoredResume(sessionId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (format: "docx" | "pdf") =>
      apiClient.post<JdTailoringSessionResponse>(
        `/api/v1/jd-tailoring/sessions/${sessionId}/generate-resume?format=${format}`,
      ),
    onSuccess: (updated) => {
      queryClient.setQueryData<JdTailoringSessionResponse[]>(KEYS.sessions, (old) =>
        old?.map((session) => (session.id === updated.id ? updated : session)),
      );
    },
  });
}

export function useDeleteJdTailoringSession() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (sessionId: string) =>
      apiClient.delete<void>(`/api/v1/jd-tailoring/sessions/${sessionId}`),
    onSuccess: () => {
      // exact: true — a plain (default, prefix-matching) invalidation of
      // KEYS.sessions also matches KEYS.messages(deletedSessionId) (which
      // nests under the same ["jd-tailoring", "sessions", ...] prefix),
      // triggering a refetch of the just-deleted session's messages
      // before the page's own onSuccess has cleared `?session=` — a real
      // (harmless but noisy) 404 caught live. Only the sessions list
      // itself needs invalidating here.
      queryClient.invalidateQueries({ queryKey: KEYS.sessions, exact: true });
    },
  });
}

/** Wipes just the conversation — the session itself (JD text, target
 * role link, any generated tailored resume) stays and keeps showing in
 * the Sessions list, unlike useDeleteJdTailoringSession above which
 * removes the whole thing. */
export function useClearJdTailoringMessages() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (sessionId: string) =>
      apiClient.delete<void>(`/api/v1/jd-tailoring/sessions/${sessionId}/messages`),
    onSuccess: (_data, sessionId) => {
      queryClient.setQueryData<JdTailoringMessageResponse[]>(KEYS.messages(sessionId), []);
    },
  });
}

/** Removes a whole question+answer turn — the message clicked plus its
 * paired counterpart, if the backend found one immediately adjacent to
 * it (see JdTailoringSessionService.delete_message). The response body
 * lists every id actually removed (not just the one requested) —
 * relying on the passed-in `messageId` alone here (an earlier version
 * did exactly that) left the paired bubble stuck on screen until a full
 * refetch, since the cache update had no way to know a second row had
 * also gone (caught from a direct user report, 2026-08-21). */
export function useDeleteJdTailoringMessage(sessionId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (messageId: string) =>
      apiClient.delete<DeleteMessageResponse>(
        `/api/v1/jd-tailoring/sessions/${sessionId}/messages/${messageId}`,
      ),
    onSuccess: (data) => {
      const deletedIds = new Set(data.deleted_message_ids);
      queryClient.setQueryData<JdTailoringMessageResponse[]>(KEYS.messages(sessionId), (old) =>
        old?.filter((message) => !deletedIds.has(message.id)),
      );
    },
  });
}
