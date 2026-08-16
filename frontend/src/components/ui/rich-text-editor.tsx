import { cn } from "@/lib/utils";
import { Bold, IndentDecrease, IndentIncrease, Italic, List } from "lucide-react";
import { useEffect, useRef } from "react";

/**
 * A small hand-rolled rich-text editor (Bold/Italic/text color only) —
 * not a real editor library. Matches this app's "no heavy UI kit"
 * convention (see Dialog's own docstring). Backed by a plain
 * contenteditable div driven by the deprecated-but-still-universally-
 * supported document.execCommand — proportionate to "bold, color,
 * italics" as literally requested, not a general-purpose editor.
 *
 * Uncontrolled by design: `defaultValue` seeds the DOM exactly once, in
 * a mount-only effect (`el.innerHTML = ...`, not a `dangerouslySetInnerHTML`
 * prop) — deliberately NOT wired through JSX, because a real bug shipped
 * from doing that: callers naturally pass their own onChange-updated
 * state right back in as `defaultValue` (e.g. `defaultValue={form.discussion}
 * onChange={(html) => setForm({ ...form, discussion: html })}`), and
 * `dangerouslySetInnerHTML` re-diffs and reassigns `innerHTML` on every
 * render whose `__html` string differs from the last — which is every
 * keystroke here. Reassigning a contenteditable's innerHTML resets the
 * browser's caret to the start of the element, so each subsequent
 * keystroke inserted at position 0 instead of the caret position,
 * silently typing every string in reverse. Caught live (not by review):
 * typing "Bold discussion text" round-tripped through the API as
 * "txet noissucsid dloB". Routing the initial value through a
 * mount-only effect instead means later `defaultValue` prop changes are
 * simply never looked at again — this must remount (via a `key` or
 * conditional render) to pick up a genuinely different value, same
 * "initialize once at the moment edit opens, never reactively re-sync"
 * rule this app already follows everywhere else (see CLAUDE.md's
 * Frontend conventions). Every write is re-sanitized server-side
 * regardless of what this sends (see app/core/rich_text.py) — the raw
 * HTML is never the enforcement boundary, just what the user sees while
 * editing.
 */
