"""Unit tests for app/core/rich_text.py's sanitize_rich_text — a pure
function, tested directly rather than through a service. Expected
outputs mirror Chromium's actual execCommand output (probed live via
Playwright, not guessed) for every toolbar action RichTextEditor
exposes: Bold, Italic, Color, Bullet list, Indent/Outdent.
"""

from __future__ import annotations

import pytest

from app.core.rich_text import sanitize_rich_text

pytestmark = pytest.mark.unit


class TestSanitizeRichText:
    def test_none_passes_through(self) -> None:
        assert sanitize_rich_text(None) is None

    def test_whitespace_only_becomes_none(self) -> None:
        assert sanitize_rich_text("   ") is None

    def test_bold_tag_survives(self) -> None:
        assert sanitize_rich_text("<b>bold</b>") == "<b>bold</b>"

    def test_italic_tag_survives(self) -> None:
        assert sanitize_rich_text("<i>italic</i>") == "<i>italic</i>"

    def test_color_span_survives(self) -> None:
        html = '<span style="color: rgb(220, 38, 38);">red text</span>'
        assert sanitize_rich_text(html) == html

    def test_bold_combined_with_color_keeps_both(self) -> None:
        # Chromium emits a single tag carrying both formats when applied
        # to the same selection, not two nested tags — `style` must be
        # allowed directly on <b>, not just <span>/<div>/<p>.
        html = '<b style="color: rgb(220, 38, 38);">bold and red</b>'
        assert sanitize_rich_text(html) == html

    def test_bullet_list_survives(self) -> None:
        html = "<ul><li>First item</li><li>Second item</li></ul>"
        assert sanitize_rich_text(html) == html

    def test_nested_bullet_list_survives(self) -> None:
        # Chromium's actual output for "indent" while inside a list —
        # a nested <ul> directly inside <ul>, no intervening <li>.
        html = "<ul><ul><li>First item</li></ul></ul>"
        assert sanitize_rich_text(html) == html

    def test_indent_blockquote_keeps_margin_only(self) -> None:
        html = (
            '<blockquote style="margin: 0 0 0 40px; border: none; padding: 0px;">'
            "indented text</blockquote>"
        )
        assert sanitize_rich_text(html) == '<blockquote style="margin: 0 0 0 40px;">indented text</blockquote>'

    def test_disallowed_font_tag_is_stripped_but_text_kept(self) -> None:
        # The exact class of bug this app hit live: Chromium's legacy
        # foreColor implementation (without styleWithCSS) emits <font
        # color="...">, which isn't in the allowlist — the tag itself
        # must disappear, not survive with the color silently dropped
        # and no error raised anywhere.
        assert sanitize_rich_text('<font color="red">text</font>') == "text"

    def test_disallowed_css_property_is_stripped_but_color_kept(self) -> None:
        html = '<span style="color: red; background: url(x); font-size: 40px;">text</span>'
        assert sanitize_rich_text(html) == '<span style="color: red;">text</span>'

    def test_script_tag_is_stripped(self) -> None:
        assert sanitize_rich_text("<b>Bold</b><script>alert(1)</script>") == "<b>Bold</b>alert(1)"

    def test_img_onerror_is_stripped(self) -> None:
        assert sanitize_rich_text('<img src=x onerror="alert(1)">text') == "text"

    def test_javascript_href_is_stripped(self) -> None:
        assert sanitize_rich_text('<a href="javascript:alert(1)">click</a>') == "click"
