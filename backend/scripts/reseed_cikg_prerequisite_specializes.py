"""Re-seed the `prerequisite_of`/`specializes` edges dropped from MVP 1's
seed script (Phase 4.5.1 MVP 2B).

MVP 1 seeded only `related_to` edges — `prerequisite_of`/`specializes`
were deliberately dropped, per the explicit user decision to strictly
follow cikg-mvp-roadmap.md's MVP 1 scope even though
cikg-mvp1-seed-data.md's own worked examples used them throughout (see
CLAUDE.md's Phase 4.5.1 status entry). That decision's own note said
"re-adding is in scope for MVP 2B" — this script does that, now that
DAG cycle-detection exists to make prerequisite_of/specializes safe.

Every edge below is transcribed directly from cikg-mvp1-seed-data.md's
worked examples (13 `prerequisite_of` + 3 `specializes`, spanning all 5
domains). Inserted directly at `content_status="approved"` — same
"hand-curated, no draft step" precedent as `seed_cikg_mvp1.py` itself,
bypassing ContentRevisionService (curated content a human is directly
asserting, not a workflow to exercise).

Run after seed_cikg_mvp1.py:

    python scripts/reseed_cikg_prerequisite_specializes.py
"""

from __future__ import annotations

import asyncio
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.db.base import async_session_factory
from app.adapters.db.models import PrerequisiteOfEdgeModel, SkillModel, SpecializesEdgeModel
from app.core.logging import get_logger

logger = get_logger(__name__)

SOURCE = "seed_script"

# (source_skill_name, target_skill_name) — "source is a prerequisite of target"
PREREQUISITE_OF_EDGES: tuple[tuple[str, str], ...] = (
    # Technology & Engineering
    ("Data Analysis", "Machine Learning"),
    ("Machine Learning", "Deep Learning"),
    ("Cybersecurity Fundamentals", "Network Security"),
    # Healthcare & Clinical
    ("Sterile Technique", "Suturing"),
    ("Suturing", "Laparoscopic Technique"),
    ("Patient Assessment", "Patient Care Planning"),
    # Finance & Accounting
    ("Double-Entry Bookkeeping", "Financial Statement Analysis"),
    ("Financial Statement Analysis", "Valuation Analysis"),
    ("Cash Flow Management", "Capital Structure Analysis"),
    # Skilled Trades
    ("Blueprint Reading", "Structural Framing"),
    ("Residential Wiring", "Industrial Controls Wiring"),
    # Sales
    ("Prospecting", "Lead Qualification"),
    ("Lead Qualification", "Consultative Selling"),
)

# (source_skill_name, target_skill_name) — "source specializes target"
SPECIALIZES_EDGES: tuple[tuple[str, str], ...] = (
    ("ICU Nursing", "Registered Nursing (General Practice)"),
    ("Pediatric Nursing", "Registered Nursing (General Practice)"),
    ("Emergency Nursing", "Registered Nursing (General Practice)"),
)


async def _skill_id(session: AsyncSession, name: str) -> uuid.UUID:
    result = await session.execute(select(SkillModel.id).where(SkillModel.name == name))
    skill_id = result.scalar_one_or_none()
    if skill_id is None:
        raise RuntimeError(f"Skill '{name}' not found — run seed_cikg_mvp1.py first.")
    return skill_id


async def reseed_prerequisite_specializes() -> None:
    async with async_session_factory() as session:
        prerequisite_count = 0
        for source_name, target_name in PREREQUISITE_OF_EDGES:
            source_id = await _skill_id(session, source_name)
            target_id = await _skill_id(session, target_name)
            existing = await session.execute(
                select(PrerequisiteOfEdgeModel.id).where(
                    PrerequisiteOfEdgeModel.source_skill_id == source_id,
                    PrerequisiteOfEdgeModel.target_skill_id == target_id,
                )
            )
            if existing.scalar_one_or_none() is not None:
                continue
            session.add(
                PrerequisiteOfEdgeModel(
                    id=uuid.uuid4(), source_skill_id=source_id, target_skill_id=target_id,
                    content_status="approved", source_attribution=SOURCE,
                )
            )
            prerequisite_count += 1
            logger.info("seeded_prerequisite_of", source=source_name, target=target_name)

        specializes_count = 0
        for source_name, target_name in SPECIALIZES_EDGES:
            source_id = await _skill_id(session, source_name)
            target_id = await _skill_id(session, target_name)
            existing = await session.execute(
                select(SpecializesEdgeModel.id).where(
                    SpecializesEdgeModel.source_skill_id == source_id,
                    SpecializesEdgeModel.target_skill_id == target_id,
                )
            )
            if existing.scalar_one_or_none() is not None:
                continue
            session.add(
                SpecializesEdgeModel(
                    id=uuid.uuid4(), source_skill_id=source_id, target_skill_id=target_id,
                    content_status="approved", source_attribution=SOURCE,
                )
            )
            specializes_count += 1
            logger.info("seeded_specializes", source=source_name, target=target_name)

        await session.commit()
    logger.info(
        "reseed_prerequisite_specializes_complete",
        prerequisite_of=prerequisite_count,
        specializes=specializes_count,
    )


if __name__ == "__main__":
    asyncio.run(reseed_prerequisite_specializes())
