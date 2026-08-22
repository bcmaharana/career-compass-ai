import { useLatestConversation, useSendChatMessage } from "@/api/queries/chat";
import { matchNavItem } from "@/lib/nav-items";
import { useChatStore } from "@/stores/chat-store";
import { useQueryClient } from "@tanstack/react-query";
import { useLocation } from "react-router-dom";

/**
 * The one place a chat turn actually gets sent — optimistic user message,
 * mutation call, assistant message written back into the shared
 * chat-store. Originally lived inline in AppFooter.tsx; pulled out so the
 * AI Career Coach page's suggested-prompt chips (CoachPage.tsx) can send a
 * turn the exact same way a typed message does, without a second,
 * diverging copy of this logic.
 *
 * `section_key` (2026-08-22) is only ever consulted by the backend when
 * starting a brand-new conversation (conversation_id is null) — it's
 * what conversation the message actually belongs to. Computed here from
 * the current route via matchNavItem, the same "which top-level section
 * is this" concept nav-items.ts already exposes for the Left Nav/Header,
 * rather than inventing a second taxonomy just for chat scoping.
 */
export function useChatComposer() {
  const location = useLocation();
  const sectionKey = matchNavItem(location.pathname).to;
  const conversationId = useChatStore((state) => state.conversationId);
  const addUserMessage = useChatStore((state) => state.addUserMessage);
  const confirmTurn = useChatStore((state) => state.confirmTurn);
  const setSending = useChatStore((state) => state.setSending);
  const sendMessage = useSendChatMessage();
  const queryClient = useQueryClient();
  // AppShell.tsx's own useLatestConversation() call resolves this and
  // hydrates conversationId once it does — calling the hook again here
  // is cheap (React Query dedupes by queryKey, no extra request) and is
  // what lets sendTurn hold off until that resume attempt has actually
  // finished. Without this guard, a message sent fast enough to beat
  // that query (page just loaded, or right after logging back in) would
  // go out with conversationId still null, silently starting a brand-new
  // conversation instead of resuming — the exact race a real user could
  // hit by typing and hitting send within that first second or so.
  const { isLoading: isResumingConversation } = useLatestConversation(sectionKey);
  const awaitingResume = !conversationId && isResumingConversation;

  function sendTurn(content: string) {
    const trimmed = content.trim();
    if (!trimmed || sendMessage.isPending || awaitingResume) return;

    const tempUserId = crypto.randomUUID();
    addUserMessage({ id: tempUserId, role: "user", content: trimmed });
    setSending(true);

    sendMessage.mutate(
      { conversation_id: conversationId, section_key: sectionKey, content: trimmed },
      {
        onSuccess: (data) => {
          // Reconciles the optimistic bubble above with its real
          // server-assigned id — a delete on that bubble afterward
          // otherwise silently no-ops against the throwaway client id.
          confirmTurn(data.conversation_id, tempUserId, data.user_message.id, {
            id: data.assistant_message.id,
            role: "assistant",
            content: data.assistant_message.content,
          });
          // Corrects this section's cached "latest conversation" answer
          // — a real bug caught live (2026-08-22): useLatestConversation
          // has `staleTime: Infinity`, so the very first visit to a
          // section with no conversation yet caches `{conversation_id:
          // null}` forever. Sending the section's first-ever message
          // creates a real conversation server-side, but chat-store.ts's
          // own conversationId is reset to null on every section
          // revisit (see AppShell.tsx's resetForSection) and re-derived
          // from this exact cached query — without this write, every
          // later revisit to the same section kept reading the frozen
          // "null" answer and looked like the conversation had vanished,
          // even though it was still sitting in the database. Also
          // covers reusing an already-known conversation_id (an existing
          // conversation's second message) with the identical value, a
          // harmless no-op write in that case.
          queryClient.setQueryData(["chat", "latest-conversation", sectionKey], {
            conversation_id: data.conversation_id,
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
