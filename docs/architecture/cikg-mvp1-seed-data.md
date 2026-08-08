# CIKG — MVP 1 (Phase 4.5.1) Seed Data Specification

Third-review addendum. Not architecture — a concrete content
specification, produced because "5 domains, ~20-30 skills each" as a
description isn't something engineering or curation can build against
directly. This is the platform's **architecture validation dataset**:
small enough to hand-curate, structured enough to exercise every
mechanism MVP 1 needs to prove (hierarchy, ontology edges, `requires`
edges from `Role`, `skill_alias` resolution).

**Implementation note (2026-07-29):** this document's worked examples
use `prerequisite_of`/`specializes` edges throughout, but
`cikg-mvp-roadmap.md`'s MVP 1 scope explicitly defers those edge types
to MVP 2B (they need the cycle-detection-at-approval workflow that
ships then) — a real inconsistency between the two documents, not
resolved before implementation started. Per explicit user direction
when this was caught, `scripts/seed_cikg_mvp1.py` follows the roadmap
strictly: every `prerequisite_of`/`specializes` edge below was dropped
from the actual seed load, seeding only `related_to`. Re-adding them is
in scope for MVP 2B alongside the governance workflow they depend on —
**done as of 2026-07-29**: all 13 `prerequisite_of` + 3 `specializes`
edges below were re-added via
`scripts/reseed_cikg_prerequisite_specializes.py` once MVP 2B's DAG
cycle-detection shipped, transcribed directly from this document.
One consequence worth knowing: Healthcare's edges below are *entirely*
`prerequisite_of`/`specializes`, so as seeded it has zero `related_to`
edges of its own — it only satisfies the exit criterion below via the
"Cross-Domain Edges" section's Risk Analysis <-> Clinical Risk
Assessment edge. Also, `related_skills.strength` is a 3-value enum
(`weak`/`moderate`/`strong`); "Project Estimating (Trades) related_to
Budget Forecasting — weak-to-moderate" was seeded as `moderate`.

## Explicit Non-Goals

This is illustrative, not authoritative domain expertise. None of the
category boundaries, skill descriptions, or role mappings below should
be treated as final or exhaustive — a real healthcare, finance, or
trades practitioner would refine plenty of this. That refinement is
what `cikg-content-governance.md`'s ongoing curation process is for.
This dataset exists to prove the *mechanics* work end to end across
genuinely different professions, not to be the platform's permanent
content.

## Summary

| Domain | Skills | Categories | Example Roles |
|---|---|---|---|
| Technology & Engineering | 24 | 4 top-level, 8 sub | 3 |
| Healthcare & Clinical | 22 | 4 top-level, 6 sub | 3 |
| Finance & Accounting | 19 | 4 top-level, 6 sub | 3 |
| Skilled Trades | 16 | 3 top-level, 5 sub | 2 |
| Sales | 16 | 3 top-level, 5 sub | 2 |
| **Total** | **97** | | **13** |

## 1. Technology & Engineering

```
Technology & Engineering
 ├─ Software Development
 │   ├─ Programming Languages
 │   └─ Software Architecture
 ├─ Data & AI
 │   ├─ Data Analysis
 │   └─ Machine Learning
 ├─ Infrastructure & Security
 │   ├─ Cloud & Platform
 │   └─ Security
 └─ Delivery Practices
     └─ Agile Delivery
```

