"""Walks sanitized rich-text HTML (see app/core/rich_text.py's
allowlist) into a flat, format-agnostic structure that both
resume_docx_builder.py and resume_pdf_builder.py render from — replaces
the old plain-text "a line starting with '• ' is a bullet" parsing
(description_lines()/strip_bullet_marker() in resume_data.py) now that
these fields store real HTML.

Built on the stdlib html.parser.HTMLParser rather than a third-party
HTML/XML library — the sanitizer's allowlist is already narrow
(b/strong/i/em/u/span/div/p/br/ul/li/blockquote, `style` limited to
color/margin, one fixed data-rainbow attribute — see rich_text.py), so
a small hand-rolled walker covers every shape this app can actually
produce without a new dependency.

Rainbow text (`<span data-rainbow="true">`, RichTextEditor's gradient
swatch) has no Word/PDF equivalent — gradient text isn't representable
in either format — so it deliberately renders as plain, unstyled text
here rather than erroring or approximating a solid color.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from html.parser import HTMLParser

#: Tags the sanitizer allows a `style` attribute on — the only ones a
#: color can ever appear on (li/ul/br never carry `style`, see
#: rich_text.py's _ALLOWED_ATTRIBUTES).
_STYLEABLE_TAGS = frozenset({"b", "strong", "i", "em", "u", "span", "div", "p", "blockquote"})

_COLOR_RE = re.compile(r"color\s*:\s*([^;]+)", re.IGNORECASE)
_RGB_RE = re.compile(r"rgb\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\)", re.IGNORECASE)


@dataclass(slots=True)
class RichRun:
    """One contiguous span of text sharing the same formatting."""

    text: str
    bold: bool = False
    italic: bool = False
    underline: bool = False
    #: "#rrggbb", already resolved from the browser's rgb(...)/hex output.
    #: None for unstyled text AND for rainbow text (see module docstring).
    color: str | None = None


@dataclass(slots=True)
class RichBlock:
    """One paragraph/list-item worth of runs, in document order."""

    runs: list[RichRun] = field(default_factory=list)
    bullet: bool = False
    indent: bool = False


def _normalize_color(raw: str) -> str | None:
    value = raw.strip()
    match = _RGB_RE.match(value)
    if match:
        r, g, b = (int(part) for part in match.groups())
        return f"#{r:02x}{g:02x}{b:02x}"
    if value.startswith("#"):
        return value
    return None  # named colors — not produced by the editor's toolbar, skip rather than guess


class _RichTextWalker(HTMLParser):
    """Single-use: feed() once (via parse_rich_text), then read .blocks."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.blocks: list[RichBlock] = []
        self._current_block: RichBlock | None = None
        self._bold = 0
        self._italic = 0
        self._underline = 0
        #: Only pushed/popped for _STYLEABLE_TAGS — li/ul/br never carry
        #: `style`, so they're excluded to keep this stack exactly
        #: balanced against handle_endtag (br in particular has no
        #: matching end tag to pop on).
        self._color_stack: list[str | None] = []
        self._bullet_depth = 0
        self._indent_depth = 0

    def _ensure_block(self) -> RichBlock:
        if self._current_block is None:
            self._current_block = RichBlock(
                bullet=self._bullet_depth > 0, indent=self._indent_depth > 0
            )
            self.blocks.append(self._current_block)
        return self._current_block

    def _close_block(self) -> None:
        self._current_block = None

    @property
    def _current_color(self) -> str | None:
        for color in reversed(self._color_stack):
            if color is not None:
                return color
        return None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "br":
            self._close_block()
            return
        if tag == "ul":
            self._bullet_depth += 1
            return
        if tag == "li":
            self._close_block()
            self._ensure_block()
            return
        if tag == "blockquote":
            self._indent_depth += 1
            self._close_block()
            return
        if tag in ("p", "div"):
            self._close_block()

        if tag in _STYLEABLE_TAGS:
            attr_dict = dict(attrs)
            if tag == "b" or tag == "strong":
                self._bold += 1
            elif tag == "i" or tag == "em":
                self._italic += 1
            elif tag == "u":
                self._underline += 1

            # A rainbow span is marked but deliberately carries no color
            # here — see module docstring.
            if tag == "span" and attr_dict.get("data-rainbow") == "true":
                self._color_stack.append(None)
            else:
                style = attr_dict.get("style") or ""
                match = _COLOR_RE.search(style)
                self._color_stack.append(_normalize_color(match.group(1)) if match else None)

    def handle_endtag(self, tag: str) -> None:
        if tag in ("br", "ul"):
            if tag == "ul":
                self._bullet_depth = max(0, self._bullet_depth - 1)
            return
        if tag == "li":
            self._close_block()
            return
        if tag == "blockquote":
            self._indent_depth = max(0, self._indent_depth - 1)
            self._close_block()
            return
        if tag in ("p", "div"):
            self._close_block()

        if tag in _STYLEABLE_TAGS:
            if tag == "b" or tag == "strong":
                self._bold = max(0, self._bold - 1)
            elif tag == "i" or tag == "em":
                self._italic = max(0, self._italic - 1)
            elif tag == "u":
                self._underline = max(0, self._underline - 1)
            if self._color_stack:
                self._color_stack.pop()

    def handle_data(self, data: str) -> None:
        if not data:
            return
        block = self._ensure_block()
        block.runs.append(
            RichRun(
                text=data,
                bold=self._bold > 0,
                italic=self._italic > 0,
                underline=self._underline > 0,
                color=self._current_color,
            )
        )


def parse_rich_text(html: str | None) -> list[RichBlock]:
    """Parses sanitized rich-text HTML into a flat list of RichBlock —
    one per paragraph/list-item, in document order. None/empty input
    returns an empty list. Blocks with no non-whitespace text (a stray
    `<p></p>`, etc.) are dropped — nothing downstream should render a
    blank line."""
    if not html:
        return []
    walker = _RichTextWalker()
    walker.feed(html)
    walker.close()
    return [block for block in walker.blocks if any(run.text.strip() for run in block.runs)]


def plain_text(html: str | None) -> str:
    """Flattened plain text, no formatting or bullets — for a field that
    needs to sit inline with other plain text (e.g. the resume header's
    "{role_label} — {headline}" subtitle line) rather than render as its
    own rich block. Runs within a block are concatenated directly (the
    original inter-word whitespace already lives in each run's own
    text); blocks (paragraph breaks) are joined with a single space
    since this is meant for a one-line context, not a multi-paragraph
    one."""
    blocks = parse_rich_text(html)
    return " ".join("".join(run.text for run in block.runs) for block in blocks).strip()
