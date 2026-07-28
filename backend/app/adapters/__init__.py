"""Infrastructure adapters.

Concrete implementations of the interfaces defined in app/domain and
app/core (repositories, identity providers, AI providers, cache, object
storage). This is the only layer allowed to import SQLAlchemy models,
provider SDKs, or other infrastructure-specific libraries directly.

Phase 0 status: empty scaffold except for the ai_providers/identity_providers
package markers, which are populated starting Phase 1 (identity) and
Phase 4 (AI platform).
"""