| Skill | Category | Description |
|---|---|---|
| Python Programming | Programming Languages | General-purpose programming in Python |
| JavaScript Programming | Programming Languages | Web/application programming in JavaScript |
| SQL & Relational Database Querying | Programming Languages, Data Analysis *(multi-category)* | Writing and optimizing relational queries |
| Software Architecture Design | Software Architecture | Structuring systems for maintainability and scale |
| API Design | Software Architecture | Designing consistent, versionable service interfaces |
| Microservices Design | Software Architecture | Decomposing systems into independently deployable services |
| Data Analysis | Data Analysis | Extracting insight from structured data |
| Statistical Modeling | Data Analysis | Applying statistical methods to explain/predict data |
| Data Pipeline Engineering | Data Analysis | Building reliable data ingestion/transformation pipelines |
| Machine Learning | Machine Learning | Training models that learn from data |
| Deep Learning | Machine Learning | Neural-network-based machine learning |
| Cloud Infrastructure Management | Cloud & Platform | Provisioning/operating cloud-hosted infrastructure |
| Container Orchestration | Cloud & Platform | Managing containerized workloads at scale |
| DevOps Practices | Cloud & Platform | Integrating development and operations workflows |
| CI/CD Pipeline Management | Cloud & Platform | Automating build/test/deploy pipelines |
| Test Automation | Cloud & Platform | Automated verification of software behavior |
| Cybersecurity Fundamentals | Security | Core principles of protecting systems and data |
| Network Security | Security | Securing network infrastructure and traffic |
| Sprint Planning | Agile Delivery | Planning near-term iterative delivery work |
| PI Planning | Agile Delivery | Cross-team planning across a multi-sprint increment (SAFe) |
| Flow Metrics | Agile Delivery | Measuring delivery flow/throughput |
| Enterprise Agile Coaching | Agile Delivery | Coaching organizational agile transformation at scale |
| Technical Requirements Analysis | Agile Delivery | Translating business needs into technical requirements |
| Technical Documentation | Software Architecture | Writing documentation for technical systems |

**Ontology edges:**
`Python Programming` `related_to` `Data Analysis` (moderate) ·
`SQL & Relational Database Querying` `related_to` `Data Analysis`
(strong) · `Data Analysis` `prerequisite_of` `Machine Learning` ·
`Machine Learning` `prerequisite_of` `Deep Learning` ·
`Cloud Infrastructure Management` `related_to` `Container
Orchestration` (strong) · `DevOps Practices` `related_to` `CI/CD
Pipeline Management` (strong) · `Cybersecurity Fundamentals`
`prerequisite_of` `Network Security` · `Sprint Planning` `related_to`
`PI Planning` (moderate) · `Enterprise Agile Coaching` `related_to`
`Flow Metrics` (moderate)

**Example Roles (`requires` edges):**
- **Software Engineer II** — requires: Python Programming (required),
  Software Architecture Design (preferred), API Design (preferred)
- **Cloud Platform Engineer** — requires: Cloud Infrastructure
  Management (required), Container Orchestration (required), DevOps
  Practices (preferred)
- **Enterprise Agile Coach** — requires: Enterprise Agile Coaching
  (required), PI Planning (required), Flow Metrics (preferred),
  Technical Requirements Analysis (preferred) — kept as one of thirteen
  example roles here, deliberately not the dominant example the way it
  was in the source spec and the foundational-pass documents.

## 2. Healthcare & Clinical

```
Healthcare & Clinical
 ├─ Clinical Practice
 │   ├─ Patient Care
 │   └─ Surgical Skills
 ├─ Nursing Practice
 │   ├─ General Nursing
 │   └─ Specialized Nursing
 ├─ Health Information & Compliance
 │   └─ Regulatory
 └─ Clinical Leadership
     └─ Care Coordination
```

