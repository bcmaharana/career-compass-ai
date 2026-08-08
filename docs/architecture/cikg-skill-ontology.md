# CIKG — Skill Ontology and Hierarchy Model

Second-pass document. Builds on `cikg-knowledge-graph-model.md`'s
`Skill` node and its `related_to`/`prerequisite_of`/`member_of` edges —
this document formalizes the categorization structure those edges sit
underneath and makes the profession-agnostic requirement concrete with
worked examples outside technology.

## A Note on Examples

The foundational pass (`ADR-006`, `cikg-ddd.md`) leaned on "Enterprise
Agile Coach" as a recurring example, inherited from the source spec's
own text. Nothing in the schema special-cases Agile/Scrum/SAFe — it's
ordinary content under Technology & Engineering, no different in kind
from a nursing specialization or a GAAP requirement. This document, and
the rest of this second pass, deliberately draws examples from across
industries so the model doesn't read as tech- or Agile-centric. Where a
domain needs a running example, it rotates: healthcare, finance,
skilled trades, sales, and technology in turn.

## Two Distinct Relationship Systems

CIKG's skill layer has two structurally different kinds of
relationship, and conflating them is the most common way skill
taxonomies go wrong:

| | **Hierarchy** (categorization) | **Ontology** (semantic relationship) |
|---|---|---|
| Question it answers | "What kind of thing is this?" | "How does this relate to that?" |
| Shape | A DAG of categories a skill *belongs to* | Typed edges directly between skills |
| Example | "Suturing" is under Healthcare → Clinical Procedures → Surgical Skills | "Suturing" is a `prerequisite_of` "Minor Surgical Procedures" |
| Multiplicity | A skill can belong to multiple categories | A skill can have many ontology edges to many other skills |
| Who maintains it | Content curators, rarely changes | Curators + AI-suggested, changes more often as the graph grows |

