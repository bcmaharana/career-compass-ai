# ADR-001: Modular Monolith Over Microservices for Initial Implementation

## Status
Accepted

## Context
Career Compass AI has clearly separable domains (Identity, Career Profile, Resume Intelligence, Skill Intelligence, Opportunity Intelligence, Learning Intelligence, AI Coach, AI Platform, Analytics). A microservices architecture would let each evolve and scale independently, but introduces distributed-systems complexity (network calls between services, distributed transactions, service discovery, cross-service deployment coordination) before there is a validated product or a team large enough to own separate services.

## Decision
Build a **modular monolith**: one deployable backend application, internally structured with the same strict layering (API → Application → Domain → Repository → Infrastructure) and module boundaries that a microservices architecture would use. Modules communicate through application-service interfaces, never by reaching into each other's tables directly.

## Consequences
**Positive:**
- Lower operational overhead — one process to deploy, monitor, and debug.
- Faster development velocity — no network calls or serialization overhead between modules during this stage.
- Transactions across modules (e.g., creating a user and their career profile) can use a single database transaction.
- The module boundaries are real code boundaries (separate packages, explicit interfaces), so extracting a module into its own service later is a deployment and wiring change, not a redesign.

**Negative / accepted trade-offs:**
- All modules currently scale together (can't independently scale, say, Resume Intelligence's parsing load without scaling everything).
- Requires discipline to avoid modules quietly coupling to each other's internals — enforced via code review and the layering rules in `backend-architecture.md`, not by a network boundary.

## Revisit Trigger
Reconsider extracting a module into its own service when: (a) that module has meaningfully different scaling characteristics from the rest of the system, (b) a separate team takes ownership of it, or (c) it needs a different technology stack (e.g., a dedicated ML-serving runtime for AI Platform).
