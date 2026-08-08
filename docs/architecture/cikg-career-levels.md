# CIKG — Career Level Framework

Second-pass document. Directly addresses the requirement that the
platform "remain profession-agnostic and support careers from
entry-level to executive level across industries."

## The Core Problem

Career ladders look completely different across fields, and titles lie
about seniority constantly: "VP" is a genuinely mid-career title at a
large investment bank but a senior-executive title almost everywhere
else; "Associate" means entry-level at a consulting firm and something
close to partner-track-senior at a law firm; a "Senior" title can
appear anywhere from two to fifteen years into a career depending on
industry. A career-level model that stores seniority as a string on the
title, or infers it from years-of-experience, breaks immediately across
professions.

**Resolution: decouple three things that are usually conflated into one
"level" field.**

| Dimension | Answers | Modeled as |
|---|---|---|
| **Level** | How much scope, ambiguity, and autonomy does this involve? | `CareerLevel` — a universal, industry-agnostic ordinal scale |
| **Track** | What *kind* of seniority is this — leading people, going deeper technically, building a practice? | `CareerTrack` — a small, extensible set (not a binary IC/Manager split) |
| **Title** | What does this get *called* here? | `Role.title` — profession/company-specific, already exists |

A `Role` references exactly one `CareerLevel` and one `CareerTrack` (a
"level" and "track" are classifications of the role, the same
many-to-one relationship `Company.industry` already uses — not a graph
traversal, since a role has exactly one level, not a set of them).

## `CareerLevel` — The Universal Scale

```
CareerLevel (
    id UUID PRIMARY KEY,
    ordinal SMALLINT NOT NULL UNIQUE,   -- 1-10, defines the ordering
    name TEXT NOT NULL,                 -- e.g. "Advanced / Senior"
    scope_description TEXT NOT NULL,    -- what defines this band — autonomy, ambiguity, impact radius
    typical_years_note TEXT             -- explicitly advisory only, see caveat below
)
```

Ten bands, defined by **scope of impact and autonomy** — never by years
of experience or a specific title, both of which vary too much across
fields to be reliable:

| Ordinal | Name | Scope / Autonomy |
|---|---|---|
| 1 | Entry / Foundational | Learning fundamentals under close supervision; executes clearly-defined tasks |
| 2 | Developing | Some independence on routine work within an established process |
| 3 | Proficient | Works independently across the standard full scope of the role |
| 4 | Advanced / Senior | Handles ambiguous/complex problems; informally mentors others |
| 5 | Expert / Staff | Recognized domain authority; influence extends beyond own immediate team |
| 6 | Principal, *or* first-line People Leadership | Either the individual-contributor ceiling (sets technical/professional direction for a function) or manages a team directly — see Track, below |
| 7 | Senior Leadership | Manages managers or owns a functional area end-to-end |
| 8 | Executive | Owns multiple functions or a major business unit |
| 9 | Senior Executive | Organization-wide accountability for a domain (a "C-suite" band in corporate contexts) |
| 10 | Chief Executive | Ultimate accountability for the whole organization |

