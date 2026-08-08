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
    # A second, deliberately private bucket for resume uploads (Phase 5).
    # object_storage_bucket is made bucket-wide public-read by
    # S3ObjectStorageRepository._ensure_bucket_exists() — correct for
    # profile photos, wrong for resumes, which carry real PII. Resumes
    # get their own bucket rather than a mixed-ACL single bucket, since
    # S3/MinIO bucket policies apply to the whole bucket.
    object_storage_resumes_bucket: str = Field(default="career-compass-resumes-dev")

    # --- Auth ---
    jwt_secret_key: str = Field(default="change-me-in-every-environment")
    jwt_access_token_expire_minutes: int = Field(default=60)
    jwt_algorithm: str = Field(default="HS256")

    # --- AI Platform ---
    anthropic_api_key: str = Field(default="")
    # Groq's free tier is rate-limited, not metered/credit-based — no
    # billing concern from having this configured in dev.
    groq_api_key: str = Field(default="")
    # ai_default_model is documentation of intent only — the model
    # actually called is read from the ModelVersion row seeded by
    # scripts/seed_platform_defaults.py (app/adapters/db/repositories/
    # ai_platform.py's SqlAlchemyModelRegistry), per ADR-004: switching
    # models is a data change, not a code/config change.
    ai_default_model: str = Field(default="claude-sonnet-5")
    # Ollama runs on the host machine, not in Docker Compose — the
    # backend container reaches it via Docker Desktop's
    # host.docker.internal DNS name, the same "container needs a
    # different address than a browser/host process would use" pattern
    # as OBJECT_STORAGE_ENDPOINT vs OBJECT_STORAGE_PUBLIC_URL above.
    # Override to http://localhost:11434 if running the backend natively
    # instead of via Docker.
    ollama_base_url: str = Field(default="http://host.docker.internal:11434")

    # --- CIKG search (Phase 4.5.1 MVP 2A) ---
    # Ollama-only for now — no paid embedding provider is wired (see
    # cikg-mvp-roadmap.md's MVP 2A scope). cikg_embedding_dimensions must
    # match the actual output size of cikg_embedding_model (nomic-embed-text
    # is 768-dim); changing the model to one with a different dimensionality
    # requires a migration to resize the content_embeddings.embedding column,
    # not just this setting.
    cikg_embedding_model: str = Field(default="nomic-embed-text")
    cikg_embedding_dimensions: int = Field(default=768)

    # --- Phone login (Firebase Phone Auth) ---
    # Firebase does the actual SMS delivery/OTP verification; the backend
    # only ever verifies the resulting Firebase ID token (see
    # app/adapters/identity_providers/firebase_phone.py) — no OTP codes
    # or SMS provider credentials of our own to manage.
    firebase_project_id: str = Field(default="")
    # Path to a Firebase service-account JSON key (Project Settings >
    # Service Accounts > Generate new private key). Kept as a file, not
    # inline JSON in an env var, so it can be bind-mounted read-only into
    # the backend container (see infra/docker-compose.yml) rather than
    # needing multi-line JSON pasted into .env. Never commit the actual
    # key file — backend/secrets/ is gitignored.
    firebase_service_account_file: str = Field(default="")

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
