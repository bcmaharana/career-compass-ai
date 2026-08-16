"""Seed the CIKG role-progression catalog expansion (Phase 6, Opportunity
Intelligence's career-path feature).

Fully specified in docs/architecture/cikg-role-progressions-seed-data.md.
Grows `CikgRole` from the 13 seeded by seed_cikg_mvp1.py to ~43, adding one
IC ladder and one management/alternate branch per each of the 5 existing
seed domains, chained together with the new `role_progresses_to`
directed edge (app/domain/career_intelligence/entities.py's
RoleProgressesToEdge) — the first role-to-role graph data this codebase
has ever seeded; every prior CIKG edge type is skill-to-skill only.

This is a genuine content-authoring exercise, not a claim of definitive
career-ladder truth — same "architecture-validation dataset" posture
seed_cikg_mvp1.py's own docstring takes for its skill catalog. Expect
revision after real usage, same as that dataset.

**Correction (2026-08-15, real user feedback on the first pass)**: the
first version of this script included 4 cross-functional "lateral
pivot" edges (e.g. `Senior Software Engineer -> Enterprise Agile
Coach`, `Senior Financial Analyst -> AML Compliance Officer`) added
purely to give the graph more cross-links. These produced misleading
`career-path` output — the BFS upstream traversal treats every incoming
edge as a real "path here," so Enterprise Agile Coach's "roles that
lead here" showed the entire software engineering IC ladder, implying
every agile coach comes from engineering, which isn't accurate. All 4
were removed; `Journeyman Electrician -> Project Superintendent` was
kept, since electricians moving into site-supervision roles is a
genuinely well-established single-domain progression, not a speculative
cross-track jump like the other 4. Lesson for future edges: only assert
a `role_progresses_to` edge for a progression that's genuinely common
knowledge within one career track — resist adding edges just to reduce
isolated nodes in the graph.

Content is inserted directly at content_status="approved",
source_attribution="seed_script" — the same "hand-curated, no draft
step" precedent seed_cikg_mvp1.py and reseed_cikg_prerequisite_specializes.py
already establish, bypassing ContentRevisionService (curated content a
human is directly asserting, not a workflow to exercise). Idempotent:
every role is a get-or-create keyed on title, every edge is a
get-or-create keyed on the (source, target) pair — safe to re-run.

Run after seed_cikg_mvp1.py:

    python scripts/seed_cikg_role_progressions.py
"""

from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.db.base import async_session_factory
from app.adapters.db.models import CikgRoleModel, RoleProgressesToEdgeModel
from app.core.logging import get_logger

logger = get_logger(__name__)

SOURCE = "seed_script"


@dataclass(frozen=True, slots=True)
class RoleProgressionSpec:
    title: str
    description: str
    experience_level: str


