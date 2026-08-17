"""Seed global (tenant_id = NULL) permissions and roles.

Idempotent — safe to run multiple times (checks for existing rows by
unique code/name before inserting). Run after migrations, before the
first tenant registers:

    python scripts/seed_platform_defaults.py

Permissions and roles are deliberately not created via Alembic data
migrations here — schema changes (tables, columns, RLS policies) go
through Alembic; reference data that might reasonably be adjusted per
environment (e.g. a staging environment wanting an extra test role)
lives in a seed script instead. If this list grows to need review/audit
history of its own, revisit as an Alembic data migration then.
"""

from __future__ import annotations

import asyncio
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.db.base import async_session_factory, set_tenant_context
from app.adapters.db.models import (
    ModelVersionModel,
    PermissionModel,
    PlatformAdminModel,
    PlatformSettingModel,
    PromptVersionModel,
    RoleModel,
    RolePermissionModel,
    TenantModel,
    UserModel,
)
from app.core.config import get_settings
from app.core.logging import get_logger
from app.domain.identity.personal_accounts import derive_personal_subdomain
from app.domain.platform_admin.permissions import ALL_PLATFORM_PERMISSION_CODES

logger = get_logger(__name__)

# --- AI Platform (Phase 4) ---
# The prompt template is a versioned, approved row rather than an
# inline string in ChatService — see ADR-004. {conversation_history}
# and {user_message} are filled in by ChatService via str.format().
CHAT_PROMPT_USE_CASE = "career_coach_chat"
CHAT_PROMPT_TEMPLATE = """You are the AI Career Coach inside Career Compass AI, an \
enterprise career-intelligence platform. Be warm, encouraging, and specific — ground \
your advice in what the person actually tells you rather than generic platitudes. \
Keep responses concise (a few sentences to a short paragraph) unless the user asks \
for more depth.

Conversation so far:
{conversation_history}

User: {user_message}

Respond as the AI Career Coach."""

