from __future__ import annotations

from datetime import date

from sqlalchemy import (
    CheckConstraint,
    Column,
    Date,
    ForeignKey,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    select,
)
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

metadata = MetaData()

plan_meta = Table(
    "plan_meta",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("project_start", Date, nullable=False),
    CheckConstraint("id = 1", name="single_plan"),
)

tasks = Table(
    "tasks",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("name", String(512), nullable=False),
    Column("description", Text, nullable=False, server_default=""),
    Column("assignee", String(256), nullable=False, server_default=""),
    Column("duration_days", Integer, nullable=False),
    Column("lag_days", Integer, nullable=False, server_default="0"),
    Column("sort_order", Integer, nullable=False, server_default="0"),
)

task_predecessors = Table(
    "task_predecessors",
    metadata,
    Column("task_id", Integer, ForeignKey("tasks.id", ondelete="CASCADE"), primary_key=True),
    Column(
        "predecessor_id",
        Integer,
        ForeignKey("tasks.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)


def make_engine(database_url: str) -> AsyncEngine:
    return create_async_engine(database_url, pool_pre_ping=True)


def make_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False)


async def init_db(engine: AsyncEngine) -> None:
    from plan_core.migrate import upgrade_head

    await upgrade_head(engine)


async def get_project_start(session: AsyncSession) -> date | None:
    row = await session.execute(select(plan_meta.c.project_start).where(plan_meta.c.id == 1))
    return row.scalar_one_or_none()
