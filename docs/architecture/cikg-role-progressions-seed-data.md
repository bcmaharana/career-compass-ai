# CIKG — Role Progression Seed Data (Phase 6, Opportunity Intelligence)

Content specification for `scripts/seed_cikg_role_progressions.py`, the
same "concrete content spec, not architecture" role
`cikg-mvp1-seed-data.md` plays for the original skill/role catalog.
Produced because Opportunity Intelligence's career-path feature needs
real role-to-role graph data to traverse — before this, CIKG's
`prerequisite_of`/`specializes`/`synonym_of`/`related_to` edges were all
skill-to-skill only; **`role_progresses_to` is the first role-to-role
edge type this codebase has ever seeded.**

## Explicit Non-Goals

Same posture as `cikg-mvp1-seed-data.md`: this is illustrative, not
authoritative career-ladder truth. Real organizations title, order, and
branch these rungs differently — this is a plausible, small,
hand-curated dataset meant to prove the traversal mechanics work end to
end, not a claim that (for example) every "Staff Engineer" role
everywhere sits exactly one rung above every "Senior Software Engineer."
Expect revision after real usage, same as the original skill catalog.

**Correction (2026-08-15, real user feedback on the first pass)**: the
first version of this dataset included 4 cross-functional "lateral
pivot" edges, added purely to give the graph more cross-links rather
than because they reflect a genuinely common progression (e.g. `Senior
Software Engineer -> Enterprise Agile Coach`). These produced
misleading `career-path` output — every incoming edge counts as a real
"path here" for the upstream BFS, so Enterprise Agile Coach's "roles
that lead here" showed the entire software engineering IC ladder,
implying every agile coach comes from engineering. All 4 were removed
(struck through below, kept visible for context rather than silently
deleted from this doc); `Journeyman Electrician -> Project
Superintendent` was kept, since electricians moving into
site-supervision is a genuinely well-established single-domain
progression, not a speculative cross-track jump like the other 4. Only
assert an edge for a progression that's genuinely common knowledge
within one career track.

## Scope

One IC (individual-contributor) ladder plus one management/alternate
branch per each of the 5 domains `seed_cikg_mvp1.py` already
established (Technology & Engineering, Healthcare & Clinical, Finance &
Accounting, Skilled Trades, Sales). Existing roles from that seed script
are reused as real rungs wherever they naturally fit, rather than
duplicated. Result: 13 existing roles + 30 new roles = 43 `CikgRole`
rows, chained by 32 `role_progresses_to` edges (originally seeded as 36;
4 speculative cross-functional edges were removed — see the correction
note above).

## Technology & Engineering

IC ladder: Software Engineer I → **Software Engineer II** (existing) →
Senior Software Engineer → Staff Engineer → Principal Engineer.
Management branch splits off Senior Software Engineer: Engineering
Manager → Senior Engineering Manager → Director of Engineering.
**Cloud Platform Engineer** and **Enterprise Agile Coach** (both
existing roles) are *not* chained into this ladder — an earlier version
added `Senior Software Engineer -> Cloud Platform Engineer`/`-> Enterprise
Agile Coach` as speculative lateral pivots; removed per the correction
note above. Both roles currently have no `role_progresses_to` edges at
all, which surfaces honestly as "no path data yet" rather than a
fabricated one.

| Source | Target |
|---|---|
| Software Engineer I | Software Engineer II |
| Software Engineer II | Senior Software Engineer |
| Senior Software Engineer | Staff Engineer |
| Staff Engineer | Principal Engineer |
| Senior Software Engineer | Engineering Manager |
| Engineering Manager | Senior Engineering Manager |
| Senior Engineering Manager | Director of Engineering |

## Healthcare & Clinical

IC ladder: Licensed Practical Nurse → **Registered Nurse** (existing) →
Charge Nurse → Nurse Manager → Director of Nursing. Two specialization
branches off existing roles: Registered Nurse → **ICU Nurse** (existing)
→ Certified Registered Nurse Anesthetist (advanced practice); **Surgical
Technologist** (existing) → Surgical First Assistant.

| Source | Target |
|---|---|
| Licensed Practical Nurse | Registered Nurse |
| Registered Nurse | ICU Nurse |
| Registered Nurse | Charge Nurse |
| Charge Nurse | Nurse Manager |
| Nurse Manager | Director of Nursing |
| ICU Nurse | Certified Registered Nurse Anesthetist |
| Surgical Technologist | Surgical First Assistant |

## Finance & Accounting

IC ladder: **Financial Analyst** (existing) → Senior Financial Analyst →
Finance Manager → Director of Finance. **AML Compliance Officer**
(existing) → AML Compliance Manager → Chief Compliance Officer sits on
its own separate track — an earlier version added
`Senior Financial Analyst -> AML Compliance Officer` as a speculative
lateral pivot into that track; removed per the correction note above.
**Investment Banking Associate** (existing) progresses to Investment
Banking VP on its own track (deal execution rather than FP&A).

| Source | Target |
|---|---|
| Financial Analyst | Senior Financial Analyst |
| Senior Financial Analyst | Finance Manager |
| Finance Manager | Director of Finance |
| AML Compliance Officer | AML Compliance Manager |
| AML Compliance Manager | Chief Compliance Officer |
| Investment Banking Associate | Investment Banking VP |

## Skilled Trades

IC ladder: Apprentice Electrician → **Journeyman Electrician**
(existing) → Master Electrician → Electrical Contractor (business
ownership). Separate site-management branch off Journeyman Electrician:
Project Superintendent → **General Contractor** (existing) *and*
Project Superintendent → Construction Project Manager (parallel
branches — a superintendent can go into either owning the contracting
business or managing builds for a client).

| Source | Target |
|---|---|
| Apprentice Electrician | Journeyman Electrician |
| Journeyman Electrician | Master Electrician |
| Master Electrician | Electrical Contractor |
| Journeyman Electrician | Project Superintendent |
| Project Superintendent | General Contractor |
| Project Superintendent | Construction Project Manager |

## Sales

IC ladder: Sales Development Representative → **Account Executive**
(existing) → Senior Account Executive → Sales Manager → Director of
Sales. **Customer Success Manager** (existing) → Senior Customer
Success Manager → VP of Customer Success sits on its own separate
track — an earlier version added `Senior Account Executive -> Customer
Success Manager` as a speculative lateral pivot into that track;
removed per the correction note above.

| Source | Target |
|---|---|
| Sales Development Representative | Account Executive |
| Account Executive | Senior Account Executive |
| Senior Account Executive | Sales Manager |
| Sales Manager | Director of Sales |
| Customer Success Manager | Senior Customer Success Manager |
| Senior Customer Success Manager | VP of Customer Success |

## Verification

Live-verified against real dev Postgres (2026-08-15): every edge type
in this document round-tripped through the real `POST /revisions` →
`submit` → `approve` governance workflow (not just direct SQL) during
development — including confirming the reverse of an already-approved
edge is correctly blocked with `EDGE_APPROVAL_WOULD_CREATE_CYCLE`, the
same exit criterion MVP 2B's `prerequisite_of`/`specializes` cycle
detection was verified against. The actual bulk load below is inserted
directly at `content_status="approved"` by
`scripts/seed_cikg_role_progressions.py`, per the same "hand-curated, no
draft step" precedent `seed_cikg_mvp1.py` and
`reseed_cikg_prerequisite_specializes.py` already establish.
