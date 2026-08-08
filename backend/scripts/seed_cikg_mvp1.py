"""Seed the CIKG MVP 1 (Phase 4.5.1) architecture-validation dataset.

Fully specified in docs/architecture/cikg-mvp1-seed-data.md: 5 domains
(Technology & Engineering, Healthcare & Clinical, Finance & Accounting,
Skilled Trades, Sales), 97 skills total with category placement, a
`related_to` ontology edge set, 13 example Roles exercising `requires`,
and 7 `skill_alias` examples. This is the platform's
architecture-validation dataset, not a claim of curatorial completeness
— see that document's "Explicit Non-Goals" section.

**Scope decision made when Phase 4.5.1 build started:** the roadmap
(cikg-mvp-roadmap.md) defers `prerequisite_of`/`specializes`/`synonym_of`
to MVP 2B (they need the cycle-detection-at-approval workflow that ships
then), but the seed-data spec's worked examples use `prerequisite_of`
and `specializes` throughout. Per explicit user direction, this seed
script follows the roadmap strictly: every `prerequisite_of`/
`specializes` edge listed in the source spec is dropped here, seeding
only `related_to` edges. Each domain still gets at least one ontology
edge per MVP 1's exit criterion — Healthcare's only edges in the source
spec are prerequisite_of/specializes, but it picks up a `related_to`
edge via the spec's own cross-domain edge set (Risk Analysis <->
Clinical Risk Assessment), so the exit criterion still holds. Re-adding
prerequisite_of/specializes is deferred to MVP 2B alongside the
governance workflow they depend on.

Content is inserted directly at content_status="approved",
source_attribution="seed_script" — the same "hand-curated, no draft
step" precedent app/scripts/seed_platform_defaults.py already sets for
CHAT_PROMPT_TEMPLATE. Idempotent: every insert is a get-or-create keyed
on the natural identity of that row (skill/role/competency name,
category name + parent, edge endpoint pair, alias normalized text) —
safe to re-run.

Run after migrations, typically right after seed_platform_defaults.py:

    python scripts/seed_cikg_mvp1.py
"""

from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.db.base import async_session_factory
from app.adapters.db.models import (
    CategoryParentModel,
    CikgRoleModel,
    RelatedSkillModel,
    RoleRequiredSkillModel,
    SkillAliasModel,
    SkillCategoryMembershipModel,
    SkillCategoryModel,
    SkillModel,
)
from app.core.logging import get_logger
from app.domain.career_intelligence.aliasing import normalize_alias_text

logger = get_logger(__name__)

SOURCE = "seed_script"


@dataclass(frozen=True, slots=True)
class SkillSpec:
    name: str
    categories: tuple[str, ...]  # leaf category name(s) — some skills are multi-category
    description: str


@dataclass(frozen=True, slots=True)
class RoleSpec:
    title: str
    # (skill_name, requirement_level)
    requires: tuple[tuple[str, str], ...]


@dataclass(frozen=True, slots=True)
class DomainSpec:
    name: str  # top-level (root) category
    # level-2 category name -> level-3 (leaf) category names
    tree: dict[str, tuple[str, ...]]
    skills: tuple[SkillSpec, ...]
    # (skill_a, skill_b, strength) — related_to only, see module docstring
    related_edges: tuple[tuple[str, str, str], ...]
    roles: tuple[RoleSpec, ...]


