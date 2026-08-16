"""Server-side sanitization for the small amount of hand-rolled rich
text this app accepts (Interview Prep's Answer/Discussion fields —
see frontend/src/components/ui/rich-text-editor.tsx). The frontend
editor is a plain contenteditable div with a Bold/Italic/Color/Bullet-
list/Indent toolbar, not a real editor library (this app deliberately
avoids heavy UI kits) — but a contenteditable div can end up holding
*arbitrary* HTML via paste, browser quirks, or a modified client, so
every write is re-sanitized here regardless of what the client sent.
Reads are trusted (rendered via dangerouslySetInnerHTML) precisely
because every write path goes through this function first — this is
the one enforcement point, not a defense someone could route around
by hitting a different endpoint, since InterviewQuestionService/
InterviewTopicService call this for every add/update.

The tag/attribute/CSS allowlists below are deliberately shaped around
Chromium's *actual* execCommand output (probed live, not guessed —
`insertUnorderedList` produces plain `<ul><li>`; `indent` inside a list
nests another `<ul>` directly (no intervening `<li>`); `indent` outside
a list wraps in `<blockquote style="margin: 0 0 0 40px; border: none;
padding: 0px;">`), not a general-purpose HTML allowlist — only `margin`
is kept from that blockquote style (border/padding are dropped by the
CSS sanitizer and simply fall back to a bare `<blockquote>`'s harmless
UA defaults, which is fine since neither was load-bearing for the
indent effect itself).
"""

from __future__ import annotations

import bleach
from bleach.css_sanitizer import CSSSanitizer

_ALLOWED_TAGS = ["b", "strong", "i", "em", "u", "span", "div", "p", "br", "ul", "li", "blockquote"]
#: `style` is allowed on every inline formatting tag, not just span/div/p
#: — combining two formats on the same selection (e.g. bold + color)
#: produces a single tag carrying both, like `<b style="color:...">`,
#: not two nested tags. Confirmed against Chromium's actual output, not
#: guessed: without `b`/`i`/etc. here, that combination silently lost
#: its color (the `style` attribute on `<b>` was simply stripped,
#: bold survived, color didn't) — caught live before shipping.
_ALLOWED_ATTRIBUTES = {tag: ["style"] for tag in ("b", "strong", "i", "em", "u", "span", "div", "p", "blockquote")}
_CSS_SANITIZER = CSSSanitizer(allowed_css_properties=["color", "margin"])


def sanitize_rich_text(value: str | None) -> str | None:
    """Strips everything outside the small bold/italic/color allowlist.
    `None` passes through unchanged (these fields are all optional)."""
    if value is None:
        return None
    cleaned = bleach.clean(
        value,
        tags=_ALLOWED_TAGS,
        attributes=_ALLOWED_ATTRIBUTES,
        css_sanitizer=_CSS_SANITIZER,
        strip=True,
    )
    stripped = cleaned.strip()
    return stripped or None
