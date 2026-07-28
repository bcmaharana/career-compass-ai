import { useSendChatMessage } from "@/api/queries/chat";
import { useChatStore } from "@/stores/chat-store";
import { Send } from "lucide-react";
import { useState } from "react";
import type { FormEvent, KeyboardEvent } from "react";

/**
 * Fixed bottom region of the app shell (brief Part 1.2): a persistent AI
 * Chat input, present on every page. A sent message is appended to the
 * center panel by ChatThread.tsx (via the shared chat-store), never
 * rendered here — this footer only ever owns the input itself.
 *
 * The assistant reply is a placeholder echo for now (see
 * backend/app/application/chat/chat_service.py) — real AI reasoning
 * depends on the AI Platform being wired to a live provider, later work.
 */
export function AppFooter() {
  const [draft, setDraft] = useState("");
  const conversationId = useChatStore((state) => state.conversationId);
  const appendTurn = useChatStore((state) => state.appendTurn);
  const sendMessage = useSendChatMessage();

  function submit() {
    const content = draft.trim();
    if (!content || sendMessage.isPending) return;

    setDraft("");
    sendMessage.mutate(
      { conversation_id: conversationId, content },
      {
        onSuccess: (data) => {
          appendTurn({
            conversationId: data.conversation_id,
            userMessage: {
              id: data.user_message.id,
              role: "user",
              content: data.user_message.content,
            },
            assistantMessage: {
              id: data.assistant_message.id,
              role: "assistant",
              content: data.assistant_message.content,
            },
          });
        },
      },
    );
  }

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    submit();
  }

  function handleKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      submit();
    }
  }

  return (
    <footer
      className="fixed left-[var(--shell-left-nav-w)] right-[var(--shell-right-nav-w)] bottom-0 z-10 flex h-[var(--shell-footer-h)] items-center border-t border-border bg-[hsl(var(--footer-bg))] px-6"
      aria-label="AI chat"
    >
      <form onSubmit={handleSubmit} className="flex w-full items-center gap-3">
        <textarea
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          onKeyDown={handleKeyDown}
          rows={1}
          placeholder="Ask Career Compass AI..."
          className="h-11 flex-1 resize-none rounded-md border border-border bg-card px-3 py-2.5 text-sm text-accent outline-none placeholder:font-bold placeholder:text-accent focus:ring-2 focus:ring-ring"
        />
        <button
          type="submit"
          disabled={!draft.trim() || sendMessage.isPending}
          className="flex h-11 w-11 shrink-0 items-center justify-center rounded-md bg-[linear-gradient(90deg,#a855f7_12.5%,#3b82f6_37.5%,#22c55e_58.33%,#fdba74_75%,#fca5a5_91.67%)] text-primary transition-opacity hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-40"
          aria-label="Send message"
        >
          <Send className="h-4 w-4" />
        </button>
      </form>
    </footer>
  );
}