**Explicit caveat, stored as a design principle, not just prose here**:
`typical_years_note` is advisory display text only ("often 8-15 years,
varies enormously by field") — nothing in the system ever computes or
infers a `CareerLevel` from years of experience. Career pace differs
too much across fields (and individuals) for that to be reliable, and
doing so would silently penalize anyone whose path doesn't match a
typical timeline. Level is inferred from *actual scope of
responsibility* (role classification, evidence — see
`cikg-skill-evidence.md`), never from tenure.

## `CareerTrack` — More Than IC vs. Manager

A naive two-track split (Individual Contributor vs. Management) is
itself a tech-industry-shaped assumption that doesn't generalize:
skilled trades often diverge into business ownership rather than
corporate management; healthcare and law have clinical/practice tracks
where deep expertise never requires managing people; academia has its
own tenure track entirely. `CareerTrack` is reference data, not a fixed
enum, for the same reason `SkillCategory` domains aren't hardcoded —
new tracks are a content operation, not a schema change:

| Track (representative starting set) | Example |
|---|---|
| Individual Contributor | Staff Engineer, Senior Financial Analyst |
| People Management | Engineering Manager, Nurse Manager |
| Clinical / Practice | Attending Physician, Senior Partner (law) |
| Academic | Associate Professor, Department Chair |
| Entrepreneurial / Ownership | Master Electrician running own contracting business |
| Specialist / Distinguished | Principal Scientist, Distinguished Engineer |

A given `CareerLevel` ordinal can be reached via different tracks —
that's the point of separating them. Band 6 via People Management looks
like a first-line manager; Band 6 via Individual Contributor looks like
a Principal Engineer with no direct reports. Same scope of impact,
genuinely different day-to-day work.

## Worked Examples Across Industries

Deliberately including finance's inverted "VP" case, since it's the
clearest illustration of why title strings can't drive this:

| Field | Title | Level (ordinal) | Track |
|---|---|---|---|
| Technology | Software Engineer I | 2 | Individual Contributor |
| Technology | Staff Engineer | 5 | Individual Contributor |
| Technology | Engineering Manager | 6 | People Management |
| Technology | VP of Engineering | 8 | People Management |
| Investment Banking | Analyst | 2 | Individual Contributor |
| Investment Banking | Associate | 3 | Individual Contributor |
| Investment Banking | **Vice President** | **4** | Individual Contributor |
| Investment Banking | Managing Director | 7 | People Management |
| Nursing | New Graduate RN | 2 | Clinical / Practice |
| Nursing | Charge Nurse | 4 | Clinical / Practice |
| Nursing | Nurse Manager | 6 | People Management |
| Nursing | Chief Nursing Officer | 9 | People Management |
| Skilled Trades (Electrical) | Apprentice Electrician | 1 | Individual Contributor |
| Skilled Trades (Electrical) | Journeyman Electrician | 3 | Individual Contributor |
| Skilled Trades (Electrical) | Master Electrician, own business | 6 | Entrepreneurial / Ownership |
| Academia | Assistant Professor | 3 | Academic |
| Academia | Full Professor | 6 | Academic |
| Academia | Dean | 8 | Academic |
| Military (Officer) | Second Lieutenant (O-1) | 2 | People Management |
| Military (Officer) | Colonel (O-6) | 7 | People Management |
| Military (Enlisted) | Private (E-1) | 1 | Individual Contributor |
| Military (Enlisted) | Sergeant Major (E-9) | 5 | Specialist / Distinguished |

Investment Banking's Vice President landing at ordinal 4 (the same
scope-of-impact band as a technology company's "Senior" individual
contributor) while Technology's VP of Engineering lands at ordinal 8 is
exactly the case this framework exists to handle correctly — a
title-string comparison would have called these equivalent.

## How This Connects to the Rest of the Graph

- **`Role.career_level_id`, `Role.career_track_id`** — every `Role`
  node (`cikg-knowledge-graph-model.md`) gains these two FKs. `CareerPath.next_role`
  edges can now be validated/visualized against monotonically
  increasing (or intentionally lateral) `CareerLevel.ordinal` values,
  and paths can be compared across tracks — "what does the Individual
  Contributor path look like next to the People Management path from
  the same starting role."
- **`Competency.typical_emergence_level_id`** (nullable FK to
  `CareerLevel`) — some competencies genuinely correlate with seniority
  band regardless of profession (e.g. "Executive Presence," "Political
  Navigation," "Budget Ownership" typically emerge around Band 6+
  across nearly every field). This is advisory metadata for career
  planning and gap analysis, not a hard gate — someone below the
  typical band isn't blocked from claiming or working toward the
  competency.
- **Skill Evidence** (`cikg-skill-evidence.md`) — a person's evidence
  (roles held, scope described in `Experience` rows) is what a future
  "what level does my experience suggest" assessment would reason over;
  this framework defines the scale that assessment reports against, it
  doesn't itself compute anyone's level.

## Related Documents

- `docs/architecture/cikg-knowledge-graph-model.md` — `Role`, `CareerPath`, `Competency` base definitions
- `docs/architecture/cikg-skill-ontology.md`
- `docs/architecture/cikg-skill-evidence.md`