| Skill | Category | Description |
|---|---|---|
| Patient Assessment | Patient Care | Evaluating a patient's condition systematically |
| Patient Care Planning | Patient Care | Developing individualized care plans |
| Vital Signs Monitoring | Patient Care | Tracking core physiological indicators |
| Sterile Technique | Surgical Skills | Maintaining an aseptic field during procedures |
| Suturing | Surgical Skills | Closing wounds/incisions |
| Laparoscopic Technique | Surgical Skills | Minimally invasive surgical procedure skill |
| Registered Nursing (General Practice) | General Nursing | Core RN scope of practice |
| Medication Administration | General Nursing | Safely administering prescribed medication |
| Clinical Documentation | General Nursing | Accurate, compliant clinical record-keeping |
| IV Therapy | General Nursing | Administering intravenous treatment |
| Infection Control | General Nursing | Preventing/managing infection transmission |
| ICU Nursing | Specialized Nursing | Critical-care nursing practice |
| Pediatric Nursing | Specialized Nursing | Nursing practice for infants/children |
| Emergency Nursing | Specialized Nursing | Nursing practice in emergency/trauma settings |
| HIPAA Compliance | Regulatory | U.S. patient-data privacy compliance |
| Electronic Health Records (EHR) Management | Regulatory | Maintaining/using digital health record systems |
| Clinical Coding (ICD-10) | Regulatory | Coding diagnoses/procedures for billing and records |
| Care Coordination | Care Coordination | Organizing care across providers/settings |
| Interdisciplinary Team Collaboration | Care Coordination | Working across clinical disciplines |
| Patient Education | Care Coordination | Teaching patients about their condition/care |
| Clinical Risk Assessment | Care Coordination | Identifying/mitigating patient-safety risk |
| Discharge Planning | Care Coordination | Planning a patient's transition out of care |

**Ontology edges:**
`Sterile Technique` `prerequisite_of` `Suturing` ·
`Suturing` `prerequisite_of` `Laparoscopic Technique` ·
`Patient Assessment` `prerequisite_of` `Patient Care Planning` ·
`ICU Nursing` `specializes` `Registered Nursing (General Practice)` ·
`Pediatric Nursing` `specializes` `Registered Nursing (General
Practice)` · `Emergency Nursing` `specializes` `Registered Nursing
(General Practice)` — the exact `specializes` shape
`cikg-skill-ontology.md` used as its worked example, now populated for
real.

**Example Roles:**
- **Registered Nurse** — requires: Registered Nursing (General
  Practice) (required), Medication Administration (required), Clinical
  Documentation (required)
- **ICU Nurse** — requires: ICU Nursing (required), Patient Assessment
  (required), Vital Signs Monitoring (required)
- **Surgical Technologist** — requires: Sterile Technique (required),
  Infection Control (required), Suturing (preferred)

## 3. Finance & Accounting

```
Finance & Accounting
 ├─ Financial Reporting
 │   ├─ Accounting
 │   └─ Reporting
 ├─ Risk & Compliance
 │   └─ Regulatory
 ├─ Investment & Analysis
 │   └─ Analysis
 └─ Corporate Finance
     └─ Treasury
```

| Skill | Category | Description |
|---|---|---|
| Double-Entry Bookkeeping | Accounting | Foundational dual-entry accounting method |
| GAAP Compliance | Accounting | Adhering to Generally Accepted Accounting Principles |
| Financial Statement Analysis | Accounting | Interpreting financial statements |
| Accounts Reconciliation | Accounting | Matching records across financial systems |
| Financial Modeling | Reporting | Building quantitative financial models |
| Budget Forecasting | Reporting | Projecting future financial performance |
| AML (Anti-Money Laundering) | Regulatory | Detecting/preventing money-laundering activity |
| KYC (Know Your Customer) | Regulatory | Verifying customer identity/risk profile |
| Regulatory Reporting | Regulatory | Preparing filings for financial regulators |
| Tax Compliance | Regulatory | Meeting tax filing/reporting obligations |
| Valuation Analysis | Analysis | Determining the value of an asset/company |
| Risk Analysis | Analysis | Identifying/quantifying financial risk |
| Portfolio Analysis | Analysis | Evaluating investment portfolio performance |
| Credit Risk Modeling | Analysis | Modeling likelihood of borrower default |
| Fraud Detection Analysis | Analysis | Identifying fraudulent financial activity |
| Cash Flow Management | Treasury | Managing an organization's liquidity |
| Capital Structure Analysis | Treasury | Analyzing debt/equity financing mix |
| Mergers & Acquisitions Analysis | Treasury | Evaluating M&A transactions |
| Audit Planning | Accounting | Planning the scope/approach of a financial audit |

