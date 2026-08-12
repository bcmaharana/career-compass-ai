import { apiClient } from "@/api/client";
import type { components } from "@/api/schema.gen";
import { useMutation, useQuery } from "@tanstack/react-query";

type SendChatMessageRequest = components["schemas"]["SendChatMessageRequest"];
type SendChatMessageResponse = components["schemas"]["SendChatMessageResponse"];
type LatestConversationResponse = components["schemas"]["LatestConversationResponse"];

export function useSendChatMessage() {
  return useMutation({
    mutationFn: (body: SendChatMessageRequest) =>
      apiClient.post<SendChatMessageResponse>("/api/v1/chat/messages", body),
  });
}

/** Lets AppShell.tsx resume the same conversation after a fresh page load
 * or a logout/login cycle — see chat-store.ts's own docstring for why
 * conversation_id otherwise doesn't survive either. `staleTime: Infinity`
 * since this only needs to run once per app mount, not refetch on window
 * focus etc. — a conversation someone starts *after* this resolves is
 * tracked in chat-store.ts from then on, not from a refetch of this. */
export function useLatestConversation() {
  return useQuery({
    queryKey: ["chat", "latest-conversation"],
    queryFn: () => apiClient.get<LatestConversationResponse>("/api/v1/chat/conversations/latest"),
    staleTime: Infinity,
  });
}