# --- Resume Intelligence (Phase 5) ---
# {resume_text} is filled in by ResumeExtractionService via
# str.format() — the literal JSON braces in the schema example below
# are escaped as {{ }} for that reason, not for readability.
RESUME_EXTRACTION_USE_CASE = "resume_extraction"
RESUME_EXTRACTION_PROMPT_TEMPLATE = """You are an expert resume parser. Extract the \
following resume text into STRICT JSON matching this schema exactly. Respond with \
ONLY the raw JSON object — no prose, no markdown code fences, no explanation.

{{
  "headline": string or null,
  "summary": string or null,
  "skills": [
    {{"name": string, "category": string or null}}
  ],
  "experience": [
    {{"title": string, "company": string, "location": string or null, \
"start_date": "YYYY-MM-DD" or null, "end_date": "YYYY-MM-DD" or null, \
"description": string or null}}
  ],
  "education": [
    {{"institution": string, "degree": string or null, "field_of_study": string or null, \
"start_date": "YYYY-MM-DD" or null, "end_date": "YYYY-MM-DD" or null, \
"description": string or null}}
  ],
  "certification_names_found": [string, ...],
  "certifications": [
    {{"name": string, "issuing_organization": string, "issue_date": "YYYY-MM-DD" or null, \
"expiration_date": "YYYY-MM-DD" or null, "credential_id": string or null, \
"credential_url": string or null}}
  ],
  "career_highlights": [
    {{"title": string, "company": string or null, "description": string or null, \
"occurred_on": "YYYY-MM-DD" or null}}
  ],
  "key_achievements": [
    {{"title": string, "company": string or null, "description": string or null, \
"occurred_on": "YYYY-MM-DD" or null}}
  ]
}}

Write the JSON keys in EXACTLY the order shown above (headline, summary, skills, \
experience, education, certification_names_found, certifications, career_highlights, \
key_achievements — with "experience" immediately after "skills", not last, and \
"certification_names_found" immediately BEFORE "certifications", not after). This order \
is deliberate, not cosmetic: you must transcribe "certification_names_found" first, \
before you have written a single object into "certifications" — see the \
"certifications" field guidance below for exactly why. Full \
per-role descriptions (see \
below) make "experience" the section most worth protecting if you start running low on \
room to respond, so it is written while the most budget remains; if a very long resume \
still runs low on room near the end, it is "career_highlights"/"key_achievements" — the \
least critical sections, and often already redundant with the per-role descriptions \
above them — that end up incomplete instead.

Every "description" field (in experience, education, career_highlights, and \
key_achievements) should \
preserve the FULL substance of that entry's original bullet points — do NOT compress \
multiple bullets into one paraphrased sentence, and do not drop bullets to save space. \
When the source resume lists bullet points for an entry, write "description" as those \
bullets joined by newline characters, one bullet per line, in their original order and \
close to their original wording (trim only obvious filler wording, never actual \
content or whole bullets). If an entry has no bullet points in the source text (e.g. a \
one-line job entry with no elaboration beneath it), use its existing short text as-is, \
or null if there is none — never invent bullets that aren't in the resume. It is still \
more important that every role, every entry, and every section appears at all than that \
any single description is exhaustive — if a resume is unusually long, it is acceptable \
to shorten a description's least important bullets before ever dropping an entire role, \
entry, or section.
  A line in the source resume text that already starts with "• " is a genuine bullet \
point — Word's own list formatting, not something you're adding. Preserve that exact \
"• " prefix on any such line you include in "description", so the distinction between \
a real bullet and a plain sentence survives into your output (the UI renders "• "-\
prefixed lines as an actual bulleted list, and un-prefixed lines as plain paragraph \
text — this only works if you carry the marker through faithfully, character for \
character, never adding it to a line that didn't already have it and never stripping \
it from one that did).
  Do NOT decide this by judging whether a line "reads like" an introduction, a \
summary, or a topic sentence — that judgment call is exactly what has been observed, \
live, causing a real, repeated mistake: a role where EVERY line, including the first, \
is genuinely "• "-prefixed in the source still had its first line's "• " silently \
stripped, because the line's wording happened to sound like an overview sentence. \
Wording is never the signal. The ONLY thing that decides whether a given output line \
starts with "• " is whether that EXACT source line itself starts with "• " — checked \
mechanically, one line at a time, ignoring what the line says. Some roles do have one \
or more genuinely plain (non-"• "-prefixed) lines before their bulleted lines in the \
source — when that's what the source actually shows, reproduce it exactly (a plain \
line stays plain, don't add a "• " it never had); when the source instead shows "• " \
on every line for that role, including the first, your output must too, with no \
exceptions for a line that merely sounds like it could have been an intro. \
Two fictional worked examples (illustrative names only, not from any real resume): \
source lines "• Owns the platform roadmap for a 12-person engineering team." / \
"• Shipped three major releases in the last fiscal year." (both genuinely "• "-prefixed, \
no plain line before them) — correct description: "• Owns the platform roadmap for a \
12-person engineering team.\\n• Shipped three major releases in the last fiscal year." — \
stripping the first "• " because that sentence "sounds like" a role overview would be \
WRONG here. Contrast with source lines "Leads a distributed team across three time \
zones." (genuinely plain, no "• ") / "• Reduced infrastructure spend by 30%." (genuinely \
"• "-prefixed) — correct description: "Leads a distributed team across three time \
zones.\\n• Reduced infrastructure spend by 30%." — here the first line stays unprefixed \
because the SOURCE line itself had no "• ", not because of how it reads.

Field guidance:
- "headline": the professional title or tagline printed directly under the person's \
name at the very top of the resume, on its own line, before any "Summary"/"Experience"/ \
etc. section begins (e.g. "Senior Software Engineer" or "Full-Stack Developer | Cloud \
Architect"). Extract this line's text even if it's identical to the title of the most \
recent role in the experience section below — that's a common, correct pattern (many \
resumes repeat the current job title as the headline), NOT a sign to skip it. Extract \
it even if the resume's "summary" paragraph (see below) opens with very similar or \
overlapping wording (fictional example — headline "Senior Data Platform Engineer | \
Cloud Infrastructure Lead" alongside a summary starting "Senior Data Platform Engineer \
and Cloud Infrastructure Lead with extensive experience...") — that overlap is normal, \
not a signal to leave one of the two null to avoid repeating yourself; "headline" and \
"summary" are two SEPARATE fields the UI displays in two separate places, and this \
exact case (a real headline silently dropped specifically because it overlapped with \
an already-extracted summary) has been observed live. This is NEVER the person's name, \
NEVER a company name, and NEVER a section header word like \
"Summary" or "Experience" by itself. Only use null if the line directly under the \
person's name is something else entirely (e.g. contact info) with no title/tagline \
line anywhere before the first section heading.
- "summary": the longer descriptive paragraph (one or more sentences) usually printed \
under a heading like "Summary", "Executive Summary", "Professional Summary", "Profile", \
or "About" — a different, LONGER piece of text than "headline", even though the summary \
paragraph often starts with wording similar to the headline (e.g. both mentioning the \
same job title). That overlap is normal — extract the summary paragraph in full anyway; \
do not leave it null just because its opening words resemble the headline.
- "skills": a FLAT list of individual skill objects, each with its own "name" and \
"category". Resumes often group skills under subheadings, e.g. "Programming Languages: \
Python, Java, C++" and "Frameworks: React, Django" — in that case extract every \
individual skill listed under every subheading as its own object, with "name" set to \
just that one skill ("Python", "Java", "C++", "React", "Django", ...) and "category" set \
to the exact subheading text it was listed under ("Programming Languages", "Frameworks"). \
NEVER put a subheading label itself into a "name" field, and NEVER combine multiple \
skills into one "name" (e.g. "Python, Java, C++" is three separate skill objects, not \
one). If a skill is listed on its own with no subheading grouping at all, set its \
"category" to null.
  "skills" is populated ONLY from a resume section that is actually about skills or \
competencies — headings like "Skills", "Core Competencies", "Technical Skills", or \
"Areas of Expertise". If the resume has no such section at all, "skills" MUST be an \
empty array — this is the correct, expected output for a resume that simply doesn't \
list skills separately, NOT a gap to fill from somewhere else. In particular, NEVER \
copy or reuse entries from "certifications" into "skills" (a certification name like \
"PMP" or "CSM" is not a skill, even though it names a competency area) and NEVER pull \
individual words or phrases out of "experience" bullet points to manufacture skill \
entries — both of these have been observed live on resumes with no dedicated skills \
section, where the model produced a "skills" list that was really just a duplicate of \
"certifications". An empty "skills" array is always preferable to inventing entries \
this way.
  Worked example — for the input line "Agile & Scaling: SAFe 6, Lean Portfolio \
Management, Scrum", the ONLY correct output is THREE separate objects, one per skill, \
each with the subheading as "category":
  [{{"name": "SAFe 6", "category": "Agile & Scaling"}}, {{"name": "Lean Portfolio \
Management", "category": "Agile & Scaling"}}, {{"name": "Scrum", "category": "Agile & \
Scaling"}}]
  These are all WRONG and must never happen: collapsing the whole line into one object \
({{"name": "Agile & Scaling", "category": "SAFe 6, Lean Portfolio Management, Scrum"}}); \
putting the subheading in "name" instead of "category" ({{"name": "Agile & Scaling", \
"category": "SAFe 6"}}); or dropping any skill from the list. "name" is always the \
individual skill. "category" is always the subheading (or null). Every single skill \
named after the colon must appear as its own object — never fewer objects than skills \
listed.
- "education": ONLY formal, degree-granting academic institutions — colleges, \
universities, or schools where the person earned a degree/diploma. Two things that are \
NOT education, even though resumes sometimes list them near an education section: (1) \
an employer/company, which always belongs in "experience" instead, even if the entry \
has no listed responsibilities — never let an employer appear in both "experience" and \
"education"; (2) a professional association, institute, or membership body (e.g. "IEEE", \
"Institution of Engineers", "PMI") — those belong in "certifications" instead, since \
membership/credentialing is what they represent, not a degree program.
- "certifications" is produced in TWO SEPARATE STEPS, not written directly — this is \
deliberate, because writing straight into "certifications" has been observed, live, \
losing 2 of 13 real items on one attempt and 0 of the same 13 on the very next, \
identical attempt: naming, issuer-inference, and date-formatting all at once is enough \
cognitive load that items silently go missing, even though every individual instruction \
below is being followed correctly for the items that DO make it through. Splitting \
transcription from enrichment removes that failure mode by making each step simple \
enough to do perfectly.
  STEP 1 — "certification_names_found": this content can appear under many different \
headings that all mean the same thing — "Certifications", "Licenses & Certifications", \
"Certifications & Training", "Professional Certifications", "Credentials", etc. Look for \
it under any of these, not only a section literally titled "Certifications". Re-read \
that section of the source text and transcribe EVERY individual certification name or \
abbreviation you find into "certification_names_found" — a flat array of plain strings, \
in the order they appear, copied close to verbatim. This is copying, not composing: do \
not infer an issuer yet, do not format a date yet, do not decide whether a name "looks \
important" enough to include yet. If a line lists several certifications separated by \
"|", ",", or "/" (fictional example — "Certified Financial Planner | ABC-100 | ABC-200 | \
XYZ Practitioner | Growth Marketing Leadership"), that ONE line becomes FIVE separate \
array entries, one per name/abbreviation — never one combined string for the whole \
line. An unfamiliar, program/course-style name (like "Growth Marketing Leadership" \
above) goes in this array exactly the same as a widely-recognized abbreviation like \
"PMP" — this step has no concept of "confidence," only "did I see this name in the \
source text."
  STEP 2 — "certifications": using "certification_names_found" as your worklist, write \
exactly one object into "certifications" for EVERY entry in that array, in the same \
order — "certifications".length MUST equal "certification_names_found".length, always. \
For each name, "issuing_organization" is required and must NEVER be left null or empty \
— but it must ALSO never be a specific organization name unless the resume text ITSELF \
states it, even for a certification whose real-world issuer is famous or obvious to you \
(fictional example: even though you may know "PMP" is issued by PMI in the real world, \
if the resume text merely lists "PMP" with no issuer mentioned anywhere near it, the \
correct output is still "Not specified in resume" — never fill in outside/general \
knowledge the source text doesn't actually contain). Only write a specific organization \
name when the resume text visibly pairs the certification with one nearby — e.g. a line \
reading "PMP (PMI)", "PMP - Project Management Institute", or "PMP, issued by PMI" all \
count as the text stating it; a bare list like "PMP | CSM | SSGB" with no issuer text \
anywhere does not, for any of those three, no matter how well-known each credential's \
real issuer actually is. When the text doesn't state one, write the literal string \
"Not specified in resume" as "issuing_organization" for that entry — this is a \
completely valid, expected value, and will be the correct answer far more often than \
not, since most resumes list certification names without also naming each issuer. Every \
name that made it into "certification_names_found" in Step 1 gets an entry here — Step \
2 is never a reason to drop something Step 1 already found.
  Before finalizing your answer, re-count both arrays and confirm \
"certifications".length equals "certification_names_found".length. If they don't match, \
you skipped a name while writing Step 2 — go back and add the missing object(s) rather \
than shortening "certification_names_found" to match.
- "career_highlights" and "key_achievements" are TWO SEPARATE lists, both usually \
found under a heading like "Career Highlights", "Key Achievements", "Highlights", \
"Achievements", "Recognitions", or "Awards" (any of these heading words can introduce \
either shape below — the heading text alone doesn't decide which list an entry goes \
into, the LINE'S OWN shape does), separate from the per-role bullet points already \
captured inside each "experience" entry's own "description". Each highlight/\
recognition line becomes one entry in exactly ONE of the two lists, based on its shape:
  (1) A plain accomplishment line with NO leading "Company - " prefix and no \
mid-sentence colon separating a short title from its detail (fictional example — "Led \
a cross-functional redesign of the onboarding flow, cutting new-customer setup time by \
40%.") goes into "career_highlights". "title" is the ENTIRE line's text verbatim \
(trimmed) — do NOT split it into title/description at a comma or a "through"/"by"/\
"coaching" clause; "description" stays null for this shape even if the line is long. \
"company" is the employer name only if the line clearly names one and it isn't already \
obvious from context (otherwise null).
  (2) A recognition/award line that specifically follows "Company - Award Name: \
Description" (fictional example — "Acme Corp - Rising Star Award: Recognized for \
leading the Q3 platform migration ahead of schedule") — a dash separating a company \
from an award name, THEN a colon separating the award name from its detail — goes \
into "key_achievements" instead, never "career_highlights". Split it three ways: \
"company" is the text before the dash ("Acme Corp"), "title" is ONLY the award/\
recognition name between the \
dash and the colon ("Rising Star Award" — never re-include the company name or the dash \
in "title"), and "description" is the text after the colon ("Recognized for leading the \
Q3 platform migration ahead of schedule").
For both lists, "occurred_on" is only set if an actual date is printed on that specific \
line (otherwise null — do not guess a date from a nearby experience entry). If a \
resume has no plain-shape lines, "career_highlights" is an empty list; if it has no \
dash-then-colon recognition lines, "key_achievements" is an empty list — do not invent \
entries in either list from experience bullet points.
- "location" (on experience entries) must always be a single string, never a list — if a \
role names more than one location (e.g. "Charlotte, NC & Pennington, NJ" or two offices \
separated by a slash), join them into ONE string exactly as they appear together in the \
text; do not split them into a JSON array of separate strings.
- Every "start_date"/"end_date"/"issue_date"/"expiration_date" you output must be taken \
from an actual date printed in the text — if a date only has a year, use "YYYY-01-01". \
A date range like "May 2025 – Present" or "Oct 2019 – Current" has a REAL start date \
that must still be extracted normally (e.g. "2025-05-01") — "current/ongoing" only ever \
means the END date is null (because there isn't one yet), it is NEVER a reason to leave \
start_date null too. This applies even to the very first/most recent entry in a list. \
Do not invent information that isn't present in the text. Order experience and \
education entries most-recent-first, matching the source text. Before finalizing your \
answer, re-check every experience and education entry against the source text one more \
time — if a role's or program's dates are visibly printed there, start_date must not be \
null.

Resume text:
---
{resume_text}
---

Respond now with ONLY the JSON object described at the top of these instructions — \
no markdown headings, no bullet-point prose, no commentary, no "Here is..." preamble, \
no code fences. Do not write a resume summary, rewrite, or improved version of the \
resume text above — your only task is to extract it into the exact JSON shape \
specified earlier. Your entire response must be a single valid JSON object: the \
very first character must be "{{" and the very last character must be "}}".
"""

