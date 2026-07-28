import { apiClient } from "@/api/client";
import type { components } from "@/api/schema.gen";
import { useMutation } from "@tanstack/react-query";

type SendChatMessageRequest = components["schemas"]["SendChatMessageRequest"];
type SendChatMessageResponse = components["schemas"]["SendChatMessageResponse"];

export function useSendChatMessage() {
  return useMutation({
    mutationFn: (body: SendChatMessageRequest) =>
      apiClient.post<SendChatMessageResponse>("/api/v1/chat/messages", body),
  });
}
