import { apiClient } from "@/api/client";
import type { components } from "@/api/schema.gen";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

type InterviewTopicResponse = components["schemas"]["InterviewTopicResponse"];
type InterviewTopicRequest = components["schemas"]["InterviewTopicRequest"];
type InterviewTopicUpdateRequest = components["schemas"]["InterviewTopicUpdateRequest"];
type InterviewQuestionResponse = components["schemas"]["InterviewQuestionResponse"];
type InterviewQuestionRequest = components["schemas"]["InterviewQuestionRequest"];
type InterviewQuestionUpdateRequest = components["schemas"]["InterviewQuestionUpdateRequest"];
type InterviewPrepScopeSummaryResponse = components["schemas"]["InterviewPrepScopeSummaryResponse"];

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

const KEYS = {
  topics: (scope: Scope) => ["interview-prep", "topics", scopeKey(scope)] as const,
  questions: (scope: Scope) => ["interview-prep", "questions", scopeKey(scope)] as const,
  summary: () => ["interview-prep", "summary"] as const,
} as const;

export function useInterviewPrepSummary() {
  return useQuery({
    queryKey: KEYS.summary(),
    queryFn: () =>
      apiClient.get<InterviewPrepScopeSummaryResponse[]>("/api/v1/interview-prep/summary"),
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
      queryClient.setQueryData(
        KEYS.topics(scope),
        (old: InterviewTopicResponse[] | undefined) =>
          old?.map((t) => (t.id === data.id ? data : t)) ?? [data],
      );
    },
  });
}

export function useDeleteInterviewTopic(scope: Scope = null) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => apiClient.delete(`/api/v1/interview-prep/topics/${id}`),
    onSuccess: (_data, id) => {
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
      }),
    onSuccess: (data) => queryClient.setQueryData(KEYS.topics(scope), data),
  });
}

export function useUploadTopicImage(scope: Scope = null) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, file }: { id: string; file: File }) =>
      apiClient.uploadFile<InterviewTopicResponse>(
        `/api/v1/interview-prep/topics/${id}/image`,
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

export function useDeleteTopicImage(scope: Scope = null) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) =>
      apiClient.delete<InterviewTopicResponse>(`/api/v1/interview-prep/topics/${id}/image`),
    onSuccess: (data) => {
      queryClient.setQueryData(
        KEYS.topics(scope),
        (old: InterviewTopicResponse[] | undefined) =>
          old?.map((t) => (t.id === data.id ? data : t)) ?? [data],
      );
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
      queryClient.setQueryData(
        KEYS.questions(scope),
        (old: InterviewQuestionResponse[] | undefined) =>
          old?.map((q) => (q.id === data.id ? data : q)) ?? [data],
      );
    },
  });
}

export function useDeleteInterviewQuestion(scope: Scope = null) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => apiClient.delete(`/api/v1/interview-prep/questions/${id}`),
    onSuccess: (_data, id) => {
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
      queryClient.setQueryData(
        KEYS.questions(scope),
        (old: InterviewQuestionResponse[] | undefined) =>
          old?.map((q) => (q.id === data.id ? data : q)) ?? [data],
      );
    },
  });
}