# --- Learning Intelligence (Phase 7) ---
# {role_name}/{missing_skills} are filled in by
# LearningRecommendationService via str.format() — the literal JSON
# braces below are escaped as {{ }} for that reason, same as the resume
# extraction template above. Wrapped in a top-level JSON *object*
# (not a bare array) specifically so the response can reuse the same
# robust "find the outermost {{ and }}" parsing idiom every other
# structured-output use case in this codebase already relies on.
LEARNING_RECOMMENDATIONS_USE_CASE = "learning_recommendations"
LEARNING_RECOMMENDATIONS_PROMPT_TEMPLATE = """You are a career development advisor inside \
Career Compass AI. A user targeting the role "{role_name}" has these skill gaps: \
{missing_skills}. For each skill, suggest 2-3 concrete, actionable learning resources \
(real, well-known courses, books, certifications, or hands-on project ideas) and a \
one-sentence note on why it matters for this role.

Respond with ONLY the raw JSON object below — no prose, no markdown code fences, no \
explanation. Your entire response must be a single valid JSON object: the very first \
character must be "{{" and the very last character must be "}}".

{{
  "recommendations": [
    {{"skill": string, "resources": [string, ...], "summary": string}}
  ]
}}
"""

# {question}/{role_context}/{profile_context}/{topic_context} are filled
# in by InterviewAnswerService via str.format() — role_context/
# profile_context/topic_context are each either a real sentence/block or
# an empty string, so the template reads naturally either way without
# needing separate templates for the grounded-vs-generic case. Plain-text
# output only (no markdown), matching every other free-text field in
# this app.
INTERVIEW_ANSWER_GENERATION_USE_CASE = "interview_answer_generation"
INTERVIEW_ANSWER_GENERATION_PROMPT_TEMPLATE = """You are an interview coach inside \
Career Compass AI, helping a candidate prepare for a real job interview{role_context}.

Interview question: "{question}"

{profile_context}{topic_context}
Write a strong, concise, first-person sample answer to this interview question — aim \
for 3-6 sentences, or a structured format like STAR if the question calls for it (e.g. \
a behavioral "tell me about a time" question). Ground your answer in the candidate \
background above where it gives you something concrete to draw on; otherwise, give \
solid general guidance for answering this kind of question well. Respond with the \
answer text only — no preamble, no meta-commentary, no markdown headers.
"""