# New roles only — the 13 from seed_cikg_mvp1.py already exist and are
# referenced by title below, not redefined here.
NEW_ROLES: tuple[RoleProgressionSpec, ...] = (
    # --- Technology & Engineering ---
    RoleProgressionSpec(
        "Software Engineer I", "Entry-level individual-contributor software engineer.", "Entry"
    ),
    RoleProgressionSpec(
        "Senior Software Engineer",
        "Owns significant features/subsystems with minimal oversight.",
        "Senior",
    ),
    RoleProgressionSpec(
        "Staff Engineer", "Cross-team technical leadership without formal management.", "Staff"
    ),
    RoleProgressionSpec(
        "Principal Engineer", "Organization-wide technical direction and architecture.", "Principal"
    ),
    RoleProgressionSpec(
        "Engineering Manager",
        "First-line people management for a software engineering team.",
        "Manager",
    ),
    RoleProgressionSpec(
        "Senior Engineering Manager",
        "Manages multiple engineering teams or managers.",
        "Senior Manager",
    ),
    RoleProgressionSpec(
        "Director of Engineering",
        "Owns engineering strategy/delivery across a department.",
        "Director",
    ),
    # --- Healthcare & Clinical ---
    RoleProgressionSpec(
        "Licensed Practical Nurse",
        "Provides basic nursing care under RN/physician supervision.",
        "Entry",
    ),
    RoleProgressionSpec(
        "Charge Nurse",
        "Coordinates nursing staff and patient assignments for a shift/unit.",
        "Senior",
    ),
    RoleProgressionSpec(
        "Nurse Manager", "Manages nursing staff and operations for a unit.", "Manager"
    ),
    RoleProgressionSpec(
        "Director of Nursing", "Owns nursing strategy/standards across a facility.", "Director"
    ),
    RoleProgressionSpec(
        "Certified Registered Nurse Anesthetist",
        "Advanced-practice nurse administering anesthesia.",
        "Advanced Practice",
    ),
    RoleProgressionSpec(
        "Surgical First Assistant",
        "Assists the surgeon directly during operative procedures.",
        "Senior",
    ),
    # --- Finance & Accounting ---
    RoleProgressionSpec(
        "Senior Financial Analyst",
        "Leads complex financial analysis with less oversight.",
        "Senior",
    ),
    RoleProgressionSpec(
        "Finance Manager", "Manages a financial analysis/planning function.", "Manager"
    ),
    RoleProgressionSpec(
        "Director of Finance", "Owns financial planning & analysis strategy for an org.", "Director"
    ),
    RoleProgressionSpec(
        "AML Compliance Manager", "Manages an AML/BSA compliance program and team.", "Manager"
    ),
    RoleProgressionSpec(
        "Chief Compliance Officer", "Owns regulatory compliance strategy org-wide.", "Executive"
    ),
    RoleProgressionSpec(
        "Investment Banking VP",
        "Leads deal execution and junior banker development.",
        "Senior Manager",
    ),
    # --- Skilled Trades ---
    RoleProgressionSpec(
        "Apprentice Electrician", "Learning electrical trade under a licensed electrician.", "Entry"
    ),
    RoleProgressionSpec(
        "Master Electrician",
        "Highest electrical licensure; can design and supervise work.",
        "Senior",
    ),
    RoleProgressionSpec(
        "Electrical Contractor", "Owns/operates an electrical contracting business.", "Owner"
    ),
    RoleProgressionSpec(
        "Project Superintendent", "Oversees day-to-day on-site construction operations.", "Senior"
    ),
    RoleProgressionSpec(
        "Construction Project Manager",
        "Owns budget, schedule, and client relationship for a build.",
        "Manager",
    ),
    # --- Sales ---
    RoleProgressionSpec(
        "Sales Development Representative",
        "Generates and qualifies pipeline for account executives.",
        "Entry",
    ),
    RoleProgressionSpec(
        "Senior Account Executive",
        "Closes larger/more complex deals with less oversight.",
        "Senior",
    ),
    RoleProgressionSpec("Sales Manager", "Manages a team of account executives.", "Manager"),
    RoleProgressionSpec(
        "Director of Sales", "Owns sales strategy/quota across a region or segment.", "Director"
    ),
    RoleProgressionSpec(
        "Senior Customer Success Manager",
        "Owns the highest-value/most complex customer relationships.",
        "Senior",
    ),
    RoleProgressionSpec(
        "VP of Customer Success", "Owns customer success strategy org-wide.", "Executive"
    ),
)

