"""Unit tests for the deterministic certifications-section parser.

Covers the delimiter/format variations a real resume might use to list
certifications — the parser exists specifically so extraction doesn't
depend on an LLM correctly noticing every name in an arbitrarily
formatted list (see certification_line_parser.py's module docstring for
the live-observed failure this replaces).
"""

from __future__ import annotations

import pytest

from app.application.resume_intelligence.certification_line_parser import (
    extract_certification_names,
)

pytestmark = pytest.mark.unit


class TestExtractCertificationNames:
    def test_pipe_separated_single_line(self) -> None:
        text = "CERTIFICATIONS\nPMP | CSM | SSGB | ICP-ENT\nEDUCATION\nfoo"
        assert extract_certification_names(text) == ["PMP", "CSM", "SSGB", "ICP-ENT"]

    def test_comma_separated_with_trailing_and(self) -> None:
        text = "Certifications\nPMP, CSM, SSGB and ICP-ENT\nExperience\nfoo"
        assert extract_certification_names(text) == ["PMP", "CSM", "SSGB", "ICP-ENT"]

    def test_semicolon_separated(self) -> None:
        text = "Certifications & Training\nPMP; CSM; SSGB\nProjects\nfoo"
        assert extract_certification_names(text) == ["PMP", "CSM", "SSGB"]

    def test_mid_line_bullet_separated(self) -> None:
        text = "Credentials\n• PMP • CSM • SSGB\nAwards\nfoo"
        assert extract_certification_names(text) == ["PMP", "CSM", "SSGB"]

    def test_one_bullet_per_line_with_dash_markers(self) -> None:
        text = (
            "LICENSES & CERTIFICATIONS\n"
            "- Project Management Professional (PMP)\n"
            "- Certified ScrumMaster (CSM)\n"
            "PROJECTS\nfoo"
        )
        assert extract_certification_names(text) == [
            "Project Management Professional (PMP)",
            "Certified ScrumMaster (CSM)",
        ]

    def test_numbered_list(self) -> None:
        text = "CERTIFICATIONS\n1. PMP\n2. CSM\n3. SSGB\nEducation\nfoo"
        assert extract_certification_names(text) == ["PMP", "CSM", "SSGB"]

    def test_single_name_issuer_year_line_is_not_split_on_its_internal_comma(self) -> None:
        """"AWS Certified Solutions Architect - Amazon Web Services, 2023"
        is ONE certification with its issuer and year attached, not two
        certifications separated by a comma — every segment being short
        AND ending in a bare year is what distinguishes this shape from a
        genuine flat list.
        """
        text = (
            "CERTIFICATIONS\n"
            "AWS Certified Solutions Architect - Amazon Web Services, 2023\n"
            "EDUCATION\nfoo"
        )
        assert extract_certification_names(text) == [
            "AWS Certified Solutions Architect - Amazon Web Services, 2023"
        ]

    def test_word_bullet_prefixed_docx_style_lines(self) -> None:
        """Matches resume_text_extractor.py's own "• " prefix
        convention for a genuine Word bullet paragraph."""
        text = "CERTIFICATIONS\n• PMP\n• CSM\nEDUCATION\nfoo"
        assert extract_certification_names(text) == ["PMP", "CSM"]

    def test_no_certifications_heading_returns_empty(self) -> None:
        text = "SOME RANDOM SECTION\nPMP, CSM\n"
        assert extract_certification_names(text) == []

    def test_content_line_mentioning_certified_is_never_mistaken_for_a_heading(self) -> None:
        """"AWS Certified Solutions Architect" contains "certif" as a
        substring but must never be treated as a NEW section heading —
        the matcher requires the whole line to equal a heading phrase,
        not just contain one."""
        text = (
            "CERTIFICATIONS\n"
            "AWS Certified Solutions Architect\n"
            "Certified Kubernetes Administrator\n"
            "EDUCATION\nfoo"
        )
        assert extract_certification_names(text) == [
            "AWS Certified Solutions Architect",
            "Certified Kubernetes Administrator",
        ]

    def test_deduplicates_case_insensitively(self) -> None:
        text = "Certifications\nPMP, csm\nPmp\nEducation\nfoo"
        assert extract_certification_names(text) == ["PMP", "csm"]

    def test_the_actual_two_previously_dropped_names_are_found(self) -> None:
        """Regression: "Digital Product Management" and "Generative AI
        Leader" are the two names repeatedly dropped by LLM extraction
        across multiple models/prompt designs — the whole reason this
        module exists. Confirms the deterministic parse gets all 13/13
        on the real resume line that triggered this."""
        text = (
            "CERTIFICATIONS\n"
            "• Advanced SAFe 6 Practice Consultant | ICP-ENT | ICP-CAT | ICP-ACC | "
            "ICP-ATF | PMP | PMI-ACP | CSM | LeSS | SSGB | Digital Product Management | "
            "Google Cloud Digital Leader | Generative AI Leader\n"
            "PROFESSIONAL EXPERIENCE\nfoo"
        )
        names = extract_certification_names(text)
        assert len(names) == 13
        assert "Digital Product Management" in names
        assert "Generative AI Leader" in names

    def test_section_ends_at_the_next_recognized_heading(self) -> None:
        text = "Certifications\nPMP\nEXECUTIVE SUMMARY\nPMP should not appear twice"
        assert extract_certification_names(text) == ["PMP"]
