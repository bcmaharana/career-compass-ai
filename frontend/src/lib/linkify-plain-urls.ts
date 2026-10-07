/** Turns bare HTTP(S) URLs into links inside already-sanitized rich text.
 * Existing anchors and code are left untouched. */
export function linkifyPlainUrls(html: string): string {
  const parsed = new DOMParser().parseFromString(html, "text/html");
  const walker = parsed.createTreeWalker(parsed.body, NodeFilter.SHOW_TEXT);
  const textNodes: Text[] = [];
  while (walker.nextNode()) {
    const node = walker.currentNode as Text;
    if (!node.parentElement?.closest("a, code, pre, script, style")) textNodes.push(node);
  }

  const urlPattern = /https?:\/\/[^\s<>"']+/gi;
  for (const textNode of textNodes) {
    const text = textNode.nodeValue ?? "";
    urlPattern.lastIndex = 0;
    if (!urlPattern.test(text)) continue;
    urlPattern.lastIndex = 0;
    const fragment = parsed.createDocumentFragment();
    let cursor = 0;
    for (const match of text.matchAll(urlPattern)) {
      const rawUrl = match[0];
      const url = rawUrl.replace(/[.,!?;:]+$/, "");
      if (!url) continue;
      const start = match.index ?? 0;
      if (start > cursor) fragment.append(text.slice(cursor, start));
      const anchor = parsed.createElement("a");
      anchor.href = url;
      anchor.target = "_blank";
      anchor.rel = "noopener noreferrer";
      anchor.textContent = url;
      fragment.append(anchor, rawUrl.slice(url.length));
      cursor = start + rawUrl.length;
    }
    if (cursor < text.length) fragment.append(text.slice(cursor));
    textNode.replaceWith(fragment);
  }

  return parsed.body.innerHTML;
}