DOMAINS: tuple[DomainSpec, ...] = (
    DomainSpec(
        name="Technology & Engineering",
        tree={
            "Software Development": ("Programming Languages", "Software Architecture"),
            "Data & AI": ("Data Analysis", "Machine Learning"),
            "Infrastructure & Security": ("Cloud & Platform", "Security"),
            "Delivery Practices": ("Agile Delivery",),
        },
        skills=(
            SkillSpec("Python Programming", ("Programming Languages",), "General-purpose programming in Python"),
            SkillSpec("JavaScript Programming", ("Programming Languages",), "Web/application programming in JavaScript"),
            SkillSpec("SQL & Relational Database Querying", ("Programming Languages", "Data Analysis"), "Writing and optimizing relational queries"),
            SkillSpec("Software Architecture Design", ("Software Architecture",), "Structuring systems for maintainability and scale"),
            SkillSpec("API Design", ("Software Architecture",), "Designing consistent, versionable service interfaces"),
            SkillSpec("Microservices Design", ("Software Architecture",), "Decomposing systems into independently deployable services"),
            SkillSpec("Data Analysis", ("Data Analysis",), "Extracting insight from structured data"),
            SkillSpec("Statistical Modeling", ("Data Analysis",), "Applying statistical methods to explain/predict data"),
            SkillSpec("Data Pipeline Engineering", ("Data Analysis",), "Building reliable data ingestion/transformation pipelines"),
            SkillSpec("Machine Learning", ("Machine Learning",), "Training models that learn from data"),
            SkillSpec("Deep Learning", ("Machine Learning",), "Neural-network-based machine learning"),
            SkillSpec("Cloud Infrastructure Management", ("Cloud & Platform",), "Provisioning/operating cloud-hosted infrastructure"),
            SkillSpec("Container Orchestration", ("Cloud & Platform",), "Managing containerized workloads at scale"),
            SkillSpec("DevOps Practices", ("Cloud & Platform",), "Integrating development and operations workflows"),
            SkillSpec("CI/CD Pipeline Management", ("Cloud & Platform",), "Automating build/test/deploy pipelines"),
            SkillSpec("Test Automation", ("Cloud & Platform",), "Automated verification of software behavior"),
            SkillSpec("Cybersecurity Fundamentals", ("Security",), "Core principles of protecting systems and data"),
            SkillSpec("Network Security", ("Security",), "Securing network infrastructure and traffic"),
            SkillSpec("Sprint Planning", ("Agile Delivery",), "Planning near-term iterative delivery work"),
            SkillSpec("PI Planning", ("Agile Delivery",), "Cross-team planning across a multi-sprint increment (SAFe)"),
            SkillSpec("Flow Metrics", ("Agile Delivery",), "Measuring delivery flow/throughput"),
            SkillSpec("Enterprise Agile Coaching", ("Agile Delivery",), "Coaching organizational agile transformation at scale"),
            SkillSpec("Technical Requirements Analysis", ("Agile Delivery",), "Translating business needs into technical requirements"),
            SkillSpec("Technical Documentation", ("Software Architecture",), "Writing documentation for technical systems"),
        ),
        related_edges=(
            ("Python Programming", "Data Analysis", "moderate"),
            ("SQL & Relational Database Querying", "Data Analysis", "strong"),
            ("Cloud Infrastructure Management", "Container Orchestration", "strong"),
            ("DevOps Practices", "CI/CD Pipeline Management", "strong"),
            ("Sprint Planning", "PI Planning", "moderate"),
            ("Enterprise Agile Coaching", "Flow Metrics", "moderate"),
        ),
        roles=(
            RoleSpec("Software Engineer II", (("Python Programming", "required"), ("Software Architecture Design", "preferred"), ("API Design", "preferred"))),
            RoleSpec("Cloud Platform Engineer", (("Cloud Infrastructure Management", "required"), ("Container Orchestration", "required"), ("DevOps Practices", "preferred"))),
            RoleSpec("Enterprise Agile Coach", (("Enterprise Agile Coaching", "required"), ("PI Planning", "required"), ("Flow Metrics", "preferred"), ("Technical Requirements Analysis", "preferred"))),
        ),
    ),
    DomainSpec(
        name="Healthcare & Clinical",
        tree={
            "Clinical Practice": ("Patient Care", "Surgical Skills"),
            "Nursing Practice": ("General Nursing", "Specialized Nursing"),
            "Health Information & Compliance": ("Regulatory",),
            "Clinical Leadership": ("Care Coordination",),
        },
        skills=(
            SkillSpec("Patient Assessment", ("Patient Care",), "Evaluating a patient's condition systematically"),
            SkillSpec("Patient Care Planning", ("Patient Care",), "Developing individualized care plans"),
            SkillSpec("Vital Signs Monitoring", ("Patient Care",), "Tracking core physiological indicators"),
            SkillSpec("Sterile Technique", ("Surgical Skills",), "Maintaining an aseptic field during procedures"),
            SkillSpec("Suturing", ("Surgical Skills",), "Closing wounds/incisions"),
            SkillSpec("Laparoscopic Technique", ("Surgical Skills",), "Minimally invasive surgical procedure skill"),
            SkillSpec("Registered Nursing (General Practice)", ("General Nursing",), "Core RN scope of practice"),
            SkillSpec("Medication Administration", ("General Nursing",), "Safely administering prescribed medication"),
            SkillSpec("Clinical Documentation", ("General Nursing",), "Accurate, compliant clinical record-keeping"),
            SkillSpec("IV Therapy", ("General Nursing",), "Administering intravenous treatment"),
            SkillSpec("Infection Control", ("General Nursing",), "Preventing/managing infection transmission"),
            SkillSpec("ICU Nursing", ("Specialized Nursing",), "Critical-care nursing practice"),
            SkillSpec("Pediatric Nursing", ("Specialized Nursing",), "Nursing practice for infants/children"),
            SkillSpec("Emergency Nursing", ("Specialized Nursing",), "Nursing practice in emergency/trauma settings"),
            SkillSpec("HIPAA Compliance", ("Regulatory",), "U.S. patient-data privacy compliance"),
            SkillSpec("Electronic Health Records (EHR) Management", ("Regulatory",), "Maintaining/using digital health record systems"),
            SkillSpec("Clinical Coding (ICD-10)", ("Regulatory",), "Coding diagnoses/procedures for billing and records"),
            SkillSpec("Care Coordination", ("Care Coordination",), "Organizing care across providers/settings"),
            SkillSpec("Interdisciplinary Team Collaboration", ("Care Coordination",), "Working across clinical disciplines"),
            SkillSpec("Patient Education", ("Care Coordination",), "Teaching patients about their condition/care"),
            SkillSpec("Clinical Risk Assessment", ("Care Coordination",), "Identifying/mitigating patient-safety risk"),
            SkillSpec("Discharge Planning", ("Care Coordination",), "Planning a patient's transition out of care"),
        ),
        related_edges=(),  # see module docstring — this domain's edges are cross-domain only
        roles=(
            RoleSpec("Registered Nurse", (("Registered Nursing (General Practice)", "required"), ("Medication Administration", "required"), ("Clinical Documentation", "required"))),
            RoleSpec("ICU Nurse", (("ICU Nursing", "required"), ("Patient Assessment", "required"), ("Vital Signs Monitoring", "required"))),
            RoleSpec("Surgical Technologist", (("Sterile Technique", "required"), ("Infection Control", "required"), ("Suturing", "preferred"))),
        ),
    ),
    DomainSpec(
        name="Finance & Accounting",
        tree={
            "Financial Reporting": ("Accounting", "Reporting"),
            "Risk & Compliance": ("Regulatory",),
            "Investment & Analysis": ("Analysis",),
            "Corporate Finance": ("Treasury",),
        },
        skills=(
            SkillSpec("Double-Entry Bookkeeping", ("Accounting",), "Foundational dual-entry accounting method"),
            SkillSpec("GAAP Compliance", ("Accounting",), "Adhering to Generally Accepted Accounting Principles"),
            SkillSpec("Financial Statement Analysis", ("Accounting",), "Interpreting financial statements"),
            SkillSpec("Accounts Reconciliation", ("Accounting",), "Matching records across financial systems"),
            SkillSpec("Financial Modeling", ("Reporting",), "Building quantitative financial models"),
            SkillSpec("Budget Forecasting", ("Reporting",), "Projecting future financial performance"),
            SkillSpec("AML (Anti-Money Laundering)", ("Regulatory",), "Detecting/preventing money-laundering activity"),
            SkillSpec("KYC (Know Your Customer)", ("Regulatory",), "Verifying customer identity/risk profile"),
            SkillSpec("Regulatory Reporting", ("Regulatory",), "Preparing filings for financial regulators"),
            SkillSpec("Tax Compliance", ("Regulatory",), "Meeting tax filing/reporting obligations"),
            SkillSpec("Valuation Analysis", ("Analysis",), "Determining the value of an asset/company"),
            SkillSpec("Risk Analysis", ("Analysis",), "Identifying/quantifying financial risk"),
            SkillSpec("Portfolio Analysis", ("Analysis",), "Evaluating investment portfolio performance"),
            SkillSpec("Credit Risk Modeling", ("Analysis",), "Modeling likelihood of borrower default"),
            SkillSpec("Fraud Detection Analysis", ("Analysis",), "Identifying fraudulent financial activity"),
            SkillSpec("Cash Flow Management", ("Treasury",), "Managing an organization's liquidity"),
            SkillSpec("Capital Structure Analysis", ("Treasury",), "Analyzing debt/equity financing mix"),
            SkillSpec("Mergers & Acquisitions Analysis", ("Treasury",), "Evaluating M&A transactions"),
            SkillSpec("Audit Planning", ("Accounting",), "Planning the scope/approach of a financial audit"),
        ),
        related_edges=(
            ("GAAP Compliance", "Financial Statement Analysis", "strong"),
            ("AML (Anti-Money Laundering)", "KYC (Know Your Customer)", "strong"),
        ),
        roles=(
            RoleSpec("Financial Analyst", (("Financial Statement Analysis", "required"), ("Financial Modeling", "required"), ("Valuation Analysis", "preferred"))),
            RoleSpec("AML Compliance Officer", (("AML (Anti-Money Laundering)", "required"), ("KYC (Know Your Customer)", "required"), ("Regulatory Reporting", "required"))),
            RoleSpec("Investment Banking Associate", (("Valuation Analysis", "required"), ("Mergers & Acquisitions Analysis", "required"), ("Financial Modeling", "required"))),
        ),
    ),
    DomainSpec(
        name="Skilled Trades",
        tree={
            "Electrical": ("Residential", "Industrial"),
            "Construction": ("General",),
            "Trade Compliance": ("Codes & Safety",),
        },
        skills=(
            SkillSpec("Residential Wiring", ("Residential",), "Installing/repairing residential electrical systems"),
            SkillSpec("Panel Installation", ("Residential",), "Installing electrical distribution panels"),
            SkillSpec("Electrical Troubleshooting", ("Residential", "Industrial"), "Diagnosing electrical faults"),
            SkillSpec("Industrial Controls Wiring", ("Industrial",), "Wiring industrial control systems"),
            SkillSpec("PLC Programming Basics", ("Industrial",), "Basic programmable logic controller programming"),
            SkillSpec("Blueprint Reading", ("General",), "Interpreting construction drawings"),
            SkillSpec("Structural Framing", ("General",), "Building structural wood/metal framing"),
            SkillSpec("Concrete Work", ("General",), "Forming, pouring, and finishing concrete"),
            SkillSpec("Welding", ("General",), "Joining metal components by welding"),
            SkillSpec("Plumbing Systems Installation", ("General",), "Installing residential/commercial plumbing"),
            SkillSpec("HVAC Systems Installation", ("General",), "Installing heating/cooling systems"),
            SkillSpec("Equipment Maintenance & Repair", ("General",), "Maintaining and repairing trade equipment"),
            SkillSpec("Project Estimating (Trades)", ("Codes & Safety",), "Estimating labor/material cost for trade work"),
            SkillSpec("NEC Code Compliance", ("Codes & Safety",), "Complying with the National Electrical Code"),
            SkillSpec("OSHA Safety Compliance", ("Codes & Safety",), "Complying with workplace safety regulations"),
            SkillSpec("Permit & Inspection Coordination", ("Codes & Safety",), "Managing permitting/inspection processes"),
        ),
        related_edges=(
            ("NEC Code Compliance", "Residential Wiring", "strong"),
            ("NEC Code Compliance", "Industrial Controls Wiring", "strong"),
            ("OSHA Safety Compliance", "Structural Framing", "moderate"),
        ),
        roles=(
            RoleSpec("Journeyman Electrician", (("Residential Wiring", "required"), ("NEC Code Compliance", "required"), ("Electrical Troubleshooting", "preferred"))),
            RoleSpec("General Contractor", (("Blueprint Reading", "required"), ("Structural Framing", "required"), ("Permit & Inspection Coordination", "required"), ("Project Estimating (Trades)", "required"))),
        ),
    ),
    DomainSpec(
        name="Sales",
        tree={
            "Revenue Generation": ("Prospecting", "Closing"),
            "Account Management": ("Relationship Management",),
            "Sales Operations": ("Enablement",),
        },
        skills=(
            SkillSpec("Prospecting", ("Prospecting",), "Identifying potential customers"),
            SkillSpec("Lead Qualification", ("Prospecting",), "Assessing whether a lead is worth pursuing"),
            SkillSpec("Cold Outreach", ("Prospecting",), "Initiating contact with unengaged prospects"),
            SkillSpec("Consultative Selling", ("Closing",), "Selling by diagnosing and addressing customer need"),
            SkillSpec("Enterprise Negotiation", ("Closing",), "Negotiating complex, high-value deals"),
            SkillSpec("Objection Handling", ("Closing",), "Responding effectively to buyer objections"),
            SkillSpec("Contract Negotiation", ("Closing",), "Negotiating deal/contract terms"),
            SkillSpec("Account Management", ("Relationship Management",), "Managing ongoing customer relationships"),
            SkillSpec("Customer Retention Strategy", ("Relationship Management",), "Strategies to retain existing customers"),
            SkillSpec("Upselling & Cross-Selling", ("Relationship Management",), "Expanding revenue within existing accounts"),
            SkillSpec("CRM Data Management", ("Enablement",), "Maintaining accurate CRM records"),
            SkillSpec("Sales Forecasting", ("Enablement",), "Predicting future sales performance"),
            SkillSpec("Pipeline Management", ("Enablement",), "Managing deals through the sales process"),
            SkillSpec("Competitive Positioning", ("Enablement",), "Positioning offerings against competitors"),
            SkillSpec("Value Proposition Development", ("Enablement",), "Articulating a compelling value proposition"),
            SkillSpec("Sales Presentation Design", ("Enablement",), "Building effective sales presentations"),
        ),
        related_edges=(
            ("Consultative Selling", "Enterprise Negotiation", "moderate"),
            ("CRM Data Management", "Pipeline Management", "strong"),
            ("Account Management", "Customer Retention Strategy", "strong"),
        ),
        roles=(
            RoleSpec("Account Executive", (("Prospecting", "required"), ("Consultative Selling", "required"), ("Enterprise Negotiation", "preferred"))),
            RoleSpec("Customer Success Manager", (("Account Management", "required"), ("Customer Retention Strategy", "required"), ("Upselling & Cross-Selling", "preferred"))),
        ),
    ),
)