# (source_title, target_title) — "source typically progresses to target".
# Existing-role titles (Software Engineer II, Cloud Platform Engineer,
# Enterprise Agile Coach, Registered Nurse, ICU Nurse, Surgical
# Technologist, Financial Analyst, AML Compliance Officer, Investment
# Banking Associate, Journeyman Electrician, General Contractor, Account
# Executive, Customer Success Manager) come from seed_cikg_mvp1.py.
PROGRESSION_EDGES: tuple[tuple[str, str], ...] = (
    # Technology & Engineering
    ("Software Engineer I", "Software Engineer II"),
    ("Software Engineer II", "Senior Software Engineer"),
    ("Senior Software Engineer", "Staff Engineer"),
    ("Staff Engineer", "Principal Engineer"),
    ("Senior Software Engineer", "Engineering Manager"),
    ("Engineering Manager", "Senior Engineering Manager"),
    ("Senior Engineering Manager", "Director of Engineering"),
    # Healthcare & Clinical
    ("Licensed Practical Nurse", "Registered Nurse"),
    ("Registered Nurse", "ICU Nurse"),
    ("Registered Nurse", "Charge Nurse"),
    ("Charge Nurse", "Nurse Manager"),
    ("Nurse Manager", "Director of Nursing"),
    ("ICU Nurse", "Certified Registered Nurse Anesthetist"),
    ("Surgical Technologist", "Surgical First Assistant"),
    # Finance & Accounting
    ("Financial Analyst", "Senior Financial Analyst"),
    ("Senior Financial Analyst", "Finance Manager"),
    ("Finance Manager", "Director of Finance"),
    ("AML Compliance Officer", "AML Compliance Manager"),
    ("AML Compliance Manager", "Chief Compliance Officer"),
    ("Investment Banking Associate", "Investment Banking VP"),
    # Skilled Trades
    ("Apprentice Electrician", "Journeyman Electrician"),
    ("Journeyman Electrician", "Master Electrician"),
    ("Master Electrician", "Electrical Contractor"),
    ("Journeyman Electrician", "Project Superintendent"),
    ("Project Superintendent", "General Contractor"),
    ("Project Superintendent", "Construction Project Manager"),
    # Sales
    ("Sales Development Representative", "Account Executive"),
    ("Account Executive", "Senior Account Executive"),
    ("Senior Account Executive", "Sales Manager"),
    ("Sales Manager", "Director of Sales"),
    ("Customer Success Manager", "Senior Customer Success Manager"),
    ("Senior Customer Success Manager", "VP of Customer Success"),
)


async def _get_or_create_role_id(
    session: AsyncSession, title: str, spec: RoleProgressionSpec | None
) -> uuid.UUID:
    result = await session.execute(select(CikgRoleModel).where(CikgRoleModel.title == title))
    existing = result.scalar_one_or_none()
    if existing is not None:
        return existing.id
    if spec is None:
        raise RuntimeError(
            f"Role '{title}' not found — run seed_cikg_mvp1.py first (it should already exist)."
        )
    model = CikgRoleModel(
        id=uuid.uuid4(),
        title=spec.title,
        description=spec.description,
        experience_level=spec.experience_level,
        content_status="approved",
        source_attribution=SOURCE,
    )
    session.add(model)
    await session.flush()
    return model.id


async def seed_role_progressions() -> None:
    specs_by_title = {spec.title: spec for spec in NEW_ROLES}

    async with async_session_factory() as session:
        role_count = 0
        for spec in NEW_ROLES:
            result = await session.execute(
                select(CikgRoleModel).where(CikgRoleModel.title == spec.title)
            )
            if result.scalar_one_or_none() is not None:
                continue
            await _get_or_create_role_id(session, spec.title, spec)
            role_count += 1
            logger.info("seeded_role", title=spec.title)
        await session.flush()

        edge_count = 0
        for source_title, target_title in PROGRESSION_EDGES:
            source_id = await _get_or_create_role_id(
                session, source_title, specs_by_title.get(source_title)
            )
            target_id = await _get_or_create_role_id(
                session, target_title, specs_by_title.get(target_title)
            )
            existing = await session.execute(
                select(RoleProgressesToEdgeModel.id).where(
                    RoleProgressesToEdgeModel.source_role_id == source_id,
                    RoleProgressesToEdgeModel.target_role_id == target_id,
                )
            )
            if existing.scalar_one_or_none() is not None:
                continue
            session.add(
                RoleProgressesToEdgeModel(
                    id=uuid.uuid4(),
                    source_role_id=source_id,
                    target_role_id=target_id,
                    content_status="approved",
                    source_attribution=SOURCE,
                )
            )
            edge_count += 1
            logger.info("seeded_role_progresses_to", source=source_title, target=target_title)

        await session.commit()

    logger.info("seed_role_progressions_complete", roles=role_count, edges=edge_count)


if __name__ == "__main__":
    asyncio.run(seed_role_progressions())
