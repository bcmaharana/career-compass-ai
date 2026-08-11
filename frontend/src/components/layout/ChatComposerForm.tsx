import { useChatComposer } from "@/hooks/useChatComposer";
import { getErrorMessage } from "@/lib/errors";
import { cn } from "@/lib/utils";
import { Send } from "lucide-react";
import { useState } from "react";
import type { FormEvent, KeyboardEvent } from "react";

interface ChatComposerFormProps {
  className?: string;
  textareaClassName?: string;
}

/**
 * The send-a-turn form itself: textarea + send button + inline error.
 * Extracted from AppFooter.tsx (the desktop docked chat bar) so
 * MobileChatSheet.tsx's bottom-sheet chat can use the exact same
 * submit/keydown logic instead of a second, diverging copy — both already
 * share `useChatComposer()`, only the surrounding chrome (a fixed bar vs.
 * a sheet's pinned footer) differs, which each caller controls via
 * `className`/`textareaClassName`.
 */
export function ChatComposerForm({ className, textareaClassName }: ChatComposerFormProps) {
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
    <form
      onSubmit={handleSubmit}
      className={cn("relative flex w-full items-center gap-3", className)}
    >
      {isError && (
        <p role="alert" className="absolute bottom-full left-0 mb-1.5 text-xs text-destructive">
          {getErrorMessage(error)}
        </p>
      )}
      <textarea
        value={draft}
        onChange={(event) => setDraft(event.target.value)}
        onKeyDown={handleKeyDown}
        rows={1}
        placeholder="Ask Career Compass AI..."
        className={cn(
          "h-11 flex-1 resize-none rounded-md border-none bg-[linear-gradient(90deg,#a855f7_12.5%,#3b82f6_37.5%,#22c55e_58.33%,#fdba74_75%,#fca5a5_91.67%)] px-3 py-2.5 text-sm font-medium text-primary outline-none placeholder:font-bold placeholder:text-primary/70 focus:ring-2 focus:ring-ring",
          textareaClassName,
        )}
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
  );
}