# Deliberately small (per cikg-mvp1-seed-data.md's "Cross-Domain Edges"
# section) — proof the graph provides value beyond five disconnected
# sub-graphs. "weak-to-moderate" in the source spec is rounded down to
# "moderate" here since the schema only has three discrete strength
# values.
CROSS_DOMAIN_RELATED_EDGES: tuple[tuple[str, str, str], ...] = (
    ("Risk Analysis", "Clinical Risk Assessment", "weak"),
    ("Project Estimating (Trades)", "Budget Forecasting", "moderate"),
    ("Enterprise Negotiation", "Mergers & Acquisitions Analysis", "weak"),
)

# (free_text, canonical_skill_name)
SKILL_ALIASES: tuple[tuple[str, str], ...] = (
    ("python", "Python Programming"),
    ("ml", "Machine Learning"),
    ("agile coaching", "Enterprise Agile Coaching"),
    ("financial modelling", "Financial Modeling"),
    ("aml", "AML (Anti-Money Laundering)"),
    ("ehr", "Electronic Health Records (EHR) Management"),
    ("cold calling", "Cold Outreach"),
)


@dataclass
class _SeedContext:
    """Accumulates name -> id lookups as the seed run progresses.
    Category names are NOT globally unique (see SkillCategoryModel), so
    categories are keyed by (parent_id_or_None, name) rather than name
    alone.
    """

    category_ids: dict[tuple[uuid.UUID | None, str], uuid.UUID] = field(default_factory=dict)
    skill_ids: dict[str, uuid.UUID] = field(default_factory=dict)
    role_ids: dict[str, uuid.UUID] = field(default_factory=dict)


