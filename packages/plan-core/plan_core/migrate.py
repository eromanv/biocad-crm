"""Run Alembic migrations against an existing async engine."""

from __future__ import annotations

from pathlib import Path

from alembic.config import Config
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import AsyncEngine

from alembic import command

_PLAN_CORE_ROOT = Path(__file__).resolve().parent.parent


def alembic_config() -> Config:
    cfg = Config(str(_PLAN_CORE_ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(_PLAN_CORE_ROOT / "alembic"))
    return cfg


def run_upgrade_sync(connection: Connection) -> None:
    cfg = alembic_config()
    cfg.attributes["connection"] = connection
    command.upgrade(cfg, "head")


async def upgrade_head(engine: AsyncEngine) -> None:
    async with engine.connect() as conn:
        await conn.run_sync(run_upgrade_sync)
        await conn.commit()
