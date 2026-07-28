# Career Compass AI — Phase 0 Design Package

Incorporates all approved refinements: modular monolith, identity abstraction layer, tiered multi-tenancy, staged AI platform rollout, Tailwind/shadcn frontend, soft deletion, data lineage, versioning, and analytics foundation.

---

## 1. Final Repository Structure

```
career-compass-ai/
├── backend/
│   ├── app/
│   │   ├── api/                          # thin routers only
│   │   │   ├── v1/
│   │   │   │   ├── identity/
│   │   │   │   ├── career_profile/
│   │   │   │   ├── resume_intelligence/
│   │   │   │   ├── skill_intelligence/
│   │   │   │   ├── opportunity_intelligence/
│   │   │   │   ├── learning_intelligence/
│   │   │   │   ├── ai_coach/
│   │   │   │   └── analytics/
│   │   │   └── middleware/
│   │   │       ├── tenant_context.py
│   │   │       ├── auth.py
│   │   │       ├── audit.py
│   │   │       └── error_handling.py
│   │   ├── application/                  # use-case orchestration
│   │   │   ├── identity/
│   │   │   ├── career_profile/
│   │   │   ├── resume_intelligence/
│   │   │   ├── skill_intelligence/
│   │   │   ├── opportunity_intelligence/
│   │   │   ├── learning_intelligence/
│   │   │   ├── ai_coach/
│   │   │   └── analytics/
│   │   ├── domain/                       # pure logic, zero framework imports
│   │   │   ├── identity/
│   │   │   ├── career_profile/
│   │   │   ├── skill/
│   │   │   ├── opportunity/
│   │   │   └── learning/
│   │   ├── adapters/
│   │   │   ├── db/                       # SQLAlchemy repositories
│   │   │   ├── storage/                  # S3/MinIO
│   │   │   ├── cache/                    # Redis
│   │   │   ├── identity_providers/       # <-- NEW: internal + external IdP adapters
│   │   │   │   ├── internal_jwt.py
│   │   │   │   ├── oidc_base.py
│   │   │   │   ├── auth0.py              # stub, implemented when needed
│   │   │   │   ├── okta.py               # stub
│   │   │   │   └── azure_entra.py        # stub
│   │   │   └── ai_providers/
│   │   │       └── anthropic_provider.py
│   │   ├── ai_platform/
│   │   │   ├── llm_service/              # Phase 1: abstraction only
│   │   │   ├── prompts/
│   │   │   ├── models/
│   │   │   ├── embeddings/               # Phase 2: RAG
│   │   │   ├── retrieval/                # Phase 2: RAG
│   │   │   ├── agents/                   # Phase 3: orchestration (empty scaffold now)
│   │   │   ├── evaluations/
│   │   │   └── governance/
│   │   ├── core/
│   │   │   ├── config.py
│   │   │   ├── security.py               # password hashing, token utils
│   │   │   ├── identity_provider_interface.py   # <-- the abstraction contract
│   │   │   ├── logging.py
│   │   │   └── exceptions.py
│   │   └── main.py
│   ├── alembic/
│   ├── tests/
│   │   ├── unit/
│   │   ├── integration/
│   │   └── e2e/
│   ├── pyproject.toml
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── components/                   # shadcn/ui-based primitives
│   │   ├── features/                     # mirrors backend domains
│   │   ├── routes/
│   │   ├── stores/
│   │   ├── api/                          # OpenAPI-generated client + TanStack Query hooks
│   │   └── styles/
│   │       └── tailwind.config.ts
│   ├── package.json
│   └── Dockerfile
├── infra/
│   ├── docker-compose.yml
│   ├── docker-compose.override.yml       # local dev overrides
│   ├── github-actions/
│   └── k8s/                              # deferred, placeholder only
└── docs/
    ├── architecture/
    ├── adr/
    └── runbooks/
```

Everything ships as **one deployable backend service** (modular monolith). Module folders under `api/`, `application/`, `domain/`, and `adapters/` are the seams along which a future service extraction would cut — no code changes to boundaries required later, just a deployment split.

---

## 2. Database ERD

Includes soft deletion (`deleted_at`), AI lineage fields, and versioning fields as requested.