# Catalog of selectable models (Settings > AI Model lets a user pick
# among "active" rows). Adding a non-Anthropic/non-Ollama entry also
# means registering its provider adapter in app/api/dependencies.py's
# get_llm_service. Illustrative blended cost_per_1k_tokens figures for
# the Anthropic rows, not billing-accurate — see the Anthropic pricing
# page for the authoritative per-model rate. Ollama rows are genuinely
# $0 — local inference on the user's own hardware, no metered API.
MODEL_CATALOG: list[tuple[str, str, float]] = [
    ("anthropic", "claude-opus-5", 0.015),
    ("anthropic", "claude-sonnet-5", 0.006),
    ("anthropic", "claude-haiku-4-5", 0.003),
    ("ollama", "qwen2.5:7b", 0.0),
    ("ollama", "qwen2.5:3b", 0.0),
    ("ollama", "qwen2.5-coder:7b", 0.0),
    ("ollama", "qwen2.5-coder:3b", 0.0),
    # Groq: hosted, free-tier (rate-limited, not metered/credit-based).
    # The original three model IDs here (llama-3.3-70b-versatile,
    # llama-3.1-8b-instant) were silently removed from Groq's catalog
    # entirely at some point — confirmed live (2026-08-17) via
    # GET /openai/v1/models returning neither, and a direct chat-
    # completions call against either 404ing with no other explanation.
    # This is a real, standing risk with Groq's free tier generally (see
    # qwen/qwen3.6-27b's own "preview, may be discontinued without
    # notice" note below) — Groq gives no deprecation notice or redirect,
    # a request just starts 404ing. Replaced with openai/gpt-oss-120b/20b,
    # confirmed live working the same day. If this happens again, check
    # GET /openai/v1/models with the real API key before assuming the
    # bug is anywhere in this app's own code.
    ("groq", "openai/gpt-oss-120b", 0.0),
    ("groq", "openai/gpt-oss-20b", 0.0),
    # qwen/qwen3.6-27b is preview status per Groq (may be discontinued
    # without notice) — kept selectable anyway since it's the specific
    # Qwen variant asked for; its display name (ai_platform/schemas.py)
    # flags "preview".
    ("groq", "qwen/qwen3.6-27b", 0.0),
]

