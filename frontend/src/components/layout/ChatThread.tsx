import { cn } from "@/lib/utils";
import { useChatStore } from "@/stores/chat-store";

/**
 * Renders the current AI Chat thread below whatever page content is
 * already in the center panel (brief Part 1.2) — never in place of it.
 * Renders nothing until the first message is sent, and disappears again
 * when AppShell clears the store on Left Nav navigation.
 */
export function ChatThread() {
  const messages = useChatStore((state) => state.messages);
  const isSending = useChatStore((state) => state.isSending);

  if (messages.length === 0 && !isSending) {
    return null;
  }

  return (
    <div className="mt-10 border-t border-border pt-6">
      <h2 className="mb-4 font-display text-sm font-semibold text-muted-foreground">AI Chat</h2>
      <div className="flex flex-col gap-3">
        {messages.map((message) => (
          <div
            key={message.id}
            className={cn(
              "max-w-xl whitespace-pre-wrap rounded-lg px-4 py-2.5 text-sm",
              message.role === "user"
                ? "ml-auto bg-primary text-primary-foreground"
                : "mr-auto bg-muted text-foreground",
            )}
          >
            {message.content}
          </div>
        ))}
        {isSending && <TypingIndicator />}
      </div>
    </div>
  );
}

/**
 * Real LLM calls (Phase 4) can take several seconds — especially
 * against a local Ollama model on modest hardware — so this bubble is
 * the only signal the user gets that the AI Career Coach is actually
 * working rather than having silently dropped the message.
 */
function TypingIndicator() {
  return (
    <div
      className="mr-auto flex items-center gap-1 rounded-lg bg-muted px-4 py-3"
      role="status"
      aria-label="AI Career Coach is thinking"
    >
      {[0, 150, 300].map((delayMs) => (
        <span
          key={delayMs}
          className="h-2 w-2 animate-bounce rounded-full bg-muted-foreground/60"
          style={{ animationDelay: `${delayMs}ms` }}
        />
      ))}
    </div>
  );
}
