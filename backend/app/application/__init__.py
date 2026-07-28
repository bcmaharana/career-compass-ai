"""Application services layer.

Orchestrates use cases by calling domain services and repository
interfaces. Contains no framework imports (no FastAPI, no SQLAlchemy) and
no business rules of its own beyond sequencing calls and managing
transaction boundaries.

Phase 0 status: empty scaffold. Domain modules (identity, career_profile,
etc.) are added starting Phase 1.
"""