```mermaid
erDiagram
    TENANT ||--o{ ORGANIZATION : has
    TENANT ||--o{ USER : has
    ORGANIZATION ||--o{ ORGANIZATION : "parent of"
    ORGANIZATION ||--o{ USER : employs
    USER ||--o{ USER_ROLE : assigned
    ROLE ||--o{ USER_ROLE : granted
    ROLE ||--o{ ROLE_PERMISSION : has
    PERMISSION ||--o{ ROLE_PERMISSION : granted_via

    USER ||--|| CAREER_PROFILE : owns
    CAREER_PROFILE ||--o{ CAREER_PROFILE_VERSION : "versioned as"
    CAREER_PROFILE ||--o{ EXPERIENCE : includes
    CAREER_PROFILE ||--o{ EDUCATION : includes
    CAREER_PROFILE ||--o{ CERTIFICATION : includes
    CAREER_PROFILE ||--o{ CAREER_GOAL : sets

    USER ||--o{ USER_SKILL : has
    SKILL ||--o{ USER_SKILL : referenced_by

    USER ||--o{ RESUME : uploads
    RESUME ||--o{ RESUME_VERSION : "versioned as"

    USER ||--o{ RECOMMENDATION : receives
    RECOMMENDATION }o--|| PROMPT_VERSION : "generated using"
    RECOMMENDATION }o--|| MODEL_VERSION : "generated using"

    USER ||--o{ AI_CONVERSATION : participates_in
    AI_CONVERSATION }o--|| PROMPT_VERSION : uses
    AI_CONVERSATION }o--|| MODEL_VERSION : uses

    TENANT ||--o{ AUDIT_EVENT : logs
    TENANT ||--o{ SUBSCRIPTION : has
    TENANT ||--o{ FEATURE_FLAG : configures
    TENANT ||--o{ ANALYTICS_EVENT : emits

    TENANT {
        uuid id PK
        string name
        string subdomain
        string plan_tier
        string status
        timestamp created_at
        timestamp updated_at
    }

    USER {
        uuid id PK
        uuid tenant_id FK
        uuid org_id FK
        string email
        string hashed_password
        string status
        bool mfa_enabled
        timestamp created_at
        timestamp updated_at
        timestamp deleted_at
    }

    CAREER_PROFILE {
        uuid id PK
        uuid tenant_id FK
        uuid user_id FK
        int current_version
        string headline
        text summary
        int career_readiness_score
        timestamp created_at
        timestamp updated_at
        timestamp deleted_at
    }

    CAREER_PROFILE_VERSION {
        uuid id PK
        uuid career_profile_id FK
        int version_number
        jsonb snapshot
        string change_reason
        timestamp created_at
    }

    RESUME {
        uuid id PK
        uuid tenant_id FK
        uuid user_id FK
        int current_version
        string storage_key
        string parsed_status
        timestamp parsed_at
        timestamp created_at
        timestamp deleted_at
    }

    RESUME_VERSION {
        uuid id PK
        uuid resume_id FK
        int version_number
        string storage_key
        timestamp created_at
    }

    USER_SKILL {
        uuid id PK
        uuid tenant_id FK
        uuid user_id FK
        uuid skill_id FK
        string proficiency_level
        string evidence_source
        timestamp last_assessed_at
        timestamp deleted_at
    }

    RECOMMENDATION {
        uuid id PK
        uuid tenant_id FK
        uuid user_id FK
        string type
        jsonb payload
        string status
        string generated_by
        uuid source_data_ref
        uuid prompt_version_id FK
        uuid model_version_id FK
        float confidence_score
        text reasoning_metadata
        timestamp generated_at
        timestamp deleted_at
    }

    AI_CONVERSATION {
        uuid id PK
        uuid tenant_id FK
        uuid user_id FK
        uuid prompt_version_id FK
        uuid model_version_id FK
        jsonb messages
        int token_usage
        float feedback_score
        timestamp created_at
    }

    PROMPT_VERSION {
        uuid id PK
        string name
        int version
        text template
        string owner
        string approved_by
        timestamp approved_at
        string status
    }

    MODEL_VERSION {
        uuid id PK
        string provider
        string model_name
        string version
        string status
        float cost_per_1k_tokens
    }

    AUDIT_EVENT {
        uuid id PK
        uuid tenant_id FK
        uuid user_id FK
        string action
        string resource_type
        uuid resource_id
        timestamp occurred_at
        jsonb metadata
        string ip_address
    }

    ANALYTICS_EVENT {
        uuid id PK
        uuid tenant_id FK
        uuid user_id FK
        string event_name
        jsonb properties
        timestamp occurred_at
    }

    FEATURE_FLAG {
        uuid id PK
        uuid tenant_id "nullable = global default"
        string key
        bool enabled
        jsonb config
    }
```

**Soft deletion:** applied to every tenant-owned, user-facing entity (`User`, `CareerProfile`, `Resume`, `UserSkill`, `Recommendation`, etc.). Repositories filter `deleted_at IS NULL` by default; a separate admin-only query path can retrieve soft-deleted records for compliance/audit purposes. Reference/catalog tables (`Skill`, `PromptVersion`, `ModelVersion`) are not soft-deleted — they're versioned/deprecated instead.