async def _get_or_create_category(
    session: AsyncSession, ctx: _SeedContext, *, name: str, parent_id: uuid.UUID | None
) -> uuid.UUID:
    key = (parent_id, name)
    if key in ctx.category_ids:
        return ctx.category_ids[key]

    result = await session.execute(select(SkillCategoryModel).where(SkillCategoryModel.name == name))
    for candidate in result.scalars().all():
        parent_result = await session.execute(
            select(CategoryParentModel.parent_category_id).where(
                CategoryParentModel.child_category_id == candidate.id
            )
        )
        actual_parent_ids = set(parent_result.scalars().all())
        if parent_id is None:
            if not actual_parent_ids:
                ctx.category_ids[key] = candidate.id
                return candidate.id
        elif parent_id in actual_parent_ids:
            ctx.category_ids[key] = candidate.id
            return candidate.id

    model = SkillCategoryModel(
        id=uuid.uuid4(), name=name, description=None, content_status="approved",
        source_attribution=SOURCE,
    )
    session.add(model)
    await session.flush()
    if parent_id is not None:
        session.add(
            CategoryParentModel(
                id=uuid.uuid4(), child_category_id=model.id, parent_category_id=parent_id,
                content_status="approved", source_attribution=SOURCE,
            )
        )
    logger.info("seeded_skill_category", name=name, parent_id=str(parent_id) if parent_id else None)
    ctx.category_ids[key] = model.id
    return model.id