PERMISSIONS: list[tuple[str, str]] = [
    ("user:read", "View users within the tenant."),
    ("user:write", "Create, update, or deactivate users within the tenant."),
    ("org:read", "View organizations/departments/teams within the tenant."),
    ("org:write", "Create or update organizations/departments/teams within the tenant."),
    ("role:read", "View roles and their assigned permissions."),
    ("role:assign", "Assign or revoke roles for a user."),
    ("audit_event:read", "View the tenant's audit event history."),
    ("feature_flag:read", "View feature flags visible to the tenant."),
    # --- CIKG (Phase 4.5.1) — platform-level roles, not per-tenant ones,
    # per cikg-content-governance.md's "Roles and Permissions" section.
    ("cikg.content.create", "Create/edit draft CIKG content (skills, roles, categories, edges)."),
    ("cikg.content.review", "Move draft CIKG content to in_review, leave review comments."),
    ("cikg.content.approve", "Approve in_review/draft CIKG content, or reject back to draft."),
    (
        "cikg.content.deprecate",
        "Move approved CIKG content to deprecated; resolve conflicting edges.",
    ),
    (
        "cikg.content.admin",
        "All cikg.content.* permissions, plus manage CareerLevel/CareerTrack reference "
        "scales and approve tenant-private extension requests.",
    ),
]

