"""Application configuration.

All configuration is loaded from environment variables (via a local .env file
in development, real environment variables in deployed environments) and
validated at startup. A missing or malformed required setting fails fast at
process start, rather than surfacing as a runtime error mid-request.

Do not read os.environ directly anywhere else in the codebase — always go
through `get_settings()` so there is a single, typed source of truth.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Typed application settings, loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- Application ---
    app_name: str = Field(default="career-compass-ai")
    app_env: str = Field(default="local")
    debug: bool = Field(default=False)
    log_level: str = Field(default="INFO")

    # --- Database ---
    database_url: str = Field(
        default="postgresql+psycopg://compass:compass@localhost:5432/career_compass"
    )
    database_pool_size: int = Field(default=5)

    # --- Redis ---
    redis_url: str = Field(default="redis://localhost:6379/0")

    # --- Object storage ---
    # object_storage_endpoint: where the *backend* reaches the object
    # store to upload/delete files (boto3's endpoint_url). Inside Docker
    # this must be the service name (e.g. http://minio:9000) — "localhost"
    # from inside a container means the container itself, not its
    # neighbors, the same issue as DATABASE_URL.
    object_storage_endpoint: str = Field(default="http://localhost:9000")
    # object_storage_public_url: the address embedded in returned
    # photo_url values, which the *browser* loads directly — this must
    # be an address reachable from outside Docker's network (e.g.
    # http://localhost:9000, assuming MinIO's port is published to the
    # host), never the internal service name, since the browser doesn't
    # participate in Docker's internal DNS at all. Defaults to the same
    # value as object_storage_endpoint for non-Docker local dev, where
    # both really are the same address.
    object_storage_public_url: str = Field(default="http://localhost:9000")
    object_storage_access_key: str = Field(default="")
    object_storage_secret_key: str = Field(default="")
    object_storage_bucket: str = Field(default="career-compass-dev")

    # --- Auth ---
    jwt_secret_key: str = Field(default="change-me-in-every-environment")
    jwt_access_token_expire_minutes: int = Field(default=60)
    jwt_algorithm: str = Field(default="HS256")

    # --- AI Platform ---
    anthropic_api_key: str = Field(default="")
    ai_default_model: str = Field(default="claude-sonnet-4-6")

    # --- Chat (UI enhancement brief Part 1.2) ---
    # Retention policy is an explicit open decision, not yet made — None
    # means "keep indefinitely" for now. Nothing reads this yet; it
    # exists so a future retention job has one place to source its
    # cutoff from, rather than a hardcoded value baked into that job.
    chat_retention_days: int | None = Field(default=None)

    # --- Quote of the day (UI enhancement brief Part 1.3) ---
    # An external API for now, with a known future plan to swap in a
    # custom/owned quote source (see app/adapters/quotes/) — configurable
    # rather than hardcoded in the adapter so even the *current* provider
    # can be repointed (e.g. a self-hosted mirror) without a code change.
    quote_provider_base_url: str = Field(default="https://zenquotes.io")

    @property
    def is_local(self) -> bool:
        return self.app_env == "local"

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"


@lru_cache
def get_settings() -> Settings:
    """Return the process-wide Settings singleton.

    Cached so environment variables are read once per process, and so
    FastAPI's Depends(get_settings) reuses the same validated instance
    everywhere it's injected.
    """
    return Settings()