**Versioning:** `CareerProfile` and `Resume` keep a `current_version` pointer on the parent row plus an append-only `*_VERSION` snapshot table, so history is queryable without complicating the "current state" read path. `Recommendation` doesn't need its own version table — each recommendation is already an immutable point-in-time record by design.

**AI lineage:** every `Recommendation` carries `source_data_ref` (what data triggered it), `prompt_version_id` + `model_version_id` (what generated it), `confidence_score`, and `reasoning_metadata` — enough to answer "why did the system suggest this" after the fact.

---

## 3. Domain Interaction Diagram

```mermaid
flowchart LR
    subgraph Coach["AI Career Coach (orchestrator)"]
    end

    subgraph Profile["Career Profile"]
    end
    subgraph Resume["Resume Intelligence"]
    end
    subgraph Skill["Skill Intelligence"]
    end
    subgraph Opportunity["Opportunity Intelligence"]
    end
    subgraph Learning["Learning Intelligence"]
    end
    subgraph AIP["AI Platform"]
    end
    subgraph Analytics["Analytics"]
    end

    Resume -->|extracted skills| Skill
    Profile -->|profile context| Skill
    Skill -->|current skill profile| Opportunity
    Skill -->|skill gaps| Learning
    Opportunity -->|target role requirements| Learning

    Coach -->|reads| Profile
    Coach -->|reads| Skill
    Coach -->|reads| Opportunity
    Coach -->|reads| Learning
    Coach -->|invokes| AIP

    Resume -.->|uses| AIP
    Skill -.->|uses, e.g. gap analysis| AIP
    Opportunity -.->|uses, e.g. matching| AIP
    Learning -.->|uses, e.g. path generation| AIP

    Profile -.emits.-> Analytics
    Skill -.emits.-> Analytics
    Opportunity -.emits.-> Analytics
    Learning -.emits.-> Analytics
    Coach -.emits.-> Analytics
```

Solid arrows = synchronous read dependency (via application service calls, never direct table access). Dotted arrows = "uses as a capability" (AI Platform) or "emits an event to" (Analytics), which is fire-and-forget / async where possible.

---

## 4. Request Lifecycle Diagram

```mermaid
sequenceDiagram
    participant Client
    participant Gateway as API Gateway
    participant MW as Middleware (auth, tenant, audit)
    participant Router as FastAPI Router
    participant AppSvc as Application Service
    participant Domain as Domain Service
    participant Repo as Repository
    participant DB as PostgreSQL (RLS)

    Client->>Gateway: HTTPS request + JWT
    Gateway->>MW: forward (rate-limited, routed)
    MW->>MW: validate JWT, extract tenant_id + user_id
    MW->>DB: SET LOCAL app.tenant_id = ...
    MW->>Router: request with populated context
    Router->>Router: validate payload (Pydantic)
    Router->>AppSvc: call use case
    AppSvc->>Domain: apply business rules
    Domain->>Repo: request/persist data (via port interface)
    Repo->>DB: parameterized query (RLS-enforced)
    DB-->>Repo: rows
    Repo-->>Domain: domain objects
    Domain-->>AppSvc: result
    AppSvc-->>Router: response DTO
    Router-->>MW: response
    MW->>DB: write AuditEvent (async)
    MW-->>Client: HTTP response
```

---

## 5. Authentication Flow

Shows internal JWT auth today, with the abstraction point where an external OIDC provider plugs in later without touching callers.

```mermaid
sequenceDiagram
    participant Client
    participant API as Auth Router
    participant IdPI as IdentityProviderInterface
    participant Internal as InternalJWTProvider
    participant External as External OIDC Provider (future)
    participant DB as User/Session Store

    Client->>API: POST /login (email, password)
    API->>IdPI: authenticate(credentials)
    IdPI->>Internal: authenticate(credentials)
    Internal->>DB: verify hashed password (Argon2id)
    DB-->>Internal: user record
    Internal-->>IdPI: identity claims
    IdPI-->>API: identity claims
    API->>DB: issue access token (15 min) + refresh token (Redis)
    API-->>Client: access + refresh tokens

    Note over Client,External: Future SSO path — same interface, different implementation
    Client->>API: GET /login/oidc/{provider}
    API->>IdPI: authenticate_via_oidc(provider, code)
    IdPI->>External: exchange code for tokens
    External-->>IdPI: OIDC claims
    IdPI-->>API: identity claims (same shape as internal path)
    API->>DB: issue access token + refresh token
    API-->>Client: access + refresh tokens
```

`IdentityProviderInterface` is the only thing `Application Services` and `API` routers depend on. `InternalJWTProvider` is the sole implementation in Phase 1; `Auth0`/`Okta`/`AzureEntra` adapters implement the same interface later, selected per-tenant via `TenantConfig`.

---

## 6. Tenant Isolation Flow