Both are needed and neither substitutes for the other: hierarchy is how
someone *browses* ("show me skills under Financial Analysis"); ontology
is how someone *reasons* ("what should I learn before this, what's
related, what's a specialization of what").

## Hierarchy: `SkillCategory`

```
SkillCategory (
    id UUID PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    created_at, updated_at, deleted_at  -- standard audit fields
)

category_parent (   -- edge table, per the pattern in cikg-knowledge-graph-model.md
    id UUID PRIMARY KEY,
    child_category_id UUID NOT NULL REFERENCES skill_category(id),
    parent_category_id UUID NOT NULL REFERENCES skill_category(id)
)

skill_category_membership (   -- edge table
    id UUID PRIMARY KEY,
    skill_id UUID NOT NULL REFERENCES skill(id),
    category_id UUID NOT NULL REFERENCES skill_category(id)
)
```

**Deliberately a DAG, not a tree, and not a fixed number of levels.**
Two real constraints drove this:

1. **A skill legitimately belongs to more than one category.** "SQL"
   belongs under both Technology → Programming Languages *and*
   Technology → Data Analysis Tools. A tree forces an arbitrary primary
   category and loses the second; `skill_category_membership` being
   many-to-many avoids that.
2. **Taxonomy depth genuinely varies by field**, and hardcoding a fixed
   depth (Domain → Category → Subcategory → Skill, always exactly four
   levels) would force shallow fields into artificial extra layers and
   deep fields (clinical specialties, legal practice areas) to
   compress. `category_parent` being a self-referencing edge table with
   no depth limit lets each domain's curators use as many or few levels
   as make sense — governance (see `cikg-content-governance.md`)
   recommends 2–4 levels as a practical convention, not a schema rule.

### Worked Examples Across Domains

```
Healthcare
  └─ Clinical Practice
       └─ Surgical Skills
            ├─ Suturing
            └─ Laparoscopic Technique
  └─ Clinical Practice
       └─ Patient Care
            └─ Patient Assessment

Finance & Accounting
  └─ Financial Reporting
       ├─ GAAP Compliance
       └─ Financial Statement Analysis
  └─ Risk & Compliance
       ├─ AML (Anti-Money Laundering)
       └─ KYC (Know Your Customer)

Skilled Trades
  └─ Electrical
       ├─ Residential Wiring
       └─ Industrial Controls
  └─ Electrical
       └─ NEC Code Compliance   -- same top-level domain, different branch

Sales
  └─ Revenue Skills
       ├─ Consultative Selling
       └─ Enterprise Negotiation

Technology & Engineering
  └─ Delivery Practices
       ├─ PI Planning              -- Agile/SAFe content, ordinary row here
       └─ Flow Metrics
  └─ Programming Languages
       └─ Python
```

Top-level `SkillCategory` domains are themselves just rows — a
representative starting set (not exhaustive, not schema-enforced):
Technology & Engineering, Healthcare & Clinical, Finance & Accounting,
Sales & Marketing, Legal & Compliance, Skilled Trades & Manufacturing,
Creative & Design, Education, Human Resources, Executive Leadership &
General Management, Public Sector & Military, Non-Profit & Social
Impact. Adding "Aerospace" or "Hospitality" later is a content
operation (`INSERT`), not a migration — consistent with `cikg-overview.md`'s
extensibility principle.

## Ontology: Skill-to-Skill Relationships

Formalizes and extends `cikg-knowledge-graph-model.md`'s edge set with
one addition:

| Edge | Meaning | Example |
|---|---|---|
| `related_to` (symmetric, carries `strength`) | Conceptually connected, neither implies the other | "Financial Modeling" related_to "Valuation" |
| `prerequisite_of` (directed) | Reasonable to learn A before B | "Double-Entry Bookkeeping" prerequisite_of "Financial Statement Analysis" |
| `specializes` (directed, **new in this pass**) | A is a narrower, more specific form of B — distinct from `prerequisite_of` (learning order) and from hierarchy (category membership) | "ICU Nursing" specializes "Registered Nursing"; "Laparoscopic Technique" specializes "Surgical Skills" |
| `synonym_of` (symmetric, **new in this pass**) | Two names for functionally the same skill — a stronger claim than `skill_alias` (ADR-006 §3), which links a *free-text string* to a canonical skill; `synonym_of` links two *canonical* skills that should probably be merged or are interchangeable in practice | "ML" synonym_of "Machine Learning"; "PM" synonym_of "Project Management" (context-dependent — see below) |

`specializes` vs. hierarchy membership: "ICU Nursing" is a
*specialization* of "Registered Nursing" (ontology — a skill relative
to another skill), and separately sits in the Healthcare → Clinical
Practice → Nursing *category* (hierarchy — where you'd browse to find
it). They answer different questions and both are populated
independently.

`synonym_of` needs governance judgment, not automatic merging —
"PM" is ambiguous across domains (Project Management vs. Product
Management vs., in some contexts, Prime Minister in a
political-science taxonomy), so `synonym_of` edges are curated, never
auto-created from string similarity alone (that's what `skill_alias`
suggestions are for, reviewed before promotion — see
`cikg-content-governance.md`).

## Normalization and Aliasing

Distinct from `synonym_of` above, `skill_alias` (introduced in
`cikg-knowledge-graph-model.md`) handles the *free-text-to-canonical*
direction:

```
skill_alias (
    id UUID PRIMARY KEY,
    skill_id UUID NOT NULL REFERENCES skill(id),
    alias_text TEXT NOT NULL,   -- e.g. "pm", "product mgmt", "prod management"
    normalized_text TEXT NOT NULL,  -- lowercased, whitespace/punctuation-collapsed form used for matching
    source TEXT NOT NULL,       -- 'curated' | 'ai_suggested' | 'user_confirmed'
    confidence NUMERIC
)
```

Normalization rule for `normalized_text`: lowercase, collapse internal
whitespace, strip punctuation except internal hyphens (so "Node.js"
normalizes distinctly from "Node js" resolving to the same alias, but
"co-founder" doesn't collapse to "cofounder" incorrectly). This is
intentionally simple (no stemming/lemmatization) — aggressive
normalization risks false-positive matches across genuinely different
skills more than it helps; ambiguous cases are exactly what
`ai_suggested` + human confirmation (governance) is for, not something
the normalization function should try to resolve unilaterally.

## Skill Attributes (Restated, Grounded)

From the source spec's requested `Skill` metadata, mapped to where each
now lives:

| Requested attribute | Where it lives |
|---|---|
| id, name, description | `Skill` node itself |
| category, subcategory | `skill_category_membership` edges (plural, not two fixed columns — see multi-category note above) |
| aliases | `skill_alias` table |
| ATS keywords | `Skill.ats_keywords` (scalar array attribute — genuinely belongs to the skill itself, not a relationship) |
| proficiency levels | `Skill.proficiency_level_definitions` (structured scalar attribute — text describing what "intermediate" vs. "advanced" means for *this* skill; not a separate graph entity, since proficiency-level text is specific to one skill and doesn't relate to other nodes) |
| related skills | `related_to` edges |
| prerequisite skills | `prerequisite_of` edges |
| associated technologies | `supports` edges (reverse, from `Technology`) |
| associated certifications | `validates` edges (reverse, from `Certification`) |
| industries | `emphasizes` edges (reverse, from `Industry`) |
| roles | `requires` edges (reverse, from `Role`) |
| behavioral indicators, measurable outcomes | `Skill` scalar attributes (text/structured, skill-specific — see `cikg-skill-evidence.md` for how these connect to a person's actual demonstrated evidence) |
| resume examples, interview examples, STAR examples | Not stored on `Skill` itself — these are generated (AI Agent Architecture) or curated content belonging to `InterviewQuestion`/future `ResumeBullet` templates that *reference* the skill via `evaluates`/`demonstrates`, not owned by it, to avoid duplicating the same example text across every skill that happens to share a scenario |
| learning resources | `teaches` edges (reverse, from `LearningResource`) |
| AI prompts | Not stored per-skill — AI generation uses the versioned `PromptVersion` registry (existing AI Platform) with the skill's structured attributes as template input variables, the same pattern `career_coach_chat` already uses for conversation context |

## Related Documents

- `docs/architecture/cikg-knowledge-graph-model.md` — base node/edge model this extends
- `docs/architecture/cikg-content-governance.md` — how new categories/skills/edges get approved
- `docs/architecture/cikg-skill-evidence.md` — how a person's real experience substantiates a skill claim
- `docs/architecture/cikg-career-levels.md` — how skills/competencies map onto seniority, independent of category
