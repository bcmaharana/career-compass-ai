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

  if (messages.length === 0) {
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
      </div>
    </div>
  );
}
