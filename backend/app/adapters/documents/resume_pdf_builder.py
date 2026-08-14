"""Generates a formatted PDF resume from a ResumeData bundle.

reportlab's Paragraph flowable interprets a small subset of HTML-like
markup (<b>, etc.) — every piece of user-entered text is escaped via
_esc() before being embedded, so a name/title/description containing
literal '&', '<', or '>' can't corrupt the markup or (worse) get
silently dropped by reportlab's parser. python-docx text runs (the
other builder) don't have this concern — they're literal strings, not
markup — so this escaping step is specific to this file.

Section order follows the specific profile's own
resolve_resume_section_order(profile.section_order) — see
resume_docx_builder.py's module docstring for the full reasoning; both
builders share the exact same resolution logic and per-format-neutral
section list, just rendering it into a different document model.
"""

from __future__ import annotations

import io
from collections.abc import Callable
from xml.sax.saxutils import escape

from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    Flowable,
    ListFlowable,
    ListItem,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
)

from app.adapters.documents.resume_data import (
    ResumeData,
    contact_line_parts,
    description_lines,
    education_degree_line,
    format_date_range,
    group_competencies_by_category,
    resolve_resume_section_order,
    strip_bullet_marker,
)


def _esc(text: str) -> str:
    return escape(text)


_STYLES = getSampleStyleSheet()
_NAME_STYLE = ParagraphStyle(
    "ResumeName", parent=_STYLES["Title"], alignment=TA_CENTER, fontSize=20
)
_SUBTITLE_STYLE = ParagraphStyle(
    "ResumeSubtitle", parent=_STYLES["Normal"], alignment=TA_CENTER, fontName="Helvetica-Oblique"
)
_CONTACT_STYLE = ParagraphStyle(
    "ResumeContact", parent=_STYLES["Normal"], alignment=TA_CENTER, fontSize=9
)
_HEADING_STYLE = ParagraphStyle(
    "ResumeHeading", parent=_STYLES["Heading2"], spaceBefore=12, spaceAfter=4
)
_BODY_STYLE = _STYLES["Normal"]
_ITALIC_STYLE = ParagraphStyle(
    "ResumeItalic", parent=_STYLES["Normal"], fontName="Helvetica-Oblique", fontSize=9, spaceAfter=4
)
_QUOTE_STYLE = ParagraphStyle(
    "ResumeQuote",
    parent=_STYLES["Normal"],
    fontName="Helvetica-Oblique",
    leftIndent=18,
    spaceAfter=2,
)
_ATTRIBUTION_STYLE = ParagraphStyle(
    "ResumeAttribution", parent=_STYLES["Normal"], leftIndent=18, fontSize=9, spaceAfter=8
)


def _description_flowable(
    description: str | None, *, exclude: tuple[str | None, ...] = ()
) -> Flowable | None:
    lines = description_lines(description, exclude=exclude)
    if not lines:
        return None
    items = [ListItem(Paragraph(_esc(strip_bullet_marker(line)), _BODY_STYLE)) for line in lines]
    return ListFlowable(items, bulletType="bullet")


def _render_core_competencies(story: list[Flowable], data: ResumeData) -> None:
    if not data.profile.core_competencies:
        return
    story.append(Paragraph("Core Competencies", _HEADING_STYLE))
    for category, items in group_competencies_by_category(data.profile.core_competencies):
        names = _esc(", ".join(item.name for item in items))
        story.append(Paragraph(f"<b>{_esc(category or 'Uncategorized')}:</b> {names}", _BODY_STYLE))


def _render_experience(story: list[Flowable], data: ResumeData) -> None:
    if not data.experiences:
        return
    story.append(Paragraph("Professional Experience", _HEADING_STYLE))
    for exp in data.experiences:
        title_line = f"<b>{_esc(exp.title)}</b> — {_esc(exp.company)}"
        if exp.location:
            title_line += f" ({_esc(exp.location)})"
        story.append(Paragraph(title_line, _BODY_STYLE))
        story.append(
            Paragraph(_esc(format_date_range(exp.start_date, exp.end_date)), _ITALIC_STYLE)
        )
        desc_flowable = _description_flowable(exp.description)
        if desc_flowable is not None:
            story.append(desc_flowable)


def _render_education(story: list[Flowable], data: ResumeData) -> None:
    if not data.educations:
        return
    story.append(Paragraph("Education", _HEADING_STYLE))
    for edu in data.educations:
        degree_line = education_degree_line(edu)
        line = f"<b>{_esc(edu.institution)}</b>"
        if degree_line:
            line += f" — {_esc(degree_line)}"
        story.append(Paragraph(line, _BODY_STYLE))
        if edu.start_date or edu.end_date:
            story.append(
                Paragraph(_esc(format_date_range(edu.start_date, edu.end_date)), _ITALIC_STYLE)
            )
        desc_flowable = _description_flowable(edu.description, exclude=(degree_line,))
        if desc_flowable is not None:
            story.append(desc_flowable)


