import { apiClient } from "@/api/client";
import type { components } from "@/api/schema.gen";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

type InterviewTopicResponse = components["schemas"]["InterviewTopicResponse"];
type InterviewTopicRequest = components["schemas"]["InterviewTopicRequest"];
type InterviewTopicUpdateRequest = components["schemas"]["InterviewTopicUpdateRequest"];
type InterviewQuestionResponse = components["schemas"]["InterviewQuestionResponse"];
type InterviewQuestionRequest = components["schemas"]["InterviewQuestionRequest"];
type InterviewQuestionUpdateRequest = components["schemas"]["InterviewQuestionUpdateRequest"];
type InterviewPrepSummaryResponse = components["schemas"]["InterviewPrepSummaryResponse"];
type AddFollowUpQuestionRequest = components["schemas"]["AddFollowUpQuestionRequest"];
type UpdateFollowUpQuestionRequest = components["schemas"]["UpdateFollowUpQuestionRequest"];
type ToggleTopicPublicRequest = components["schemas"]["ToggleTopicPublicRequest"];

type MoveDirection = "up" | "down";

/** null = generic/Master-scoped, a real id = that Target Role — same
 * scoping axis career-profile.ts's Scope already establishes. */
type Scope = string | null;

function scopeKey(scope: Scope): string {
  return scope ?? "master";
}

function withScope(path: string, scope: Scope): string {
  return scope ? `${path}?target_role_id=${scope}` : path;
}

/** Writes a question or follow-up question response back into a cached
 * top-level questions list — a top-level question is replaced in place,
 * a follow-up is replaced inside its parent's `follow_ups` array (found
 * via `data.parent_question_id`, since a follow-up never appears as its
 * own top-level entry in this list). Shared by every mutation whose
 * response could be either shape: generate-answer (same endpoint for
 * both), and every follow-up-specific mutation below. */
function replaceQuestionInCache(
  old: InterviewQuestionResponse[] | undefined,
  data: InterviewQuestionResponse,
): InterviewQuestionResponse[] {
  if (data.parent_question_id === null) {
    if (!old) return [data];
    return old.map((q) => (q.id === data.id ? data : q));
  }
  if (!old) return [];
  return old.map((q) =>
    q.id === data.parent_question_id
      ? { ...q, follow_ups: q.follow_ups.map((f) => (f.id === data.id ? data : f)) }
      : q,
  );
}

const KEYS = {
  topics: (scope: Scope) => ["interview-prep", "topics", scopeKey(scope)] as const,
  questions: (scope: Scope) => ["interview-prep", "questions", scopeKey(scope)] as const,
  summary: () => ["interview-prep", "summary"] as const,
} as const;

export function useInterviewPrepSummary() {
  return useQuery({
    queryKey: KEYS.summary(),
    queryFn: () => apiClient.get<InterviewPrepSummaryResponse>("/api/v1/interview-prep/summary"),
  });
}

export function useInterviewTopics(scope: Scope = null) {
  return useQuery({
    queryKey: KEYS.topics(scope),
    queryFn: () =>
      apiClient.get<InterviewTopicResponse[]>(withScope("/api/v1/interview-prep/topics", scope)),
  });
}

export function useCreateInterviewTopic(scope: Scope = null) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: InterviewTopicRequest) =>
      apiClient.post<InterviewTopicResponse>("/api/v1/interview-prep/topics", body),
    onSuccess: (data) => {
      queryClient.setQueryData(KEYS.topics(scope), (old: InterviewTopicResponse[] | undefined) => [
        ...(old ?? []),
        data,
      ]);
      queryClient.invalidateQueries({ queryKey: KEYS.summary() });
    },
  });
}

export function useUpdateInterviewTopic(scope: Scope = null) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, body }: { id: string; body: InterviewTopicUpdateRequest }) =>
      apiClient.patch<InterviewTopicResponse>(`/api/v1/interview-prep/topics/${id}`, body),
    onSuccess: (data) => {
      // ScopeTagSelector allows unchecking the scope currently being
      // viewed (see its own docstring) — if that just happened, this
      // item no longer belongs in this scope's cached list at all, not
      // just updated in place.
      const stillInScope = data.scope_target_role_ids.includes(scope);
      queryClient.setQueryData(
        KEYS.topics(scope),
        (old: InterviewTopicResponse[] | undefined) => {
          if (!old) return stillInScope ? [data] : [];
          return stillInScope
            ? old.map((t) => (t.id === data.id ? data : t))
            : old.filter((t) => t.id !== data.id);
        },
      );
      // A scope tag add/remove changes another scope's topic_count too
      // (or this one's), which this scope's own cached list can't
      // reflect on its own.
      queryClient.invalidateQueries({ queryKey: KEYS.summary() });
    },
  });
}

