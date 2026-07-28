"""Domain layer: business rules, framework-free.

Nothing in this package or its submodules may import FastAPI, SQLAlchemy,
or any other framework/infrastructure library. Domain services operate on
plain Python objects (dataclasses) and repository *interfaces* only, so
they can be unit tested without a database or an HTTP server.

Phase 0 status: empty scaffold. Domain modules are added starting Phase 1.
"""
