"""Server-side sanitization for the hand-rolled rich text this app
accepts app-wide (Career Profile's headline/summary/experience/etc.,
Interview Prep's Answer/Discussion/Article content, Showcase Page
content columns, Learning Log notes — see
frontend/src/components/ui/rich-text-editor.tsx, the one shared editor
component every one of these fields renders through). The frontend
editor is a plain contenteditable div with a Bold/Italic/Underline/
Link/Color/Bullet-list/Indent toolbar, not a real editor library (this
app deliberately avoids heavy UI kits) — but a contenteditable div can
end up holding *arbitrary* HTML via paste, browser quirks, or a
modified client, so every write is re-sanitized here regardless of what
the client sent. Reads are trusted (rendered via dangerouslySetInnerHTML)
precisely because every write path goes through this function first —
this is the one enforcement point, not a defense someone could route
around by hitting a different endpoint, since every domain service that
persists rich text calls this for every add/update.

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

import html as _html
import re

import bleach
from bleach.css_sanitizer import CSSSanitizer

_ALLOWED_TAGS = ["b", "strong", "i", "em", "u", "span", "div", "p", "br", "ul", "ol", "li", "blockquote", "a"]
#: `style` is allowed on every inline formatting tag, not just span/div/p
#: — combining two formats on the same selection (e.g. bold + color)
#: produces a single tag carrying both, like `<b style="color:...">`,
#: not two nested tags. Confirmed against Chromium's actual output, not
#: guessed: without `b`/`i`/etc. here, that combination silently lost
#: its color (the `style` attribute on `<b>` was simply stripped,
#: bold survived, color didn't) — caught live before shipping.
_ALLOWED_ATTRIBUTES: dict[str, list[str]] = {
    tag: ["style"] for tag in ("b", "strong", "i", "em", "u", "span", "div", "p", "blockquote", "ul", "ol")
}
#: A link (2026-08-24: "highlight/select a text string and add a link to
#: that text string in any box we have text") is built client-side by
#: directly wrapping the selection's Range in a real `<a>` element
#: (@bcmaharana/ui-kit's RichTextEditor.applyLink — same
#: direct-DOM-manipulation approach the "rainbow" color swatch already
#: uses, not document.execCommand('createLink'), specifically so
#: target="_blank"/rel="noreferrer" can be set deterministically rather
#: than relying on execCommand's own, more limited output shape).
#: `href`'s scheme is validated below via bleach's `protocols` allowlist
#: — same three schemes (http/https/mailto) as
#: app/domain/interview_prep/entities.py's is_safe_reference_url, this
#: app's other free-text-URL enforcement point.
_ALLOWED_ATTRIBUTES["a"] = ["href", "target", "rel", "style"]
_ALLOWED_PROTOCOLS = ["http", "https", "mailto"]
#: Gradient text-color presets (rainbow/sunset/ocean — RichTextEditor's
#: GRADIENT_PRESETS) are a genuine CSS gradient on the glyphs, which
#: document.execCommand can't apply as an inline style (foreColor only
#: accepts a solid color) — so each is marked with one of these fixed
#: attribute+value pairs instead, and the actual gradient lives in a
#: stylesheet rule ([data-rainbow="true"]/[data-gradient="sunset"]/etc.
#: in globals.css), not in anything the client sends. `data-gradient`'s
#: VALUE still needs an enum check below (bleach only validates that the
#: ATTRIBUTE is allowed on the tag, not which value it holds) — an
#: unrecognized value is stripped by _strip_invalid_data_gradient rather
#: than trusted, so a client can't smuggle an arbitrary attribute value
#: through even though the attribute name itself is allowlisted.
_ALLOWED_ATTRIBUTES["span"].append("data-rainbow")
_ALLOWED_ATTRIBUTES["span"].append("data-gradient")
_ALLOWED_GRADIENT_NAMES = {"rainbow", "sunset", "ocean"}
#: font-family/background-color/text-align/list-style-type all take
#: simple keyword/color/string values with no CSS function capable of
#: fetching a URL (unlike e.g. background-image) — safe to allow by
#: property name alone, same as the pre-existing color/margin entries.
_CSS_SANITIZER = CSSSanitizer(
    allowed_css_properties=[
        "color",
        "margin",
        "background-color",
        "font-family",
        "font-size",
        "text-align",
        "list-style-type",
    ]
)
_DATA_GRADIENT_RE = re.compile(r'data-gradient="([^"]*)"')


def _strip_invalid_data_gradient(html: str) -> str:
    def replace(match: re.Match[str]) -> str:
        return match.group(0) if match.group(1) in _ALLOWED_GRADIENT_NAMES else ""

    return _DATA_GRADIENT_RE.sub(replace, html)


def sanitize_rich_text(value: str | None) -> str | None:
    """Strips everything outside the rich-text formatting allowlist.
    `None` passes through unchanged (these fields are all optional)."""
    if value is None:
        return None
    cleaned = bleach.clean(
        value,
        tags=_ALLOWED_TAGS,
        attributes=_ALLOWED_ATTRIBUTES,
        protocols=_ALLOWED_PROTOCOLS,
        css_sanitizer=_CSS_SANITIZER,
        strip=True,
    )
    cleaned = _strip_invalid_data_gradient(cleaned)
    stripped = cleaned.strip()
    return stripped or None


def plain_text_to_rich_html(text: str | None) -> str | None:
    """Converts a legacy plain-text description — optionally using the
    "a line starting with '• ' is a bullet" convention that
    frontend/src/features/career-profile/ExperienceSection.tsx's
    DescriptionText component (and the resume-extraction AI prompt)
    already established — into the equivalent sanitized rich-text HTML
    this app now stores for these fields. Reimplements DescriptionText's
    exact grouping logic in Python: split on newlines, drop blank
    lines, detect the bullet prefix, group consecutive same-type lines
    into blocks, and render bullet blocks as a real `<ul><li>` list and
    plain blocks as one `<p>` per line.

    Used only by `scripts/migrate_plain_text_descriptions_to_html.py`'s
    one-time backfill of existing data — resume-merge deliberately does
    NOT call this (see resume_merge_service.py's own docstring): freshly
    AI-extracted text is left as plain text until a user reformats it by
    hand in the rich-text editor.

    A no-op on anything that already looks like HTML (contains a `<`),
    so re-running the migration script is always safe.
    """
    if text is None:
        return None
    if "<" in text:
        return text

    blocks: list[tuple[bool, list[str]]] = []
    for raw_line in text.split("\n"):
        line = raw_line.strip()
        if not line:
            continue
        bullet = line.startswith("• ")
        line_text = line[2:] if bullet else line
        if blocks and blocks[-1][0] is bullet:
            blocks[-1][1].append(line_text)
        else:
            blocks.append((bullet, [line_text]))

    if not blocks:
        return None

    html_parts: list[str] = []
    for bullet, lines in blocks:
        if bullet:
            items = "".join(f"<li>{_html.escape(line)}</li>" for line in lines)
            html_parts.append(f"<ul>{items}</ul>")
        else:
            html_parts.extend(f"<p>{_html.escape(line)}</p>" for line in lines)

    return sanitize_rich_text("".join(html_parts))