async def _get_or_create_skill(
    session: AsyncSession, ctx: _SeedContext, *, name: str, description: str
) -> uuid.UUID:
    if name in ctx.skill_ids:
        return ctx.skill_ids[name]
    result = await session.execute(select(SkillModel).where(SkillModel.name == name))
    existing = result.scalar_one_or_none()
    if existing is not None:
        ctx.skill_ids[name] = existing.id
        return existing.id
    model = SkillModel(
        id=uuid.uuid4(), name=name, description=description, content_status="approved",
        source_attribution=SOURCE,
    )
    session.add(model)
    await session.flush()
    logger.info("seeded_skill", name=name)
    ctx.skill_ids[name] = model.id
    return model.id


async def _link_skill_to_category(session: AsyncSession, *, skill_id: uuid.UUID, category_id: uuid.UUID) -> None:
    result = await session.execute(
        select(SkillCategoryMembershipModel).where(
            SkillCategoryMembershipModel.skill_id == skill_id,
            SkillCategoryMembershipModel.category_id == category_id,
        )
    )
    if result.scalar_one_or_none() is not None:
        return
    session.add(
        SkillCategoryMembershipModel(
            id=uuid.uuid4(), skill_id=skill_id, category_id=category_id,
            content_status="approved", source_attribution=SOURCE,
        )
    )