# name -> permission codes granted
ROLES: dict[str, list[str]] = {
    "platform_admin": [code for code, _ in PERMISSIONS],  # all permissions
    "organization_admin": [
        "user:read",
        "user:write",
        "org:read",
        "org:write",
        "role:read",
        "role:assign",
        "audit_event:read",
        "feature_flag:read",
    ],
    "manager": ["user:read", "org:read"],
    "career_coach": ["user:read"],
    "employee": ["user:read"],
    "ai_service_account": [],
    # MVP 1's single-approver model: one curator role holding create
    # through approve. cikg.content.admin (reference-scale management,
    # tenant-extension approval) is deliberately platform_admin-only for
    # now, not granted here — see cikg-content-governance.md.
    "cikg_curator": ["cikg.content.create", "cikg.content.review", "cikg.content.approve"],
}


async def _seed_permissions(session: AsyncSession) -> dict[str, uuid.UUID]:
    code_to_id: dict[str, uuid.UUID] = {}
    for code, description in PERMISSIONS:
        result = await session.execute(select(PermissionModel).where(PermissionModel.code == code))
        existing = result.scalar_one_or_none()
        if existing is not None:
            code_to_id[code] = existing.id
            continue

        model = PermissionModel(id=uuid.uuid4(), code=code, description=description)
        session.add(model)
        await session.flush()
        code_to_id[code] = model.id
        logger.info("seeded_permission", code=code)

    return code_to_id


