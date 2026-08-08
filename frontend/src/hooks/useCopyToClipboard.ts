import { useCallback, useRef, useState } from "react";

/**
 * Copies text to the clipboard and exposes a short-lived `copied` flag
 * for inline UI feedback (e.g. swapping a button's icon/label to a
 * checkmark for a moment) — shared by every "Copy" button on the Skill
 * Intelligence page rather than each one re-implementing the same
 * clipboard-write-plus-timeout logic.
 */
export function useCopyToClipboard(resetAfterMs = 1500) {
  const [copied, setCopied] = useState(false);
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const copy = useCallback(
    async (text: string) => {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      if (timeoutRef.current) clearTimeout(timeoutRef.current);
      timeoutRef.current = setTimeout(() => setCopied(false), resetAfterMs);
    },
    [resetAfterMs],
  );

  return { copy, copied };
}
