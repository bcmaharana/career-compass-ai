import { useLatestConversation, useSendChatMessage } from "@/api/queries/chat";
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
  // AppShell.tsx's own useLatestConversation() call resolves this and
  // hydrates conversationId once it does — calling the hook again here
  // is cheap (React Query dedupes by queryKey, no extra request) and is
  // what lets sendTurn hold off until that resume attempt has actually
  // finished. Without this guard, a message sent fast enough to beat
  // that query (page just loaded, or right after logging back in) would
  // go out with conversationId still null, silently starting a brand-new
  // conversation instead of resuming — the exact race a real user could
  // hit by typing and hitting send within that first second or so.
  const { isLoading: isResumingConversation } = useLatestConversation();
  const awaitingResume = !conversationId && isResumingConversation;

  function sendTurn(content: string) {
    const trimmed = content.trim();
    if (!trimmed || sendMessage.isPending || awaitingResume) return;

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
    // Covers both "a turn is actively in flight" and "still waiting to
    // know whether to resume an existing conversation" — ChatComposerForm
    // is the only real consumer of this, and both cases mean the same
    // thing to it: the send button should be disabled right now.
    isPending: sendMessage.isPending || awaitingResume,
    isError: sendMessage.isError,
    error: sendMessage.error,
  };
}