async def _get_or_create_role(
    session: AsyncSession, ctx: _SeedContext, *, title: str
) -> uuid.UUID:
    if title in ctx.role_ids:
        return ctx.role_ids[title]
    result = await session.execute(select(CikgRoleModel).where(CikgRoleModel.title == title))
    existing = result.scalar_one_or_none()
    if existing is not None:
        ctx.role_ids[title] = existing.id
        return existing.id
    model = CikgRoleModel(
        id=uuid.uuid4(), title=title, description=None, experience_level=None,
        content_status="approved", source_attribution=SOURCE,
    )
    session.add(model)
    await session.flush()
    logger.info("seeded_cikg_role", title=title)
    ctx.role_ids[title] = model.id
    return model.id


async def _link_role_requires_skill(
    session: AsyncSession, *, role_id: uuid.UUID, skill_id: uuid.UUID, requirement_level: str
) -> None:
    result = await session.execute(
        select(RoleRequiredSkillModel).where(
            RoleRequiredSkillModel.role_id == role_id, RoleRequiredSkillModel.skill_id == skill_id
        )
    )
    if result.scalar_one_or_none() is not None:
        return
    session.add(
        RoleRequiredSkillModel(
            id=uuid.uuid4(), role_id=role_id, skill_id=skill_id,
            requirement_level=requirement_level, content_status="approved",
            source_attribution=SOURCE,
        )
    )