def _render_certifications(story: list[Flowable], data: ResumeData) -> None:
    if not data.certifications:
        return
    story.append(Paragraph("Certifications", _HEADING_STYLE))
    for cert in data.certifications:
        line = f"<b>{_esc(cert.name)}</b> — {_esc(cert.issuing_organization)}"
        if cert.issue_date:
            line += f" ({cert.issue_date.strftime('%b %Y')})"
        story.append(Paragraph(line, _BODY_STYLE))


def _render_career_highlights(story: list[Flowable], data: ResumeData) -> None:
    if not data.career_highlights:
        return
    story.append(Paragraph("Career Highlights", _HEADING_STYLE))
    items = [
        ListItem(Paragraph(_esc(highlight.title), _BODY_STYLE))
        for highlight in data.career_highlights
    ]
    story.append(ListFlowable(items, bulletType="bullet"))


def _render_key_achievements(story: list[Flowable], data: ResumeData) -> None:
    if not data.key_achievements:
        return
    story.append(Paragraph("Key Achievements", _HEADING_STYLE))
    achievement_items = []
    for achievement in data.key_achievements:
        prefix = f"{_esc(achievement.company)} — " if achievement.company else ""
        text = f"<b>{prefix}{_esc(achievement.title)}</b>"
        if achievement.description:
            text += f": {_esc(achievement.description)}"
        achievement_items.append(ListItem(Paragraph(text, _BODY_STYLE)))
    story.append(ListFlowable(achievement_items, bulletType="bullet"))


def _render_career_goals(story: list[Flowable], data: ResumeData) -> None:
    if not data.career_goals:
        return
    story.append(Paragraph("Career Goals", _HEADING_STYLE))
    for goal in data.career_goals:
        line = f"<b>{_esc(goal.target_role)}</b>"
        if goal.target_date:
            line += f" (Target: {_esc(goal.target_date.strftime('%b %Y'))})"
        story.append(Paragraph(line, _BODY_STYLE))
        if goal.description:
            story.append(Paragraph(_esc(goal.description), _BODY_STYLE))


def _render_recommendations(story: list[Flowable], data: ResumeData) -> None:
    if not data.recommendations:
        return
    story.append(Paragraph("Recommendations", _HEADING_STYLE))
    for endorsement in data.recommendations:
        story.append(Paragraph(f"“{_esc(endorsement.content)}”", _QUOTE_STYLE))
        detail_parts = [
            part for part in (endorsement.recommender_title, endorsement.relationship) if part
        ]
        attribution = f"— <b>{_esc(endorsement.recommender_name)}</b>"
        if detail_parts:
            attribution += f", {_esc(', '.join(detail_parts))}"
        story.append(Paragraph(attribution, _ATTRIBUTION_STYLE))


_SECTION_RENDERERS: dict[str, Callable[[list[Flowable], ResumeData], None]] = {
    "core_competencies": _render_core_competencies,
    "experience": _render_experience,
    "education": _render_education,
    "certifications": _render_certifications,
    "career_highlights": _render_career_highlights,
    "key_achievements": _render_key_achievements,
    "career_goals": _render_career_goals,
    "recommendations": _render_recommendations,
}


def build_resume_pdf(data: ResumeData) -> bytes:
    buffer = io.BytesIO()
    document = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        topMargin=0.6 * inch,
        bottomMargin=0.6 * inch,
        leftMargin=0.75 * inch,
        rightMargin=0.75 * inch,
    )

    story: list[Flowable] = [
        Paragraph(_esc(data.user.display_name or data.user.email), _NAME_STYLE)
    ]

    subtitle_parts = [part for part in (data.role_label, data.profile.headline) if part]
    if subtitle_parts:
        story.append(Paragraph(_esc(" — ".join(subtitle_parts)), _SUBTITLE_STYLE))

    contact_parts = contact_line_parts(data.user)
    if contact_parts:
        story.append(Paragraph(_esc(" | ".join(contact_parts)), _CONTACT_STYLE))

    story.append(Spacer(1, 0.15 * inch))

    if data.profile.summary:
        story.append(Paragraph("Summary", _HEADING_STYLE))
        story.append(Paragraph(_esc(data.profile.summary), _BODY_STYLE))

    for section_key in resolve_resume_section_order(data.profile.section_order):
        _SECTION_RENDERERS[section_key](story, data)

    document.build(story)
    return buffer.getvalue()