**Ontology edges:**
`Double-Entry Bookkeeping` `prerequisite_of` `Financial Statement
Analysis` — the exact example already used in `cikg-skill-ontology.md`,
now a real seed edge · `Financial Statement Analysis`
`prerequisite_of` `Valuation Analysis` · `GAAP Compliance`
`related_to` `Financial Statement Analysis` (strong) · `AML
(Anti-Money Laundering)` `related_to` `KYC (Know Your Customer)`
(strong) · `Cash Flow Management` `prerequisite_of` `Capital Structure
Analysis`

**Example Roles:**
- **Financial Analyst** — requires: Financial Statement Analysis
  (required), Financial Modeling (required), Valuation Analysis
  (preferred)
- **AML Compliance Officer** — requires: AML (Anti-Money Laundering)
  (required), KYC (Know Your Customer) (required), Regulatory
  Reporting (required)
- **Investment Banking Associate** — requires: Valuation Analysis
  (required), Mergers & Acquisitions Analysis (required), Financial
  Modeling (required) — the role deliberately used in
  `cikg-career-levels.md`'s "VP means something different here" example

## 4. Skilled Trades

```
Skilled Trades
 ├─ Electrical
 │   ├─ Residential
 │   └─ Industrial
 ├─ Construction
 │   └─ General
 └─ Trade Compliance
     └─ Codes & Safety
```

| Skill | Category | Description |
|---|---|---|
| Residential Wiring | Residential | Installing/repairing residential electrical systems |
| Panel Installation | Residential | Installing electrical distribution panels |
| Electrical Troubleshooting | Residential, Industrial *(multi-category)* | Diagnosing electrical faults |
| Industrial Controls Wiring | Industrial | Wiring industrial control systems |
| PLC Programming Basics | Industrial | Basic programmable logic controller programming |
| Blueprint Reading | General | Interpreting construction drawings |
| Structural Framing | General | Building structural wood/metal framing |
| Concrete Work | General | Forming, pouring, and finishing concrete |
| Welding | General | Joining metal components by welding |
| Plumbing Systems Installation | General | Installing residential/commercial plumbing |
| HVAC Systems Installation | General | Installing heating/cooling systems |
| Equipment Maintenance & Repair | General | Maintaining and repairing trade equipment |
| Project Estimating (Trades) | Codes & Safety | Estimating labor/material cost for trade work |
| NEC Code Compliance | Codes & Safety | Complying with the National Electrical Code |
| OSHA Safety Compliance | Codes & Safety | Complying with workplace safety regulations |
| Permit & Inspection Coordination | Codes & Safety | Managing permitting/inspection processes |

**Ontology edges:**
`Blueprint Reading` `prerequisite_of` `Structural Framing` ·
`Residential Wiring` `prerequisite_of` `Industrial Controls Wiring` ·
`NEC Code Compliance` `related_to` `Residential Wiring` (strong) ·
`NEC Code Compliance` `related_to` `Industrial Controls Wiring`
(strong) · `OSHA Safety Compliance` `related_to` `Structural Framing`
(moderate)

**Example Roles:**
- **Journeyman Electrician** — requires: Residential Wiring (required),
  NEC Code Compliance (required), Electrical Troubleshooting
  (preferred)
- **General Contractor** — requires: Blueprint Reading (required),
  Structural Framing (required), Permit & Inspection Coordination
  (required), Project Estimating (Trades) (required)

## 5. Sales

```
Sales
 ├─ Revenue Generation
 │   ├─ Prospecting
 │   └─ Closing
 ├─ Account Management
 │   └─ Relationship Management
 └─ Sales Operations
     └─ Enablement
```

