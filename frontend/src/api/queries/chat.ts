import { apiClient } from "@/api/client";
import type { components } from "@/api/schema.gen";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

type SendChatMessageRequest = components["schemas"]["SendChatMessageRequest"];
type SendChatMessageResponse = components["schemas"]["SendChatMessageResponse"];
type LatestConversationResponse = components["schemas"]["LatestConversationResponse"];
type ChatMessageResponse = components["schemas"]["ChatMessageResponse"];
type DeleteChatMessageResponse = components["schemas"]["DeleteChatMessageResponse"];

const KEYS = {
  messages: (conversationId: string) => ["chat", "conversations", conversationId, "messages"] as const,
};

export function useSendChatMessage() {
  return useMutation({
    mutationFn: (body: SendChatMessageRequest) =>
      apiClient.post<SendChatMessageResponse>("/api/v1/chat/messages", body),
  });
}

/** Lets AppShell.tsx resume that SECTION's own conversation after a fresh
 * page load, a logout/login cycle, or navigating into a section for the
 * first time this session — see chat-store.ts's own docstring for why
 * conversation_id otherwise doesn't survive any of those. Keyed by
 * `sectionKey` (matchNavItem(pathname).to) so switching sections
 * naturally triggers its own fetch rather than reusing another
 * section's cached answer. `staleTime: Infinity` since this only needs
 * to run once per section per app mount, not refetch on window focus
 * etc. — a conversation someone starts *after* this resolves is tracked
 * in chat-store.ts from then on, not from a refetch of this. */
export function useLatestConversation(sectionKey: string) {
  return useQuery({
    queryKey: ["chat", "latest-conversation", sectionKey],
    queryFn: () =>
      apiClient.get<LatestConversationResponse>(
        `/api/v1/chat/conversations/latest?section_key=${encodeURIComponent(sectionKey)}`,
      ),
    staleTime: Infinity,
  });
}

/** Real, fetchable history (2026-08-21, matching JD Tailoring's own
 * useJdTailoringMessages) — hydrates chat-store.ts's `messages` array
 * with what's actually saved server-side, rather than the thread only
 * ever showing what accumulated client-side this session. */
export function useChatMessages(conversationId: string | null) {
  return useQuery({
    queryKey: conversationId ? KEYS.messages(conversationId) : ["chat", "conversations", "none"],
    queryFn: () =>
      apiClient.get<ChatMessageResponse[]>(
        `/api/v1/chat/conversations/${conversationId}/messages`,
      ),
    enabled: conversationId !== null,
  });
}

/** "Clear conversation" — wipes messages, the conversation row/id stays
 * (matching JD Tailoring's useClearJdTailoringMessages). */
export function useClearChatMessages() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (conversationId: string) =>
      apiClient.delete<void>(`/api/v1/chat/conversations/${conversationId}/messages`),
    onSuccess: (_data, conversationId) => {
      queryClient.setQueryData<ChatMessageResponse[]>(KEYS.messages(conversationId), []);
    },
  });
}

/** Removes the whole conversation — matching JD Tailoring's
 * useDeleteJdTailoringSession. The caller is responsible for resetting
 * chat-store.ts's conversationId afterward (see ConversationPanel.tsx),
 * since this hook only knows about the TanStack Query cache, not that
 * store. Takes the current section's key so it can correct that exact
 * section's cached "latest conversation" entry.
 *
 * Also corrects the cached "latest conversation" query to `null` here —
 * a real bug caught live (2026-08-21): that query has `staleTime:
 * Infinity` and is fetched once per section, so without this its cached
 * data kept pointing at the conversation this very mutation just
 * deleted, which AppShell.tsx's resume effect would otherwise read and
 * write straight back into the store the moment conversationId became
 * null again. */
export function useDeleteChatConversation(sectionKey: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (conversationId: string) =>
      apiClient.delete<void>(`/api/v1/chat/conversations/${conversationId}`),
    onSuccess: () => {
      queryClient.setQueryData<LatestConversationResponse>(
        ["chat", "latest-conversation", sectionKey],
        { conversation_id: null },
      );
    },
  });
}

/** Removes a whole question+answer turn — the message clicked plus its
 * paired counterpart, if the backend found one immediately adjacent to
 * it. The response lists every id actually removed (matching JD
 * Tailoring's useDeleteJdTailoringMessage) so the caller can drop every
 * affected bubble from chat-store.ts, not just the one it clicked. */
export function useDeleteChatMessage(conversationId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (messageId: string) =>
      apiClient.delete<DeleteChatMessageResponse>(
        `/api/v1/chat/conversations/${conversationId}/messages/${messageId}`,
      ),
    onSuccess: (data) => {
      const deletedIds = new Set(data.deleted_message_ids);
      queryClient.setQueryData<ChatMessageResponse[]>(KEYS.messages(conversationId), (old) =>
        old?.filter((message) => !deletedIds.has(message.id)),
      );
    },
  });
}
