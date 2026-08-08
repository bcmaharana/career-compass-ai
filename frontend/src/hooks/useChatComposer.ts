import { useSendChatMessage } from "@/api/queries/chat";
import { useChatStore } from "@/stores/chat-store";

/**
 * The one place a chat turn actually gets sent — optimistic user message,
 * mutation call, assistant message written back into the shared
 * chat-store. Originally lived inline in AppFooter.tsx; pulled out so the
 * AI Career Coach page's suggested-prompt chips (CoachPage.tsx) can send a
 * turn the exact same way a typed message does, without a second,
 * diverging copy of this logic.
 */
export function useChatComposer() {
  const conversationId = useChatStore((state) => state.conversationId);
  const addUserMessage = useChatStore((state) => state.addUserMessage);
  const addAssistantMessage = useChatStore((state) => state.addAssistantMessage);
  const setSending = useChatStore((state) => state.setSending);
  const sendMessage = useSendChatMessage();

  function sendTurn(content: string) {
    const trimmed = content.trim();
    if (!trimmed || sendMessage.isPending) return;

    addUserMessage({ id: crypto.randomUUID(), role: "user", content: trimmed });
    setSending(true);

    sendMessage.mutate(
      { conversation_id: conversationId, content: trimmed },
      {
        onSuccess: (data) => {
          addAssistantMessage(data.conversation_id, {
            id: data.assistant_message.id,
            role: "assistant",
            content: data.assistant_message.content,
          });
        },
        onSettled: () => setSending(false),
      },
    );
  }

  return {
    sendTurn,
    isPending: sendMessage.isPending,
    isError: sendMessage.isError,
    error: sendMessage.error,
  };
}
