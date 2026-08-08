import { useChatComposer } from "@/hooks/useChatComposer";
import { getErrorMessage } from "@/lib/errors";
import { Send } from "lucide-react";
import { useState } from "react";
import type { FormEvent, KeyboardEvent } from "react";

/**
 * Fixed bottom region of the app shell (brief Part 1.2): a persistent AI
 * Chat input, present on every page. A sent message is appended to the
 * center panel by ChatThread.tsx (via the shared chat-store), never
 * rendered here — this footer only ever owns the input itself. The
 * AI Career Coach page (CoachPage.tsx) is a second entry point into the
 * exact same send flow — see useChatComposer.ts.
 *
 * The user's own message is added to the store immediately (optimistic,
 * client-generated id) rather than waiting for the server round-trip —
 * see chat-store.ts's docstring for why that matters now that the
 * assistant reply is a real (and sometimes slow) LLM call.
 */
export function AppFooter() {
  const [draft, setDraft] = useState("");
  const { sendTurn, isPending, isError, error } = useChatComposer();

  function submit() {
    if (!draft.trim() || isPending) return;
    sendTurn(draft);
    setDraft("");
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
      className="fixed bottom-0 left-[var(--current-left-nav-w)] right-[var(--current-right-nav-w)] z-10 flex h-[var(--shell-footer-h)] items-center border-t border-border bg-[hsl(var(--footer-bg))] px-6 transition-[left,right] duration-200 ease-out"
      aria-label="AI chat"
    >
      <form onSubmit={handleSubmit} className="relative flex w-full items-center gap-3">
        {isError && (
          <p
            role="alert"
            className="absolute bottom-full left-0 mb-1.5 text-xs text-destructive"
          >
            {getErrorMessage(error)}
          </p>
        )}
        <textarea
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          onKeyDown={handleKeyDown}
          rows={1}
          placeholder="Ask Career Compass AI..."
          className="h-11 flex-1 resize-none rounded-md border-none bg-[linear-gradient(90deg,#a855f7_12.5%,#3b82f6_37.5%,#22c55e_58.33%,#fdba74_75%,#fca5a5_91.67%)] px-3 py-2.5 text-sm font-medium text-primary outline-none placeholder:font-bold placeholder:text-primary/70 focus:ring-2 focus:ring-ring"
        />
        <button
          type="submit"
          disabled={!draft.trim() || isPending}
          className="flex h-11 w-11 shrink-0 items-center justify-center rounded-md bg-[linear-gradient(90deg,#a855f7_12.5%,#3b82f6_37.5%,#22c55e_58.33%,#fdba74_75%,#fca5a5_91.67%)] text-primary transition-opacity hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-40"
          aria-label="Send message"
        >
          <Send className="h-4 w-4" />
        </button>
      </form>
    </footer>
  );
}