```mermaid
sequenceDiagram
    participant Client
    participant MW as Tenant Middleware
    participant Session as DB Session
    participant RLS as Postgres RLS Policy
    participant Table as tenant-owned table

    Client->>MW: request with JWT (contains tenant_id claim)
    MW->>MW: extract & validate tenant_id
    MW->>Session: open DB session
    MW->>Session: SET LOCAL app.tenant_id = '<tenant_id>'
    Session->>RLS: every query on tenant-owned tables
    RLS->>Table: WHERE tenant_id = current_setting('app.tenant_id')
    Table-->>RLS: only matching rows
    RLS-->>Session: filtered result set
    Session-->>MW: rows scoped to caller's tenant
    Note over RLS,Table: Even a repository bug that omits a tenant_id filter<br/>cannot leak cross-tenant rows — DB enforces it.
```

Enforced at two layers deliberately: application code always filters by `tenant_id` (defense in depth), and RLS policies make it structurally impossible to bypass even under a bug.

**Tier roadmap (unchanged from proposal, confirmed):**
- Tier 1 (default): shared DB + shared schema + RLS.
- Tier 2 (large enterprise tenant): same schema, dedicated database — a connection-string swap per tenant, no application code change since repositories already scope by `tenant_id`.
- Tier 3 (regulated customer): dedicated infrastructure — same container image, isolated deployment.

---

## 7. AI Request Lifecycle

Reflects the staged rollout: Phase 1 is LLM abstraction only, no agents yet.

```mermaid
sequenceDiagram
    participant AppSvc as Application Service
    participant LLM as LLM Service (ai_platform.llm_service)
    participant Prompt as Prompt Registry
    participant Model as Model Registry
    participant Provider as Provider Adapter (Anthropic)
    participant Gov as Governance/Observability
    participant DB as AIConversation / Recommendation table

    AppSvc->>LLM: request(use_case, input_data)
    LLM->>Prompt: get_active_version(use_case)
    Prompt-->>LLM: PromptVersion (approved only)
    LLM->>Model: get_active_model(tenant_config)
    Model-->>LLM: ModelVersion
    LLM->>Provider: invoke(prompt, model, input_data)
    Provider-->>LLM: raw response + token usage
    LLM->>Gov: log_invocation(prompt_version, model_version, tokens, latency)
    Gov->>DB: write AIConversation / lineage fields
    LLM-->>AppSvc: structured result + confidence metadata
    AppSvc->>AppSvc: apply human-review gate if tenant requires it
    AppSvc-->>DB: persist Recommendation (status=pending_review or approved)
```

Phase 2 (RAG) inserts an embeddings/retrieval step between `Prompt` and `Provider`. Phase 3 (agents) wraps this same lifecycle in a multi-step orchestration loop — the lifecycle itself doesn't change, agents just call it repeatedly with intermediate reasoning steps.

---

## 8. Local Development Setup Approach

```
infra/docker-compose.yml services:
  - postgres        (pgvector-enabled image, exposes 5432)
  - redis           (exposes 6379)
  - minio           (S3-compatible, local object storage, exposes 9000/9001)
  - backend         (FastAPI, hot-reload via uvicorn --reload, mounts ./backend)
  - frontend        (Vite dev server, hot-reload, mounts ./frontend)
```

**Setup steps:**
1. `cp .env.example .env` — fill in local secrets (never committed).
2. `docker compose -f infra/docker-compose.yml up -d postgres redis minio`
3. `cd backend && alembic upgrade head` — applies migrations, including RLS policy creation.
4. `docker compose -f infra/docker-compose.yml up backend frontend` (or run both natively with `uvicorn app.main:app --reload` / `npm run dev` for faster iteration).
5. Seed script (`backend/scripts/seed_dev_data.py`) creates a demo tenant, org, admin user, and reference `Skill` catalog so the frontend isn't empty on first run.
6. Backend docs available at `/docs` (FastAPI's auto-generated OpenAPI UI) — this is also the source for the frontend's generated API client.

No Kubernetes, no cloud dependency required for local dev — everything above runs on a laptop via Docker Compose, consistent with keeping Phase 0 operationally simple.

---

## Roadmap (confirmed, per your adjustment)

Phase 0 → Foundation · Phase 1 → Platform Foundation (tenant, identity abstraction, RBAC, audit, feature flags) · Phase 2 → Career Profile · Phase 3 → Skill Intelligence · Phase 4 → AI Platform Foundation · Phase 5 → Resume Intelligence · Phase 6 → Opportunity Intelligence · Phase 7 → Learning Intelligence · Phase 8 → AI Career Coach · Phase 9 → Analytics, Billing, Enterprise Features.

---

Ready to begin Phase 0 implementation on your confirmation.