async def _seed_roles(session: AsyncSession, permission_ids_by_code: dict[str, uuid.UUID]) -> None:
    for role_name, permission_codes in ROLES.items():
        result = await session.execute(
            select(RoleModel).where(RoleModel.name == role_name, RoleModel.tenant_id.is_(None))
        )
        role = result.scalar_one_or_none()
        if role is None:
            role = RoleModel(id=uuid.uuid4(), tenant_id=None, name=role_name)
            session.add(role)
            await session.flush()
            logger.info("seeded_role", name=role_name)

        # Queried directly rather than via role.permissions (the ORM
        # relationship) — accessing that collection lazily on a
        # freshly-flushed object hit a MissingGreenlet error in practice
        # against the real async engine. A direct query sidesteps the
        # relationship-loading-strategy question entirely and is no less
        # correct for this idempotency check.
        existing_result = await session.execute(
            select(RolePermissionModel.permission_id).where(RolePermissionModel.role_id == role.id)
        )
        existing_permission_ids = set(existing_result.scalars().all())

        for code in permission_codes:
            permission_id = permission_ids_by_code[code]
            if permission_id in existing_permission_ids:
                continue
            session.add(RolePermissionModel(role_id=role.id, permission_id=permission_id))
            logger.info("seeded_role_permission", role=role_name, permission=code)


async def _seed_prompt_version(session: AsyncSession, *, use_case: str, template: str) -> None:
    """Inserts a new approved version whenever the in-code template text
    has changed since the last seed run, rather than only ever inserting
    once (the original behavior here silently kept serving a stale
    template after the RESUME_EXTRACTION_PROMPT_TEMPLATE constant was
    edited — a real gap, since editing this file is otherwise the only
    way prompts get updated in this codebase). The prior version is left
    untouched (audit trail), and SqlAlchemyPromptRegistry.get_active_version
    already resolves the highest `version` among approved rows, so a
    higher-numbered row here becomes active automatically — no separate
    "deprecate the old one" step needed.
    """
    result = await session.execute(
        select(PromptVersionModel)
        .where(PromptVersionModel.name == use_case, PromptVersionModel.status == "approved")
        .order_by(PromptVersionModel.version.desc())
        .limit(1)
    )
    current = result.scalar_one_or_none()
    if current is not None and current.template == template:
        return

    next_version = current.version + 1 if current is not None else 1
    session.add(
        PromptVersionModel(
            id=uuid.uuid4(),
            name=use_case,
            version=next_version,
            template=template,
            status="approved",
            owner="platform",
            approved_by="platform",
        )
    )
    logger.info("seeded_prompt_version", name=use_case, version=next_version)


async def _seed_ai_platform_defaults(session: AsyncSession) -> None:
    settings = get_settings()

    await _seed_prompt_version(
        session, use_case=CHAT_PROMPT_USE_CASE, template=CHAT_PROMPT_TEMPLATE
    )
    await _seed_prompt_version(
        session, use_case=RESUME_EXTRACTION_USE_CASE, template=RESUME_EXTRACTION_PROMPT_TEMPLATE
    )
    await _seed_prompt_version(
        session,
        use_case=LEARNING_RECOMMENDATIONS_USE_CASE,
        template=LEARNING_RECOMMENDATIONS_PROMPT_TEMPLATE,
    )
    await _seed_prompt_version(
        session,
        use_case=INTERVIEW_ANSWER_GENERATION_USE_CASE,
        template=INTERVIEW_ANSWER_GENERATION_PROMPT_TEMPLATE,
    )

    result = await session.execute(select(ModelVersionModel))
    existing_by_name = {model.model_name: model for model in result.scalars().all()}

    for provider, model_name, cost_per_1k_tokens in MODEL_CATALOG:
        if model_name in existing_by_name:
            continue
        session.add(
            ModelVersionModel(
                id=uuid.uuid4(),
                provider=provider,
                model_name=model_name,
                version="1",
                status="active",
                cost_per_1k_tokens=cost_per_1k_tokens,
                is_default=(model_name == settings.ai_default_model),
            )
        )
        logger.info("seeded_model_version", model_name=model_name)
    await session.flush()

    # If nothing in the catalog matches AI_DEFAULT_MODEL (e.g. it was
    # changed to a model not yet in MODEL_CATALOG) and no row is marked
    # default yet, fall back to the first catalog entry rather than
    # leaving the platform with no default at all.
    result = await session.execute(
        select(ModelVersionModel).where(ModelVersionModel.is_default.is_(True))
    )
    if result.scalar_one_or_none() is None:
        result = await session.execute(
            select(ModelVersionModel).where(ModelVersionModel.status == "active").limit(1)
        )
        fallback = result.scalar_one_or_none()
        if fallback is not None:
            fallback.is_default = True
            logger.info("defaulted_model_version", model_name=fallback.model_name)


