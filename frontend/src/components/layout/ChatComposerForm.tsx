import { useChatComposer } from "@/hooks/useChatComposer";
import { getErrorMessage } from "@/lib/errors";
import { cn } from "@/lib/utils";
import { Bot } from "lucide-react";
import { useRef, useState } from "react";
import type { ChangeEvent, FormEvent, KeyboardEvent } from "react";

/**
 * How many single-line heights the box may grow to before it scrolls
 * internally instead of growing further — a multiplier of the textarea's
 * own CSS `min-height` (min-h-11, see below) rather than a hardcoded px
 * value, so the cap scales the same way the CSS-driven min height
 * already does (globals.css shrinks root font-size, and therefore every
 * rem-based min-height, below `md` — see its "Mobile shell only" note).
 */
const MAX_HEIGHT_LINES = 5;

/** Grows/shrinks the textarea to fit its current content, clamped between
 * its CSS min-height (the original single-line box) and MAX_HEIGHT_LINES
 * worth of that — beyond the cap it scrolls internally
 * (overflow-y-auto is a static class, not toggled here) rather than
 * growing further. Resetting to `height: auto` first is required each
 * call so scrollHeight reflects the *current* content, not a stale
 * larger value left over from before text was deleted. */
function autoResize(el: HTMLTextAreaElement) {
  el.style.height = "auto";
  const minHeight = parseFloat(getComputedStyle(el).minHeight) || el.scrollHeight;
  const maxHeight = minHeight * MAX_HEIGHT_LINES;
  el.style.height = `${Math.min(Math.max(el.scrollHeight, minHeight), maxHeight)}px`;
}

interface ChatComposerFormProps {
  className?: string;
  textareaClassName?: string;
}

/**
 * The send-a-turn form itself: textarea + send button + inline error.
 * Extracted from AppFooter.tsx so it's a standalone, reusable piece
 * rather than logic inlined there — `className`/`textareaClassName` let
 * a caller adjust the surrounding chrome without forking the submit/
 * keydown/auto-resize logic itself.
 *
 * The textarea auto-grows with its content (autoResize above), capped at
 * MAX_HEIGHT_LINES worth of its own single-line height before it scrolls
 * internally — the form uses `items-end` so the send button stays
 * pinned to the last line as the box grows upward, matching how the
 * fixed footer bar (AppFooter.tsx) that hosts this on every page tracks
 * the box's actual height via --current-footer-h rather than a static
 * one.
 */
export function ChatComposerForm({ className, textareaClassName }: ChatComposerFormProps) {
  const [draft, setDraft] = useState("");
  const { sendTurn, isPending, isError, error } = useChatComposer();
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  function submit() {
    if (!draft.trim() || isPending) return;
    sendTurn(draft);
    setDraft("");
    // Clearing the inline height (rather than reusing autoResize on now-
    // empty content) drops straight back to the CSS min-h-11 default —
    // simplest possible reset, no computed-style math needed for it.
    if (textareaRef.current) {
      textareaRef.current.style.height = "";
    }
  }

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    submit();
  }

  function handleChange(event: ChangeEvent<HTMLTextAreaElement>) {
    setDraft(event.target.value);
    autoResize(event.target);
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
      className={cn("relative flex w-full items-end gap-3", className)}
    >
      {isError && (
        <p role="alert" className="absolute bottom-full left-0 mb-1.5 text-xs text-destructive">
          {getErrorMessage(error)}
        </p>
      )}
      <textarea
        ref={textareaRef}
        value={draft}
        onChange={handleChange}
        onKeyDown={handleKeyDown}
        rows={1}
        placeholder="Ask Career Compass AI..."
        className={cn(
          "min-h-11 flex-1 resize-none overflow-y-auto scrollbar-hide rounded-md border-none bg-[linear-gradient(90deg,#a855f7_12.5%,#3b82f6_37.5%,#22c55e_58.33%,#fdba74_75%,#fca5a5_91.67%)] px-3 py-2.5 text-sm font-medium text-primary outline-none placeholder:font-bold placeholder:text-primary/70 focus:ring-2 focus:ring-ring",
          textareaClassName,
        )}
      />
      <button
        type="submit"
        disabled={!draft.trim() || isPending}
        className="flex h-11 w-11 shrink-0 items-center justify-center rounded-md bg-[linear-gradient(90deg,#a855f7_12.5%,#3b82f6_37.5%,#22c55e_58.33%,#fdba74_75%,#fca5a5_91.67%)] text-primary transition-opacity hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-40"
        aria-label="Send message"
      >
        <Bot className="h-4 w-4" />
      </button>
    </form>
  );
}
