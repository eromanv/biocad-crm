from __future__ import annotations

import asyncio
import os
from logging.config import fileConfig
from pathlib import Path

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context
from plan_core.db import metadata

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = metadata

_REPO_ROOT = Path(__file__).resolve().parents[2]


def _load_repo_env() -> None:
    """Load fullstack-app/.env without overriding already-set variables."""
    env_path = _REPO_ROOT / ".env"
    if not env_path.is_file():
        return
    for raw in env_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip("'").strip('"')
        os.environ.setdefault(key, value)


def _in_docker() -> bool:
    return Path("/.dockerenv").exists()


def get_url() -> str:
    """URL from the environment — never edit alembic.ini when creds change.

    Compose DATABASE_URL uses hostname `db`. From the host (uv run alembic)
    that name does not resolve, so it is rewritten to 127.0.0.1:POSTGRES_PORT.
    """
    _load_repo_env()
    url = os.environ.get("DATABASE_URL")
    if url:
        if not _in_docker():
            port = os.environ.get("POSTGRES_PORT", "5433")
            url = url.replace("@db:5432", f"@127.0.0.1:{port}")
        return url

    user = os.environ.get("POSTGRES_USER", "biocad")
    password = os.environ.get("POSTGRES_PASSWORD", "biocad")
    db_name = os.environ.get("POSTGRES_DB", "biocad")
    port = os.environ.get("POSTGRES_PORT", "5433")
    host = os.environ.get("POSTGRES_HOST", "127.0.0.1")
    return f"postgresql+asyncpg://{user}:{password}@{host}:{port}/{db_name}"


def run_migrations_offline() -> None:
    context.configure(
        url=get_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = get_url()
    connectable = async_engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    connection = config.attributes.get("connection")
    if connection is None:
        asyncio.run(run_async_migrations())
    else:
        do_run_migrations(connection)


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
