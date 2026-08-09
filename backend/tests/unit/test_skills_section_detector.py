from app.application.resume_intelligence.skills_section_detector import (
    has_dedicated_skills_section,
)


class TestHasDedicatedSkillsSection:
    def test_true_for_plain_skills_heading(self) -> None:
        raw_text = "JANE DOE\nSUMMARY\nExperienced engineer.\nSKILLS\nPython, PostgreSQL\n"
        assert has_dedicated_skills_section(raw_text) is True

    def test_true_for_core_competencies_heading(self) -> None:
        raw_text = "JANE DOE\nCORE COMPETENCIES\nLeadership, Stakeholder Management\n"
        assert has_dedicated_skills_section(raw_text) is True

    def test_true_for_technical_skills_heading(self) -> None:
        raw_text = "JANE DOE\nTECHNICAL SKILLS\nPython, AWS, Docker\n"
        assert has_dedicated_skills_section(raw_text) is True

    def test_true_for_areas_of_expertise_heading(self) -> None:
        raw_text = "JANE DOE\nAREAS OF EXPERTISE\nAgile Coaching, Change Management\n"
        assert has_dedicated_skills_section(raw_text) is True

    def test_true_for_skills_and_competencies_heading(self) -> None:
        raw_text = "JANE DOE\nSKILLS & COMPETENCIES\nPython, AWS\n"
        assert has_dedicated_skills_section(raw_text) is True

    def test_false_when_no_skills_heading_anywhere(self) -> None:
        """The exact real-resume shape that surfaced this bug live: only
        a name/headline, EXECUTIVE SUMMARY, CERTIFICATIONS, and
        PROFESSIONAL EXPERIENCE — no Skills/Core Competencies section at
        all, even though the Executive Summary prose happens to mention
        several skill-sounding phrases in passing.
        """
        raw_text = (
            "BISHNU MAHARANA\n"
            "Enterprise Agile Transformation Coach | Advanced SAFe® Practice Consultant\n"
            "215-500-8380 - bishnu@example.com\n"
            "EXECUTIVE SUMMARY\n"
            "Skilled in coaching executives, RTEs, Product Managers, Scrum Masters, "
            "Product Owners, and engineering teams to align strategy with execution "
            "through SAFe practices, Lean Portfolio Management, flow metrics, and "
            "measurable outcome-based governance.\n"
            "CERTIFICATIONS\n"
            "Advanced SAFe 6 Practice Consultant | PMP | CSM\n"
            "PROFESSIONAL EXPERIENCE\n"
            "Acme Corp | Agile Coach | Jan 2020 - Present\n"
            "- Led enterprise transformation initiatives.\n"
        )
        assert has_dedicated_skills_section(raw_text) is False

    def test_false_for_empty_text(self) -> None:
        assert has_dedicated_skills_section("") is False

    def test_word_containing_skill_as_substring_is_not_mistaken_for_a_heading(self) -> None:
        """A content line mentioning "skill(s)" mid-sentence must never
        be mistaken for a heading — only a line that IS (almost)
        entirely the heading phrase itself counts, same fullmatch
        reasoning as certification_line_parser.py's own heading regex.
        """
        raw_text = (
            "JANE DOE\nSUMMARY\n"
            "A skilled engineer with a decade of experience building distributed systems.\n"
            "EXPERIENCE\nAcme Corp\n"
        )
        assert has_dedicated_skills_section(raw_text) is False

    def test_heading_with_trailing_colon_is_recognized(self) -> None:
        raw_text = "JANE DOE\nSkills:\nPython, AWS\n"
        assert has_dedicated_skills_section(raw_text) is True
