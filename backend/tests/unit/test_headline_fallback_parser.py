from app.application.resume_intelligence.headline_fallback_parser import (
    extract_headline_fallback,
)


class TestExtractHeadlineFallback:
    def test_headline_directly_under_name_before_contact_line(self) -> None:
        raw_text = (
            "BISHNU MAHARANA\n"
            "Enterprise Agile Transformation Coach | Advanced SAFe Practice Consultant\n"
            "215-500-8380 - bishnu@example.com - linkedin.com/in/example\n"
            "EXECUTIVE SUMMARY\n"
            "Enterprise Agile Transformation Coach with extensive experience...\n"
        )
        assert (
            extract_headline_fallback(raw_text)
            == "Enterprise Agile Transformation Coach | Advanced SAFe Practice Consultant"
        )

    def test_headline_after_contact_line(self) -> None:
        raw_text = (
            "JANE DOE\n"
            "jane.doe@example.com - 555-123-4567\n"
            "Senior Data Platform Engineer | Cloud Infrastructure Lead\n"
            "SUMMARY\n"
            "Experienced engineer...\n"
        )
        assert (
            extract_headline_fallback(raw_text)
            == "Senior Data Platform Engineer | Cloud Infrastructure Lead"
        )

    def test_no_headline_when_section_heading_follows_name_directly(self) -> None:
        raw_text = "JOHN SMITH\nEXECUTIVE SUMMARY\nA long career of achievement...\n"
        assert extract_headline_fallback(raw_text) is None

    def test_no_headline_when_only_contact_lines_follow_name(self) -> None:
        raw_text = (
            "JOHN SMITH\n"
            "555-123-4567\n"
            "john.smith@example.com\n"
            "linkedin.com/in/johnsmith\n"
            "SUMMARY\n"
            "A long career of achievement...\n"
        )
        assert extract_headline_fallback(raw_text) is None

    def test_single_line_resume_returns_none(self) -> None:
        assert extract_headline_fallback("JOHN SMITH") is None

    def test_empty_text_returns_none(self) -> None:
        assert extract_headline_fallback("") is None

    def test_blank_lines_between_name_and_headline_are_skipped(self) -> None:
        raw_text = "JANE DOE\n\n\nPrincipal Software Architect\nSUMMARY\nText...\n"
        assert extract_headline_fallback(raw_text) == "Principal Software Architect"

    def test_all_caps_headline_is_still_accepted(self) -> None:
        raw_text = "JANE DOE\nSENIOR PRODUCT MANAGER AND STRATEGY LEAD\nSUMMARY\nText...\n"
        assert extract_headline_fallback(raw_text) == "SENIOR PRODUCT MANAGER AND STRATEGY LEAD"

    def test_short_all_caps_line_is_treated_as_a_heading_not_a_headline(self) -> None:
        raw_text = "JANE DOE\nSKILLS\nPython, Java, C++\n"
        assert extract_headline_fallback(raw_text) is None

    def test_resume_text_starting_directly_with_a_section_heading_returns_none(self) -> None:
        """Live-observed real bug: a resume text with no name/headline/
        contact block at all — e.g. a deliberately partial upload
        beginning mid-résumé at "PROFESSIONAL EXPERIENCE" — was skipped
        over unconditionally as "the name" (line 0 is always assumed to
        be one), and the very next line (a job's own "Company | Title |
        Location | Dates" header) was returned as the headline instead.
        If line 0 is itself already a known section heading, there's no
        Name/Headline/Contact structure here at all, and nothing after
        it should be guessed at either."""
        raw_text = (
            "PROFESSIONAL EXPERIENCE\n"
            "Acme Corp | Engineer | Philadelphia, PA | Jun 2022 - Present\n"
            "Did engineering things.\n"
        )
        assert extract_headline_fallback(raw_text) is None

    def test_ordinary_name_line_is_not_mistaken_for_a_heading(self) -> None:
        """A person's name is just as commonly short and all-caps as a
        section heading ("JANE DOE", "BISHNU MAHARANA") — line 0 must
        only be rejected on an exact, unambiguous heading-phrase match,
        never the broader short-all-caps heuristic used for candidate
        headline lines further down."""
        raw_text = "JANE DOE\nPrincipal Software Architect\nSUMMARY\nText...\n"
        assert extract_headline_fallback(raw_text) == "Principal Software Architect"

    def test_gives_up_after_scanning_a_small_window(self) -> None:
        raw_text = (
            "JANE DOE\n"
            "555-123-4567\n"
            "jane@example.com\n"
            "linkedin.com/in/jane\n"
            "Principal Software Architect\n"
            "SUMMARY\n"
            "Text...\n"
        )
        # Three contact-shaped lines fill the whole scan window, so the
        # real headline one line further down is never reached — an
        # accepted false negative to keep the scan narrow and avoid
        # false positives elsewhere.
        assert extract_headline_fallback(raw_text) is None
