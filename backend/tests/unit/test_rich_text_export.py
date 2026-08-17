"""Unit tests for app/adapters/documents/rich_text_export.py — the
HTML -> (bold/italic/color/bullet/indent) block walker that both
resume_docx_builder.py and resume_pdf_builder.py render from.
"""

from __future__ import annotations

import pytest

from app.adapters.documents.rich_text_export import parse_rich_text, plain_text

pytestmark = pytest.mark.unit


class TestParseRichText:
    def test_none_returns_empty(self) -> None:
        assert parse_rich_text(None) == []

    def test_empty_string_returns_empty(self) -> None:
        assert parse_rich_text("") == []

    def test_bare_untagged_text_becomes_one_plain_block(self) -> None:
        blocks = parse_rich_text("Just some text")
        assert len(blocks) == 1
        assert blocks[0].bullet is False
        assert blocks[0].indent is False
        assert [r.text for r in blocks[0].runs] == ["Just some text"]

    def test_two_paragraphs_become_two_blocks(self) -> None:
        blocks = parse_rich_text("<p>First</p><p>Second</p>")
        assert [b.runs[0].text for b in blocks] == ["First", "Second"]

    def test_divs_become_separate_blocks_too(self) -> None:
        # Chrome's default per-line wrapper on Enter in a contenteditable.
        blocks = parse_rich_text("<div>line one</div><div>line two</div>")
        assert [b.runs[0].text for b in blocks] == ["line one", "line two"]

    def test_bullet_list_items_are_marked_and_separated(self) -> None:
        blocks = parse_rich_text("<ul><li>First item</li><li>Second item</li></ul>")
        assert len(blocks) == 2
        assert all(b.bullet for b in blocks)
        assert [b.runs[0].text for b in blocks] == ["First item", "Second item"]

    def test_nested_list_bullets_still_marked_bullet(self) -> None:
        # Chromium's actual "indent inside a list" output — a bare
        # nested <ul>, no intervening <li> (see rich_text.py's own
        # docstring on this exact shape).
        blocks = parse_rich_text("<ul><ul><li>Nested item</li></ul></ul>")
        assert len(blocks) == 1
        assert blocks[0].bullet is True

    def test_blockquote_marks_the_block_indented(self) -> None:
        blocks = parse_rich_text('<blockquote style="margin: 0 0 0 40px;">indented</blockquote>')
        assert len(blocks) == 1
        assert blocks[0].indent is True
        assert blocks[0].bullet is False

    def test_bold_run_is_flagged(self) -> None:
        blocks = parse_rich_text("<b>bold text</b>")
        assert blocks[0].runs[0].bold is True
        assert blocks[0].runs[0].italic is False

    def test_strong_and_em_are_treated_the_same_as_b_and_i(self) -> None:
        blocks = parse_rich_text("<strong>bold</strong> <em>italic</em>")
        assert blocks[0].runs[0].bold is True
        assert blocks[0].runs[2].italic is True

    def test_underline_run_is_flagged(self) -> None:
        blocks = parse_rich_text("<u>underlined</u>")
        assert blocks[0].runs[0].underline is True

    def test_color_is_extracted_and_normalized_from_rgb(self) -> None:
        # This is Chromium's actual real output shape for the color
        # swatch (styleWithCSS mode) — confirmed live, not guessed.
        blocks = parse_rich_text('<span style="color: rgb(220, 38, 38);">red text</span>')
        assert blocks[0].runs[0].color == "#dc2626"

    def test_bold_and_color_combined_on_one_tag_both_apply(self) -> None:
        blocks = parse_rich_text('<b style="color: rgb(220, 38, 38);">bold and red</b>')
        run = blocks[0].runs[0]
        assert run.bold is True
        assert run.color == "#dc2626"

    def test_rainbow_span_carries_no_color(self) -> None:
        # Gradient text has no Word/PDF equivalent — deliberately
        # unstyled rather than approximated with a solid color.
        blocks = parse_rich_text('<span data-rainbow="true">rainbow text</span>')
        assert blocks[0].runs[0].color is None
        assert blocks[0].runs[0].bold is False

    def test_color_does_not_leak_past_its_own_tag(self) -> None:
        blocks = parse_rich_text(
            '<p><span style="color: rgb(220, 38, 38);">red</span> plain again</p>'
        )
        assert blocks[0].runs[0].color == "#dc2626"
        assert blocks[0].runs[1].color is None

    def test_br_forces_a_new_block_without_unbalancing_the_parser(self) -> None:
        # <br> has no matching end tag — must not corrupt later parsing.
        blocks = parse_rich_text("<p>line one<br>line two</p><p>line three</p>")
        assert [b.runs[0].text for b in blocks] == ["line one", "line two", "line three"]

    def test_empty_paragraph_is_dropped(self) -> None:
        blocks = parse_rich_text("<p>Real content</p><p></p>")
        assert len(blocks) == 1

    def test_mixed_bullet_and_plain_blocks_preserve_order_and_flags(self) -> None:
        html = "<p>Intro</p><ul><li>First</li><li>Second</li></ul><p>Outro</p>"
        blocks = parse_rich_text(html)
        assert [(b.runs[0].text, b.bullet) for b in blocks] == [
            ("Intro", False),
            ("First", True),
            ("Second", True),
            ("Outro", False),
        ]


class TestPlainText:
    def test_none_returns_empty_string(self) -> None:
        assert plain_text(None) == ""

    def test_strips_all_formatting(self) -> None:
        assert plain_text('<b style="color: rgb(220, 38, 38);">bold and red</b>') == "bold and red"

    def test_runs_within_a_block_concatenate_without_extra_spaces(self) -> None:
        html = "<p>Mix <i>italic</i> and <b>bold</b> together</p>"
        assert plain_text(html) == "Mix italic and bold together"

    def test_multiple_blocks_join_with_a_single_space(self) -> None:
        assert plain_text("<p>First</p><p>Second</p>") == "First Second"