/** `targetRoleId`/`deleteEverywhere` map straight to the DELETE
 * endpoint's query params — `deleteEverywhere` only matters when the
 * item is tagged to more than one scope (a single-scope item is always
 * fully deleted regardless of this flag, per InterviewTopicService's
 * own delete() semantics), but is always sent for clarity at the call
 * site rather than left implicit. */
export function useDeleteInterviewTopic(scope: Scope = null) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, deleteEverywhere }: { id: string; deleteEverywhere: boolean }) => {
      const params = new URLSearchParams({ delete_everywhere: String(deleteEverywhere) });
      if (scope) params.set("target_role_id", scope);
      return apiClient.delete(`/api/v1/interview-prep/topics/${id}?${params.toString()}`);
    },
    onSuccess: (_data, { id }) => {
      queryClient.setQueryData(
        KEYS.topics(scope),
        (old: InterviewTopicResponse[] | undefined) => old?.filter((t) => t.id !== id) ?? [],
      );
      // Any question that linked to this topic now has a stale topic_id
      // client-side — simplest correct fix is a background refetch
      // rather than trying to reconcile it locally.
      queryClient.invalidateQueries({ queryKey: KEYS.questions(scope) });
      queryClient.invalidateQueries({ queryKey: KEYS.summary() });
    },
  });
}

export function useMoveInterviewTopic(scope: Scope = null) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, direction }: { id: string; direction: MoveDirection }) =>
      apiClient.post<InterviewTopicResponse[]>(`/api/v1/interview-prep/topics/${id}/move`, {
        direction,
        target_role_id: scope,
      }),
    onSuccess: (data) => queryClient.setQueryData(KEYS.topics(scope), data),
  });
}

export function useUploadTopicColumnImage(scope: Scope = null) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, columnId, file }: { id: string; columnId: string; file: File }) =>
      apiClient.uploadFile<InterviewTopicResponse>(
        `/api/v1/interview-prep/topics/${id}/blocks/${columnId}/image`,
        file,
      ),
    onSuccess: (data) => {
      queryClient.setQueryData(
        KEYS.topics(scope),
        (old: InterviewTopicResponse[] | undefined) =>
          old?.map((t) => (t.id === data.id ? data : t)) ?? [data],
      );
    },
  });
}

/** Toggles a Topic's public/private ("Article") visibility — a
 * dedicated action, not folded into useUpdateInterviewTopic, mirroring
 * InterviewTopicService.set_public's own separation on the backend.
 * Turning ON invalidates the current-user query too — the first time
 * ANY resource is ever made public, the backend lazily assigns the
 * viewer a default handle (see HandleService.ensure_handle), which the
 * copy-link UI needs fresh, not whatever was cached at login. */
export function useToggleTopicPublic(scope: Scope = null) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, body }: { id: string; body: ToggleTopicPublicRequest }) =>
      apiClient.post<InterviewTopicResponse>(
        `/api/v1/interview-prep/topics/${id}/toggle-public`,
        body,
      ),
    onSuccess: (data, { body }) => {
      queryClient.setQueryData(
        KEYS.topics(scope),
        (old: InterviewTopicResponse[] | undefined) =>
          old?.map((t) => (t.id === data.id ? data : t)) ?? [data],
      );
      if (body.is_public) {
        queryClient.invalidateQueries({ queryKey: ["current-user"] });
      }
    },
  });
}

export function useInterviewQuestions(scope: Scope = null) {
  return useQuery({
    queryKey: KEYS.questions(scope),
    queryFn: () =>
      apiClient.get<InterviewQuestionResponse[]>(
        withScope("/api/v1/interview-prep/questions", scope),
      ),
  });
}

export function useCreateInterviewQuestion(scope: Scope = null) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: InterviewQuestionRequest) =>
      apiClient.post<InterviewQuestionResponse>("/api/v1/interview-prep/questions", body),
    onSuccess: (data) => {
      queryClient.setQueryData(
        KEYS.questions(scope),
        (old: InterviewQuestionResponse[] | undefined) => [...(old ?? []), data],
      );
      queryClient.invalidateQueries({ queryKey: KEYS.summary() });
    },
  });
}

export function useUpdateInterviewQuestion(scope: Scope = null) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, body }: { id: string; body: InterviewQuestionUpdateRequest }) =>
      apiClient.patch<InterviewQuestionResponse>(`/api/v1/interview-prep/questions/${id}`, body),
    onSuccess: (data) => {
      // Same "scope tags are freely editable, including the one
      // currently being viewed" case as useUpdateInterviewTopic above.
      const stillInScope = data.scope_target_role_ids.includes(scope);
      queryClient.setQueryData(
        KEYS.questions(scope),
        (old: InterviewQuestionResponse[] | undefined) => {
          if (!old) return stillInScope ? [data] : [];
          return stillInScope
            ? old.map((q) => (q.id === data.id ? data : q))
            : old.filter((q) => q.id !== data.id);
        },
      );
      queryClient.invalidateQueries({ queryKey: KEYS.summary() });
    },
  });
}

