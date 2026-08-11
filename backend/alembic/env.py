"""Alembic environment configuration.

The database URL always comes from app.core.config.get_settings(), never
hard-coded here or in alembic.ini, so migrations run against whatever
environment's DATABASE_URL is set — local, CI, staging, or production.

Uses migrations_database_url (the `compass` superuser role), not
database_url (the restricted `compass_app` role the running app
connects as) — migrations need DDL rights (CREATE TABLE, ALTER TABLE,
CREATE POLICY) compass_app deliberately doesn't have. Falls back to
database_url only if migrations_database_url isn't set, which just
means migrations fail loudly with a Postgres permission error instead
of silently running unprivileged — never a silent bypass either way.
"""

from __future__ import annotations

from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

from alembic import context
from app.adapters.db import models  # noqa: F401 -- registers all ORM models on Base.metadata
from app.adapters.db.base import Base
from app.core.config import get_settings

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

_settings = get_settings()
config.set_main_option(
    "sqlalchemy.url", _settings.migrations_database_url or _settings.database_url
)


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