export function RichTextEditor({
  id,
  defaultValue,
  onChange,
  placeholder,
  className,
  autoFocus,
}: {
  id?: string;
  defaultValue?: string | null;
  onChange: (html: string) => void;
  placeholder?: string;
  className?: string;
  autoFocus?: boolean;
}) {
  const editorRef = useRef<HTMLDivElement>(null);
  const initialValueRef = useRef(defaultValue ?? "");

  useEffect(() => {
    if (editorRef.current) {
      editorRef.current.innerHTML = initialValueRef.current;
    }
    // Intentionally empty deps — see the component docstring on why
    // this must only ever run once, on mount.
  }, []);

  function exec(command: string, value?: string) {
    editorRef.current?.focus();
    // styleWithCSS is a GLOBAL, persistent mode for the whole document,
    // not a per-command flag — once any click enables it, every later
    // command (on any editor, for the rest of the page's lifetime) also
    // starts producing CSS-based <span style="..."> markup instead of
    // semantic tags. Only foreColor genuinely needs that (no tag means
    // "arbitrary color"); bold/italic have real semantic tags (<b>/<i>)
    // that are simpler and don't need it. Explicitly setting it per
    // command — true only for foreColor, false otherwise — makes the
    // produced markup deterministic regardless of click order. Caught
    // live as a real, order-dependent bug: an earlier version always
    // left it on after any first use, which silently turned bold/italic
    // into <span style="font-weight/font-style:...">  — and since the
    // sanitizer's CSS allowlist only permits color/margin (see
    // app/core/rich_text.py), those got stripped, so which formats
    // "worked" depended on the order a user happened to click buttons
    // in, not on which button was clicked.
    document.execCommand("styleWithCSS", false, command === "foreColor" ? "true" : "false");
    document.execCommand(command, false, value);
    onChange(editorRef.current?.innerHTML ?? "");
  }

  return (
    <div className={cn("flex flex-col gap-0", className)}>
      <div className="flex items-center gap-1 rounded-t-md border border-b-0 border-border bg-muted/40 p-1">
        <button
          type="button"
          onMouseDown={(e) => e.preventDefault()}
          onClick={() => exec("bold")}
          aria-label="Bold"
          className="rounded p-1.5 text-muted-foreground hover:bg-muted hover:text-foreground"
        >
          <Bold className="h-4 w-4" />
        </button>
        <button
          type="button"
          onMouseDown={(e) => e.preventDefault()}
          onClick={() => exec("italic")}
          aria-label="Italic"
          className="rounded p-1.5 text-muted-foreground hover:bg-muted hover:text-foreground"
        >
          <Italic className="h-4 w-4" />
        </button>
        <div className="mx-1 h-4 w-px bg-border" />
        {RICH_TEXT_COLOR_SWATCHES.map((color) => (
          <button
            key={color}
            type="button"
            onMouseDown={(e) => e.preventDefault()}
            onClick={() => exec("foreColor", color)}
            aria-label={`Text color ${color}`}
            className="h-5 w-5 rounded-full border border-border"
            style={{ backgroundColor: color }}
          />
        ))}
        <div className="mx-1 h-4 w-px bg-border" />
        <button
          type="button"
          onMouseDown={(e) => e.preventDefault()}
          onClick={() => exec("insertUnorderedList")}
          aria-label="Bullet list"
          className="rounded p-1.5 text-muted-foreground hover:bg-muted hover:text-foreground"
        >
          <List className="h-4 w-4" />
        </button>
        <button
          type="button"
          onMouseDown={(e) => e.preventDefault()}
          onClick={() => exec("outdent")}
          aria-label="Decrease indent"
          className="rounded p-1.5 text-muted-foreground hover:bg-muted hover:text-foreground"
        >
          <IndentDecrease className="h-4 w-4" />
        </button>
        <button
          type="button"
          onMouseDown={(e) => e.preventDefault()}
          onClick={() => exec("indent")}
          aria-label="Increase indent"
          className="rounded p-1.5 text-muted-foreground hover:bg-muted hover:text-foreground"
        >
          <IndentIncrease className="h-4 w-4" />
        </button>
      </div>
      <div
        id={id}
        ref={editorRef}
        contentEditable
        role="textbox"
        aria-multiline="true"
        suppressContentEditableWarning
        autoFocus={autoFocus}
        onInput={() => onChange(editorRef.current?.innerHTML ?? "")}
        data-placeholder={placeholder}
        className={cn(
          "min-h-[100px] w-full rounded-b-md border border-border bg-card px-3 py-2 text-sm",
          "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2",
          "empty:before:text-muted-foreground empty:before:content-[attr(data-placeholder)]",
          RICH_TEXT_CONTENT_CLASSES,
        )}
      />
    </div>
  );
}

const RICH_TEXT_COLOR_SWATCHES = ["#0f172a", "#dc2626", "#2563eb", "#16a34a", "#a855f7"];

//: Tailwind's Preflight reset strips <ul>/<li>'s default list-style and
//: padding — restored explicitly here so a bullet list actually shows
//: bullets, in both the live editor and the readonly display below.
const RICH_TEXT_CONTENT_CLASSES =
  "[&_ul]:list-disc [&_ul]:pl-5 [&_li]:my-0.5 [&_blockquote]:border-l-2 [&_blockquote]:border-border";

/** Readonly rendering of sanitized rich-text HTML — the display half of
 * RichTextEditor. Trusts the HTML it's given (dangerouslySetInnerHTML)
 * because every write path re-sanitizes server-side before persisting
 * (app/core/rich_text.py) — this component is never itself the
 * sanitization boundary. */
export function RichTextDisplay({ html, className }: { html: string; className?: string }) {
  return (
    <div
      dangerouslySetInnerHTML={{ __html: html }}
      className={cn("text-sm [&_span]:inline", RICH_TEXT_CONTENT_CLASSES, className)}
    />
  );
}
