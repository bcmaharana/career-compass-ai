"""Unit tests for app/core/rich_text.py's sanitize_rich_text — a pure
function, tested directly rather than through a service. Expected
outputs mirror Chromium's actual execCommand output (probed live via
Playwright, not guessed) for every toolbar action RichTextEditor
exposes: Bold, Italic, Color, Bullet list, Indent/Outdent.
"""

from __future__ import annotations

import pytest

from app.core.rich_text import plain_text_to_rich_html, sanitize_rich_text

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

    def test_rainbow_marker_span_survives(self) -> None:
        # RichTextEditor's rainbow swatch wraps a selection in this exact
        # marker (see rich-text-editor.tsx's applyRainbow()) — the actual
        # gradient lives in a globals.css rule keyed off this attribute,
        # not in anything the client sends.
        html = '<span data-rainbow="true">rainbow text</span>'
        assert sanitize_rich_text(html) == html

    def test_rainbow_attribute_only_allowed_on_span_not_other_tags(self) -> None:
        # bleach strips a disallowed attribute but keeps the tag/text —
        # data-rainbow was only ever added to span's allowlist.
        assert sanitize_rich_text('<b data-rainbow="true">text</b>') == "<b>text</b>"

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

    def test_javascript_href_is_stripped_but_link_text_and_tag_kept(self) -> None:
        # <a> is now an allowed tag (2026-08-24 link feature) — bleach's
        # `protocols` allowlist strips just the disallowed href
        # attribute, not the whole tag/text (confirmed against bleach's
        # actual behavior, not guessed).
        assert sanitize_rich_text('<a href="javascript:alert(1)">click</a>') == "<a>click</a>"

    def test_data_href_is_stripped_but_link_text_and_tag_kept(self) -> None:
        assert sanitize_rich_text('<a href="data:text/html,evil">click</a>') == "<a>click</a>"

    def test_safe_link_survives_with_target_and_rel(self) -> None:
        # RichTextEditor's applyLink() always sets target="_blank"
        # rel="noreferrer" directly on the element it creates (see that
        # function's own docstring for why, over execCommand).
        html = '<a href="https://example.com" target="_blank" rel="noreferrer">click</a>'
        assert sanitize_rich_text(html) == html

    def test_mailto_link_survives(self) -> None:
        html = '<a href="mailto:test@example.com">mail</a>'
        assert sanitize_rich_text(html) == html

    def test_link_combined_with_bold_and_color_survives(self) -> None:
        html = '<b style="color: red;"><a href="https://example.com">link</a></b>'
        assert sanitize_rich_text(html) == html


class TestPlainTextToRichHtml:
    """plain_text_to_rich_html() reimplements ExperienceSection.tsx's
    DescriptionText bullet-grouping logic in Python, for the one-time
    scripts/migrate_plain_text_descriptions_to_html.py backfill."""

    def test_none_passes_through(self) -> None:
        assert plain_text_to_rich_html(None) is None

    def test_whitespace_only_becomes_none(self) -> None:
        assert plain_text_to_rich_html("   \n  ") is None

    def test_already_html_is_a_no_op(self) -> None:
        # Makes the migration script safe to re-run — anything that
        # already contains a tag is assumed already migrated.
        html = "<p>Already migrated</p>"
        assert plain_text_to_rich_html(html) == html

    def test_single_plain_line_becomes_a_paragraph(self) -> None:
        assert plain_text_to_rich_html("Just one line") == "<p>Just one line</p>"

    def test_multiple_plain_lines_become_separate_paragraphs(self) -> None:
        assert (
            plain_text_to_rich_html("First line\nSecond line")
            == "<p>First line</p><p>Second line</p>"
        )

    def test_blank_lines_are_dropped(self) -> None:
        assert (
            plain_text_to_rich_html("First line\n\n\nSecond line")
            == "<p>First line</p><p>Second line</p>"
        )

    def test_bullet_lines_become_a_real_list(self) -> None:
        assert (
            plain_text_to_rich_html("• First\n• Second")
            == "<ul><li>First</li><li>Second</li></ul>"
        )

    def test_mixed_bullet_and_plain_lines_form_separate_blocks(self) -> None:
        assert (
            plain_text_to_rich_html("Intro line\n• First bullet\n• Second bullet\nOutro line")
            == "<p>Intro line</p><ul><li>First bullet</li><li>Second bullet</li></ul><p>Outro line</p>"
        )

    def test_special_characters_are_html_escaped(self) -> None:
        assert (
            plain_text_to_rich_html("Reduced costs & increased revenue")
            == "<p>Reduced costs &amp; increased revenue</p>"
        )
