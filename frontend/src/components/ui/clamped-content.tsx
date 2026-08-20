import { RichTextDisplay } from "@/components/ui/rich-text-editor";
import { cn } from "@/lib/utils";
import { useEffect, useRef, useState } from "react";
import type { ReactNode } from "react";

interface ClampedTextProps {
  children: ReactNode;
  /** The underlying text/html content, used only as the effect
   * dependency that decides when to re-measure overflow — `children`
   * itself is a fresh element on every render, so it can't serve as a
   * stable dependency the way this plain string can. */
  content: string;
  /** Accessible label for the Show more/less toggle, e.g. "Senior
   * Engineer description" — read by screen readers, not shown visually. */
  label: string;
  className?: string;
}

/**
 * Generic "clamp to 3 lines, click to see the rest" wrapper — replaces
 * the old all-or-nothing Eye/EyeOff CollapseToggle previously used for
 * Experience entry descriptions and Interview Prep's AI-Suggested
 * Answer (direct 2026-08-20 request: "show 1st three lines only and
 * when user clicks, then sees the full", extended the same day to
 * Interview Prep). Content-agnostic — callers render their own
 * `children` (rich HTML via ClampedRichText below, or plain text
 * directly) so this one component covers both.
 *
 * The toggle only renders when the content actually overflows 3 lines —
 * measured once via scrollHeight vs. clientHeight against the initial
 * (always-clamped-on-mount, since `expanded` starts false) render, the
 * same overflow-detection technique this app's rich-text editor
 * auto-resize logic already uses elsewhere. Short content that already
 * fits in 3 lines shows no button at all, since there's nothing more to
 * reveal.
 */
export function ClampedText({ children, content, label, className }: ClampedTextProps) {
  const [expanded, setExpanded] = useState(false);
  const [isOverflowing, setIsOverflowing] = useState(false);
  const contentRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = contentRef.current;
    if (!el) return;
    setIsOverflowing(el.scrollHeight > el.clientHeight + 1);
    // Deliberately only re-measures when the content itself changes, not
    // on every `expanded` toggle — once expanded, the clamp class is
    // gone, so scrollHeight/clientHeight would trivially match and wipe
    // out the overflow flag that "Show less" depends on to reappear.
  }, [content]);

  return (
    <div>
      <div ref={contentRef} className={cn(expanded ? undefined : "line-clamp-3", className)}>
        {children}
      </div>
      {isOverflowing && (
        <button
          type="button"
          onClick={() => setExpanded((v) => !v)}
          aria-label={expanded ? `Show less of ${label}` : `Show more of ${label}`}
          className="mt-1 text-xs font-medium text-accent hover:underline"
        >
          {expanded ? "Show less" : "Show more"}
        </button>
      )}
    </div>
  );
}

/** ClampedText specialized for sanitized rich-text HTML (RichTextDisplay)
 * — the common case (Experience/Education/etc. descriptions). */
export function ClampedRichText({
  html,
  label,
  className,
}: {
  html: string;
  label: string;
  className?: string;
}) {
  return (
    <ClampedText content={html} label={label} className={className}>
      <RichTextDisplay html={html} />
    </ClampedText>
  );
}