async def _seed_platform_settings_defaults(session: AsyncSession) -> None:
    """Seeds the two settings the admin page (Settings > Platform Admin)
    was built to make editable — from the current env values, so a fresh
    environment starts with exactly today's behavior. Never overwrites
    an existing row (an admin's real edit must never be clobbered by a
    reseed), matching _seed_permissions/_seed_roles's own idempotency.
    """
    settings = get_settings()
    defaults: list[tuple[str, str, str]] = [
        (
            "resend_from_email",
            settings.resend_from_email,
            "Default sender address for account emails (verification links, password resets).",
        ),
        (
            "resend_welcome_from_email",
            settings.resend_welcome_from_email,
            "Sender address for the post-signup welcome email.",
        ),
    ]
    for key, value, description in defaults:
        result = await session.execute(
            select(PlatformSettingModel).where(PlatformSettingModel.key == key)
        )
        if result.scalar_one_or_none() is not None:
            continue
        session.add(
            PlatformSettingModel(id=uuid.uuid4(), key=key, value=value, description=description)
        )
        logger.info("seeded_platform_setting", key=key)


def _parse_bootstrap_accounts(raw: str) -> list[tuple[str | None, str]]:
    """Parses PLATFORM_ADMIN_BOOTSTRAP_ACCOUNTS into (subdomain, email)
    pairs — subdomain is None for a bare email (Personal account).
    "subdomain:email" (Enterprise) splits on the *last* colon so an
    email itself never needs escaping.
    """
    accounts: list[tuple[str | None, str]] = []
    for entry in raw.split(","):
        entry = entry.strip()
        if not entry:
            continue
        if ":" in entry:
            subdomain, email = entry.rsplit(":", 1)
            accounts.append((subdomain.strip(), email.strip()))
        else:
            accounts.append((None, entry))
    return accounts


async def _seed_platform_admin_bootstrap(session: AsyncSession) -> None:
    """Grants every account in PLATFORM_ADMIN_BOOTSTRAP_ACCOUNTS every
    platform.* permission, if not already granted — the one seed-time
    step the admin page genuinely needs, since with zero admins granted,
    nobody could ever reach the page to grant the first one. Resolves
    each account the same way login does (derive_personal_subdomain for
    a bare email, the explicit subdomain for "subdomain:email"). Skips
    (logs and continues) any account that doesn't exist yet — this can
    run before that account has signed up in a brand-new environment, so
    "account not found yet" is expected, not an error.
    """
    accounts = _parse_bootstrap_accounts(get_settings().platform_admin_bootstrap_accounts)
    for subdomain, email in accounts:
        resolved_subdomain = subdomain or derive_personal_subdomain(email)
        tenant_result = await session.execute(
            select(TenantModel).where(TenantModel.subdomain == resolved_subdomain)
        )
        tenant = tenant_result.scalar_one_or_none()
        if tenant is None:
            logger.info("platform_admin_bootstrap_skipped_no_account", email=email)
            continue

        # users is RLS-forced — must bind tenant context before this
        # query, same as every other cross-tenant-resolution flow in
        # this codebase (e.g. AuthenticateUserService.execute).
        await set_tenant_context(session, tenant.id)
        user_result = await session.execute(
            select(UserModel).where(UserModel.tenant_id == tenant.id, UserModel.email == email)
        )
        user = user_result.scalar_one_or_none()
        if user is None:
            logger.info("platform_admin_bootstrap_skipped_no_account", email=email)
            continue

        grant_result = await session.execute(
            select(PlatformAdminModel).where(
                PlatformAdminModel.tenant_id == tenant.id, PlatformAdminModel.user_id == user.id
            )
        )
        if grant_result.scalar_one_or_none() is not None:
            continue

        full_name = (
            " ".join(part for part in (user.salutation, user.first_name, user.last_name) if part)
            or user.email
        )
        session.add(
            PlatformAdminModel(
                id=uuid.uuid4(),
                tenant_id=tenant.id,
                user_id=user.id,
                email=user.email,
                full_name=full_name,
                permission_codes=sorted(ALL_PLATFORM_PERMISSION_CODES),
                # Self-attributed — there's no other admin to credit
                # this bootstrap grant to.
                granted_by_user_id=user.id,
            )
        )
        logger.info("seeded_platform_admin_bootstrap", email=email)


async def seed_platform_defaults() -> None:
    async with async_session_factory() as session:
        permission_ids_by_code = await _seed_permissions(session)
        await _seed_roles(session, permission_ids_by_code)
        await _seed_ai_platform_defaults(session)
        await _seed_platform_settings_defaults(session)
        await _seed_platform_admin_bootstrap(session)
        await session.commit()
    logger.info("seed_complete")


if __name__ == "__main__":
    asyncio.run(seed_platform_defaults())
