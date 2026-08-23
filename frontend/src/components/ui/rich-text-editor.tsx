import { cn } from "@/lib/utils";
import { Bold, IndentDecrease, IndentIncrease, Italic, Link2, List, Underline, Unlink } from "lucide-react";
import { useEffect, useRef, useState } from "react";

/**
 * A small hand-rolled rich-text editor (Bold/Italic/Underline/Link/
 * text color/bullet-list/indent) — not a real editor library. Matches
 * this app's "no heavy UI kit" convention (see Dialog's own docstring).
 * Backed by a plain contenteditable div driven by the deprecated-but-
 * still-universally-supported document.execCommand for most formats;
 * Link (2026-08-24: "highlight/select a text string and be able to add
 * a link to that text string in any box we have text") is built by
 * directly wrapping the selection's Range in a real `<a>` instead — see
 * applyLink's own docstring for why.
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

//: A bare host/path like "example.com" or "linkedin.com/in/x" has no
//: scheme for a browser to resolve as absolute — left as-is, an <a
//: href="example.com"> resolves RELATIVE to the current page, not as an
//: external link (direct 2026-08-24 correction: "the url doesn't need
//: to have https://"). Same scheme-detection regex as this app's other
//: free-text-URL entry point (app/domain/interview_prep/entities.py's
//: is_safe_reference_url) — a leading ALPHA then any mix of
//: letters/digits/+/-/. before a colon; a value that already has one
//: (https:, mailto:, ...) is left untouched, anything else gets
//: "https://" prepended.
const _SCHEME_RE = /^[a-zA-Z][a-zA-Z0-9+.-]*:/;

//: Requires a real-looking domain (at least one label, then a final
//: TLD of 2+ letters — "example.com", "sub.example.co.uk", optionally
//: followed by a port/path/query/fragment) before it's trusted to get
//: "https://" prepended (direct 2026-08-24 follow-up: "The URL must
//: check if .com or .xxx is there or not") — rejects plain non-URL text
//: like "hello" that would otherwise silently become a broken
//: "https://hello" link. Only applied when there's no explicit scheme
//: already (mailto:/etc. isn't a domain-shaped string at all); an
//: explicit scheme is trusted as-is, same as normalizeLinkUrl above.
const _DOMAIN_LIKE_RE =
  /^[a-zA-Z0-9](?:[a-zA-Z0-9-]*[a-zA-Z0-9])?(?:\.[a-zA-Z0-9](?:[a-zA-Z0-9-]*[a-zA-Z0-9])?)*\.[a-zA-Z]{2,}(?::\d+)?(?:[/?#].*)?$/;

function isLikelyValidLinkUrl(url: string): boolean {
  return _SCHEME_RE.test(url) || _DOMAIN_LIKE_RE.test(url);
}

function normalizeLinkUrl(url: string): string {
  return _SCHEME_RE.test(url) ? url : `https://${url}`;
}

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

  // Bold/Italic/Underline have no visible "this is currently active"
  // state — confirmed live as the real driver behind a "bold sometimes
  // applies, sometimes doesn't" report: execCommand's toggle is
  // perfectly deterministic (queryCommandState('bold') at the current
  // selection decides on/off), but a selection spanning a MIX of
  // already-bold and not-bold text toggles the *entire* selection to
  // whichever state it wasn't already fully in — a first click can make
  // it all bold, and clicking again on that same (now fully bold)
  // selection un-bolds it, which reads as "random" with zero visual cue
  // beforehand about which way it's about to go. Tracking + highlighting
  // the actual state turns that into predictable, visible behavior
  // instead of trying to change execCommand's own (correct) semantics.
  const [activeFormats, setActiveFormats] = useState({
    bold: false,
    italic: false,
    underline: false,
    link: false,
  });

  function refreshActiveFormats() {
    if (!editorRef.current) return;
    const selection = window.getSelection();
    // Only reflect this editor's own state — selectionchange is a
    // document-global event, and a page can have several
    // RichTextEditor instances open at once (see e.g. Interview Prep's
    // per-question answer editors).
    if (!selection || !editorRef.current.contains(selection.anchorNode)) return;
    setActiveFormats({
      bold: document.queryCommandState("bold"),
      italic: document.queryCommandState("italic"),
      underline: document.queryCommandState("underline"),
      // queryCommandState has no "am I on a link" concept — unlink has
      // no on/off state to toggle, so queryCommandEnabled (true whenever
      // unlink would actually do something, i.e. the selection/cursor
      // intersects an <a>) is the correct signal here instead.
      link: document.queryCommandEnabled("unlink"),
    });
  }

  useEffect(() => {
    if (editorRef.current) {
      editorRef.current.innerHTML = initialValueRef.current;
    }
    // Intentionally empty deps — see the component docstring on why
    // this must only ever run once, on mount.
  }, []);

  useEffect(() => {
    document.addEventListener("selectionchange", refreshActiveFormats);
    return () => document.removeEventListener("selectionchange", refreshActiveFormats);
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
    refreshActiveFormats();
  }

  /** The "rainbow" swatch is a genuine multi-color gradient fill, which
   * document.execCommand('foreColor', ...) can't produce — that command
   * only ever accepts a single solid color. Applied instead by directly
   * wrapping the current Selection's Range in a `<span
   * data-rainbow="true">` marker; the actual gradient lives in a
   * stylesheet rule (globals.css's `[data-rainbow="true"]`), not in
   * anything generated here, so the sanitizer only has to trust one
   * fixed attribute+value rather than arbitrary CSS. `surroundContents`
   * throws for a range that partially selects a non-text node (e.g. a
   * selection spanning across an existing <b> boundary) — extractContents
   * + re-insert handles any selection shape, at the cost of losing node
   * identity for whatever was selected, which doesn't matter here since
   * nothing tracks node references across an edit. */
  function applyRainbow() {
    editorRef.current?.focus();
    const selection = window.getSelection();
    if (!selection || selection.rangeCount === 0) return;
    const range = selection.getRangeAt(0);
    if (range.collapsed) return;
    if (!editorRef.current?.contains(range.commonAncestorContainer)) return;

    const span = document.createElement("span");
    span.setAttribute("data-rainbow", "true");
    try {
      range.surroundContents(span);
    } catch {
      const contents = range.extractContents();
      span.appendChild(contents);
      range.insertNode(span);
    }
    onChange(editorRef.current?.innerHTML ?? "");
  }

  // Highlight a text string, add a link to it (direct 2026-08-24
  // request: "in any box we have text"). Built the same way as
  // applyRainbow above — directly wrapping the selection's Range in a
  // real `<a>` — rather than document.execCommand('createLink', ...),
  // specifically so target="_blank"/rel="noreferrer" can be set on the
  // element deterministically rather than relying on execCommand's own
  // more limited output shape (no attribute control at all). The
  // popover steals focus the moment its URL input is clicked, which
  // collapses/changes window.getSelection() on most browsers — the
  // Range must be captured and cloned at "Link" click time, before that
  // happens, and reused later at "Apply" time rather than re-queried.
  const [linkPopoverOpen, setLinkPopoverOpen] = useState(false);
  const [linkUrlDraft, setLinkUrlDraft] = useState("");
  const [linkUrlError, setLinkUrlError] = useState(false);
  const savedRangeRef = useRef<Range | null>(null);
  const linkPopoverRef = useRef<HTMLDivElement>(null);
  const linkUrlInputRef = useRef<HTMLInputElement>(null);

  function openLinkPopover() {
    const selection = window.getSelection();
    if (!selection || selection.rangeCount === 0) return;
    const range = selection.getRangeAt(0);
    if (range.collapsed) return; // nothing highlighted — matches the rainbow swatch's own silent no-op
    if (!editorRef.current?.contains(range.commonAncestorContainer)) return;
    savedRangeRef.current = range.cloneRange();
    setLinkUrlDraft("");
    setLinkUrlError(false);
    setLinkPopoverOpen(true);
  }

  function applyLink(event: React.FormEvent) {
    event.preventDefault();
    const range = savedRangeRef.current;
    const trimmed = linkUrlDraft.trim();
    if (!range || !trimmed) return;
    if (!isLikelyValidLinkUrl(trimmed)) {
      setLinkUrlError(true);
      return;
    }
    const url = normalizeLinkUrl(trimmed);
    editorRef.current?.focus();

    const anchor = document.createElement("a");
    anchor.setAttribute("href", url);
    anchor.setAttribute("target", "_blank");
    anchor.setAttribute("rel", "noreferrer");
    try {
      range.surroundContents(anchor);
    } catch {
      const contents = range.extractContents();
      anchor.appendChild(contents);
      range.insertNode(anchor);
    }
    onChange(editorRef.current?.innerHTML ?? "");
    refreshActiveFormats();
    setLinkPopoverOpen(false);
    savedRangeRef.current = null;
  }

  function removeLink() {
    exec("unlink");
  }

  useEffect(() => {
    if (!linkPopoverOpen) return;
    linkUrlInputRef.current?.focus();
    function handlePointerDown(event: MouseEvent) {
      if (linkPopoverRef.current && !linkPopoverRef.current.contains(event.target as Node)) {
        setLinkPopoverOpen(false);
      }
    }
    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") setLinkPopoverOpen(false);
    }
    document.addEventListener("mousedown", handlePointerDown);
    document.addEventListener("keydown", handleKeyDown);
    return () => {
      document.removeEventListener("mousedown", handlePointerDown);
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, [linkPopoverOpen]);

  return (
    <div className="flex flex-col gap-0">
      <div className="flex items-center gap-1 rounded-t-md border border-b-0 border-border bg-muted/40 p-1">
        <button
          type="button"
          onMouseDown={(e) => e.preventDefault()}
          onClick={() => exec("bold")}
          aria-label="Bold"
          aria-pressed={activeFormats.bold}
          title={activeFormats.bold ? "Bold (currently on for this selection)" : "Bold"}
          className={cn(
            "rounded p-1.5 hover:bg-muted",
            activeFormats.bold
              ? "bg-muted text-foreground"
              : "text-muted-foreground hover:text-foreground",
          )}
        >
          <Bold className="h-4 w-4" />
        </button>
        <button
          type="button"
          onMouseDown={(e) => e.preventDefault()}
          onClick={() => exec("italic")}
          aria-label="Italic"
          aria-pressed={activeFormats.italic}
          title={activeFormats.italic ? "Italic (currently on for this selection)" : "Italic"}
          className={cn(
            "rounded p-1.5 hover:bg-muted",
            activeFormats.italic
              ? "bg-muted text-foreground"
              : "text-muted-foreground hover:text-foreground",
          )}
        >
          <Italic className="h-4 w-4" />
        </button>
        <button
          type="button"
          onMouseDown={(e) => e.preventDefault()}
          onClick={() => exec("underline")}
          aria-label="Underline"
          aria-pressed={activeFormats.underline}
          title={activeFormats.underline ? "Underline (currently on for this selection)" : "Underline"}
          className={cn(
            "rounded p-1.5 hover:bg-muted",
            activeFormats.underline
              ? "bg-muted text-foreground"
              : "text-muted-foreground hover:text-foreground",
          )}
        >
          <Underline className="h-4 w-4" />
        </button>
        <div className="relative">
          <button
            type="button"
            onMouseDown={(e) => e.preventDefault()}
            onClick={openLinkPopover}
            aria-label="Add link"
            aria-pressed={linkPopoverOpen}
            title="Add link (select text first)"
            className={cn(
              "rounded p-1.5 hover:bg-muted",
              linkPopoverOpen
                ? "bg-muted text-foreground"
                : "text-muted-foreground hover:text-foreground",
            )}
          >
            <Link2 className="h-4 w-4" />
          </button>
          {linkPopoverOpen && (
            <div
              ref={linkPopoverRef}
              className="absolute left-0 top-full z-30 mt-1 flex w-64 flex-col gap-1 rounded-md border border-border bg-card p-2 shadow-md"
            >
              <form className="flex w-full items-center gap-1.5" onSubmit={applyLink}>
                <input
                  ref={linkUrlInputRef}
                  // Plain text, not type="url" — native URL validation
                  // requires a scheme, which would block exactly the
                  // "example.com" case normalizeLinkUrl() exists to
                  // accept (direct 2026-08-24 correction: "the url
                  // doesn't need to have https://").
                  type="text"
                  value={linkUrlDraft}
                  onChange={(e) => {
                    setLinkUrlDraft(e.target.value);
                    if (linkUrlError) setLinkUrlError(false);
                  }}
                  placeholder="example.com or https://..."
                  className={cn(
                    "h-7 min-w-0 flex-1 rounded border bg-background px-2 text-xs focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                    linkUrlError ? "border-destructive" : "border-border",
                  )}
                />
                <button
                  type="submit"
                  className="rounded bg-foreground px-2 py-1 text-xs font-medium text-background hover:opacity-90"
                >
                  Add
                </button>
              </form>
              {linkUrlError && (
                <p role="alert" className="text-xs text-destructive">
                  Enter a real web address, like example.com
                </p>
              )}
            </div>
          )}
        </div>
        <button
          type="button"
          onMouseDown={(e) => e.preventDefault()}
          onClick={removeLink}
          disabled={!activeFormats.link}
          aria-label="Remove link"
          title={activeFormats.link ? "Remove link" : "Place the cursor in a link to remove it"}
          className={cn(
            "rounded p-1.5 hover:bg-muted",
            activeFormats.link
              ? "text-muted-foreground hover:text-foreground"
              : "text-muted-foreground/40 hover:bg-transparent",
          )}
        >
          <Unlink className="h-4 w-4" />
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
        <button
          type="button"
          onMouseDown={(e) => e.preventDefault()}
          onClick={applyRainbow}
          aria-label="Text color rainbow"
          title="Rainbow (select text first)"
          className="h-5 w-5 rounded-full border border-border"
          style={{
            background:
              "linear-gradient(90deg, #a855f7 12.5%, #3b82f6 37.5%, #22c55e 58.33%, #fdba74 75%, #fca5a5 91.67%)",
          }}
        />
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
          className,
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
  "[&_ul]:list-disc [&_ul]:pl-5 [&_li]:my-0.5 " +
  "[&_a]:text-accent [&_a]:underline [&_a]:underline-offset-2 [&_a]:hover:text-accent/80";

/** Readonly rendering of sanitized rich-text HTML — the display half of
 * RichTextEditor. Trusts the HTML it's given (dangerouslySetInnerHTML)
 * because every write path re-sanitizes server-side before persisting
 * (app/core/rich_text.py) — this component is never itself the
 * sanitization boundary.
 *
 * `whitespace-pre-line` is a defensive addition, not load-bearing for
 * real HTML content (already broken into block-level <p>/<div>/<li>
 * elements, which don't need it) — it exists for the one case where a
 * field can legitimately hold *tag-free* plain text with real `\n`
 * characters: Resume Intelligence's AI-extracted descriptions are
 * deliberately left as plain text on merge (see
 * resume_merge_service.py's own docstring), and bare `\n` is otherwise
 * ignorable whitespace in HTML — without this, a multi-line merged
 * description would collapse into one run-on paragraph instead of
 * preserving line breaks the way every plain-text field in this app
 * already did before rich text existed. */
export function RichTextDisplay({ html, className }: { html: string; className?: string }) {
  return (
    <div
      dangerouslySetInnerHTML={{ __html: html }}
      className={cn(
        "whitespace-pre-line text-sm [&_span]:inline",
        RICH_TEXT_CONTENT_CLASSES,
        className,
      )}
    />
  );
}