async def _link_related_skills(
    session: AsyncSession, *, skill_a_id: uuid.UUID, skill_b_id: uuid.UUID, strength: str
) -> None:
    ordered_a, ordered_b = sorted((skill_a_id, skill_b_id))
    result = await session.execute(
        select(RelatedSkillModel).where(
            RelatedSkillModel.skill_a_id == ordered_a, RelatedSkillModel.skill_b_id == ordered_b
        )
    )
    if result.scalar_one_or_none() is not None:
        return
    session.add(
        RelatedSkillModel(
            id=uuid.uuid4(), skill_a_id=ordered_a, skill_b_id=ordered_b, strength=strength,
            content_status="approved", source_attribution=SOURCE,
        )
    )


async def _create_skill_alias_if_missing(
    session: AsyncSession, *, skill_id: uuid.UUID, alias_text: str
) -> None:
    normalized = normalize_alias_text(alias_text)
    result = await session.execute(
        select(SkillAliasModel).where(SkillAliasModel.normalized_text == normalized)
    )
    if result.scalar_one_or_none() is not None:
        return
    session.add(
        SkillAliasModel(
            id=uuid.uuid4(), skill_id=skill_id, alias_text=alias_text,
            normalized_text=normalized, source="curated", confidence=None,
        )
    )
    logger.info("seeded_skill_alias", alias_text=alias_text)


async def _seed_domain(session: AsyncSession, ctx: _SeedContext, domain: DomainSpec) -> None:
    root_id = await _get_or_create_category(session, ctx, name=domain.name, parent_id=None)

    leaf_category_ids: dict[str, uuid.UUID] = {}
    for level2_name, leaves in domain.tree.items():
        level2_id = await _get_or_create_category(session, ctx, name=level2_name, parent_id=root_id)
        for leaf_name in leaves:
            leaf_category_ids[leaf_name] = await _get_or_create_category(
                session, ctx, name=leaf_name, parent_id=level2_id
            )

    for skill_spec in domain.skills:
        skill_id = await _get_or_create_skill(
            session, ctx, name=skill_spec.name, description=skill_spec.description
        )
        for category_name in skill_spec.categories:
            await _link_skill_to_category(
                session, skill_id=skill_id, category_id=leaf_category_ids[category_name]
            )

    for skill_a_name, skill_b_name, strength in domain.related_edges:
        await _link_related_skills(
            session,
            skill_a_id=ctx.skill_ids[skill_a_name],
            skill_b_id=ctx.skill_ids[skill_b_name],
            strength=strength,
        )

    for role_spec in domain.roles:
        role_id = await _get_or_create_role(session, ctx, title=role_spec.title)
        for skill_name, requirement_level in role_spec.requires:
            await _link_role_requires_skill(
                session,
                role_id=role_id,
                skill_id=ctx.skill_ids[skill_name],
                requirement_level=requirement_level,
            )


async def seed_cikg_mvp1() -> None:
    async with async_session_factory() as session:
        ctx = _SeedContext()

        for domain in DOMAINS:
            await _seed_domain(session, ctx, domain)

        for skill_a_name, skill_b_name, strength in CROSS_DOMAIN_RELATED_EDGES:
            await _link_related_skills(
                session,
                skill_a_id=ctx.skill_ids[skill_a_name],
                skill_b_id=ctx.skill_ids[skill_b_name],
                strength=strength,
            )

        for alias_text, canonical_skill_name in SKILL_ALIASES:
            await _create_skill_alias_if_missing(
                session, skill_id=ctx.skill_ids[canonical_skill_name], alias_text=alias_text
            )

        await session.commit()
    logger.info(
        "cikg_mvp1_seed_complete",
        domains=len(DOMAINS),
        skills=sum(len(d.skills) for d in DOMAINS),
        roles=sum(len(d.roles) for d in DOMAINS),
    )


if __name__ == "__main__":
    asyncio.run(seed_cikg_mvp1())