| Skill | Category | Description |
|---|---|---|
| Prospecting | Prospecting | Identifying potential customers |
| Lead Qualification | Prospecting | Assessing whether a lead is worth pursuing |
| Cold Outreach | Prospecting | Initiating contact with unengaged prospects |
| Consultative Selling | Closing | Selling by diagnosing and addressing customer need |
| Enterprise Negotiation | Closing | Negotiating complex, high-value deals |
| Objection Handling | Closing | Responding effectively to buyer objections |
| Contract Negotiation | Closing | Negotiating deal/contract terms |
| Account Management | Relationship Management | Managing ongoing customer relationships |
| Customer Retention Strategy | Relationship Management | Strategies to retain existing customers |
| Upselling & Cross-Selling | Relationship Management | Expanding revenue within existing accounts |
| CRM Data Management | Enablement | Maintaining accurate CRM records |
| Sales Forecasting | Enablement | Predicting future sales performance |
| Pipeline Management | Enablement | Managing deals through the sales process |
| Competitive Positioning | Enablement | Positioning offerings against competitors |
| Value Proposition Development | Enablement | Articulating a compelling value proposition |
| Sales Presentation Design | Enablement | Building effective sales presentations |

**Ontology edges:**
`Prospecting` `prerequisite_of` `Lead Qualification` · `Lead
Qualification` `prerequisite_of` `Consultative Selling` ·
`Consultative Selling` `related_to` `Enterprise Negotiation`
(moderate) · `CRM Data Management` `related_to` `Pipeline Management`
(strong) · `Account Management` `related_to` `Customer Retention
Strategy` (strong)

**Example Roles:**
- **Account Executive** — requires: Prospecting (required),
  Consultative Selling (required), Enterprise Negotiation (preferred)
- **Customer Success Manager** — requires: Account Management
  (required), Customer Retention Strategy (required), Upselling &
  Cross-Selling (preferred)

## Cross-Domain Edges

Deliberately included, in deliberately small number — proof that the
graph provides value beyond five disconnected sub-graphs, without
overreaching into forced/implausible connections:

- `Risk Analysis` (Finance) `related_to` `Clinical Risk Assessment`
  (Healthcare) — weak; both are domain-specific applications of the
  same underlying risk-assessment competency.
- `Project Estimating (Trades)` `related_to` `Budget Forecasting`
  (Finance) — weak-to-moderate; both are cost-forecasting disciplines.
- `Enterprise Negotiation` (Sales) `related_to` `Mergers & Acquisitions
  Analysis` (Finance) — weak; both involve structuring high-value
  deals, though from different vantage points.

## `skill_alias` Examples (Free-Text → Canonical Resolution, ADR-006 §3)

Directly exercises MVP 1's exit criterion — a free-text
`core_competencies` entry resolving to a canonical `Skill`:

| Free text | Resolves to |
|---|---|
| "python" | Python Programming |
| "ml" | Machine Learning |
| "agile coaching" | Enterprise Agile Coaching |
| "financial modelling" *(British spelling)* | Financial Modeling |
| "aml" | AML (Anti-Money Laundering) |
| "ehr" | Electronic Health Records (EHR) Management |
| "cold calling" | Cold Outreach |

## What's Intentionally Absent From This Seed Set

- **No `synonym_of` edges.** Not every edge type needs a seed instance
  — `synonym_of` specifically is left to emerge from real curation once
  `cikg-observability.md`'s "duplicate candidates" metric surfaces
  genuine merge candidates from actual content growth, rather than
  fabricating a forced example here.
- **No `CareerLevel`/`CareerTrack` assignments.** Per the narrowed MVP 4
  scope in `cikg-mvp-roadmap.md`, level/track mapping happens later and
  deliberately starts from a small, low-ambiguity set — not bundled
  into this seed data.
- **No `SkillMarketSnapshot` data.** Market Intelligence is deferred
  past MVP entirely (`cikg-mvp-roadmap.md`'s "Beyond MVP" section).

## Related Documents

- `docs/architecture/cikg-mvp-roadmap.md` — where this fits in the build sequence
- `docs/architecture/cikg-skill-ontology.md` — the hierarchy/ontology model this populates
- `docs/architecture/cikg-content-governance.md` — the ongoing curation process this seed data is a starting point for, not a substitute for
