/**
 * Flattens rich-text HTML (Headline, Executive Summary, and the other
 * fields RichTextEditor/RichTextDisplay handle — see CLAUDE.md's
 * "Rich-text editor rollout" entry) down to plain text, for the rare
 * spot that needs to embed a rich-text field's *content* somewhere
 * that isn't itself rendered as HTML — e.g. weaving a headline into an
 * LLM prompt string (suggested-prompts.ts), where the raw markup would
 * otherwise show up as literal `<span style="...">` noise in both the
 * composed chat message and the model's own context.
 *
 * A detached `<div>` (never inserted into the document) is used purely
 * as a parser — setting `innerHTML` never executes embedded scripts on
 * an unattached element, and this only ever runs on server-sanitized
 * content (see `app/core/rich_text.py`) besides.
 */
export function stripHtml(html: string): string {
  const div = document.createElement("div");
  div.innerHTML = html;
  return (div.textContent ?? "").trim();
}