export function useDeleteInterviewQuestion(scope: Scope = null) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, deleteEverywhere }: { id: string; deleteEverywhere: boolean }) => {
      const params = new URLSearchParams({ delete_everywhere: String(deleteEverywhere) });
      if (scope) params.set("target_role_id", scope);
      return apiClient.delete(`/api/v1/interview-prep/questions/${id}?${params.toString()}`);
    },
    onSuccess: (_data, { id }) => {
      queryClient.setQueryData(
        KEYS.questions(scope),
        (old: InterviewQuestionResponse[] | undefined) => old?.filter((q) => q.id !== id) ?? [],
      );
      queryClient.invalidateQueries({ queryKey: KEYS.summary() });
    },
  });
}

export function useMoveInterviewQuestion(scope: Scope = null) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, direction }: { id: string; direction: MoveDirection }) =>
      apiClient.post<InterviewQuestionResponse[]>(`/api/v1/interview-prep/questions/${id}/move`, {
        direction,
        target_role_id: scope,
      }),
    onSuccess: (data) => queryClient.setQueryData(KEYS.questions(scope), data),
  });
}

export function useGenerateInterviewAnswer(scope: Scope = null) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) =>
      apiClient.post<InterviewQuestionResponse>(
        `/api/v1/interview-prep/questions/${id}/generate-answer`,
      ),
    onSuccess: (data) => {
      // `id` here can be either a top-level question or a follow-up's —
      // the endpoint is shared, see replaceQuestionInCache's own doc.
      queryClient.setQueryData(KEYS.questions(scope), (old: InterviewQuestionResponse[] | undefined) =>
        replaceQuestionInCache(old, data),
      );
    },
  });
}

// --- Follow-up questions ---
//
// The same InterviewQuestionResponse shape as a top-level question,
// nested under its parent's `follow_ups` — see
// app/domain/interview_prep/entities.py's InterviewQuestion docstring
// for the full "why". Not independently scope-tagged, so unlike every
// mutation above these never need to reason about "is it still in this
// scope" — a follow-up is visible wherever its parent is, full stop.

export function useAddFollowUpQuestion(scope: Scope = null) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ parentQuestionId, body }: { parentQuestionId: string; body: AddFollowUpQuestionRequest }) =>
      apiClient.post<InterviewQuestionResponse>(
        `/api/v1/interview-prep/questions/${parentQuestionId}/follow-ups`,
        body,
      ),
    onSuccess: (data, { parentQuestionId }) => {
      queryClient.setQueryData(
        KEYS.questions(scope),
        (old: InterviewQuestionResponse[] | undefined) =>
          old?.map((q) =>
            q.id === parentQuestionId ? { ...q, follow_ups: [...q.follow_ups, data] } : q,
          ) ?? [],
      );
      queryClient.invalidateQueries({ queryKey: KEYS.summary() });
    },
  });
}

export function useUpdateFollowUpQuestion(scope: Scope = null) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, body }: { id: string; body: UpdateFollowUpQuestionRequest }) =>
      apiClient.patch<InterviewQuestionResponse>(`/api/v1/interview-prep/follow-up-questions/${id}`, body),
    onSuccess: (data) => {
      queryClient.setQueryData(KEYS.questions(scope), (old: InterviewQuestionResponse[] | undefined) =>
        replaceQuestionInCache(old, data),
      );
    },
  });
}

export function useDeleteFollowUpQuestion(scope: Scope = null) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id }: { id: string; parentQuestionId: string }) =>
      apiClient.delete(`/api/v1/interview-prep/follow-up-questions/${id}`),
    onSuccess: (_data, { id, parentQuestionId }) => {
      queryClient.setQueryData(
        KEYS.questions(scope),
        (old: InterviewQuestionResponse[] | undefined) =>
          old?.map((q) =>
            q.id === parentQuestionId
              ? { ...q, follow_ups: q.follow_ups.filter((f) => f.id !== id) }
              : q,
          ) ?? [],
      );
      queryClient.invalidateQueries({ queryKey: KEYS.summary() });
    },
  });
}

export function useMoveFollowUpQuestion(scope: Scope = null) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, direction }: { id: string; direction: MoveDirection; parentQuestionId: string }) =>
      apiClient.post<InterviewQuestionResponse[]>(
        `/api/v1/interview-prep/follow-up-questions/${id}/move`,
        { direction },
      ),
    onSuccess: (siblings, { parentQuestionId }) => {
      queryClient.setQueryData(
        KEYS.questions(scope),
        (old: InterviewQuestionResponse[] | undefined) =>
          old?.map((q) => (q.id === parentQuestionId ? { ...q, follow_ups: siblings } : q)) ?? [],
      );
    },
  });
}
