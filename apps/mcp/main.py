"""Biocad plan MCP — FastMCP streamable-http on /mcp + /health."""

from __future__ import annotations

import json
import os
from contextlib import asynccontextmanager
from typing import Any

from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

from plan_core.cpm import ScheduleError
from plan_core.repo import PlanRepository, create_repository

DATABASE_URL = os.environ.get(
    "DATABASE_URL", "postgresql+asyncpg://biocad:biocad@localhost:5433/biocad"
)

mcp = FastMCP(
    "biocad-plan",
    host="0.0.0.0",
    port=int(os.environ.get("MCP_PORT", "8101")),
    stateless_http=True,
    transport_security=TransportSecuritySettings(
        enable_dns_rebinding_protection=False,
    ),
)

_repo: PlanRepository | None = None


def repo() -> PlanRepository:
    if _repo is None:
        raise RuntimeError("Repository not initialized")
    return _repo


def _dump(plan: Any) -> str:
    return json.dumps(plan.public_dict(), ensure_ascii=False)


@mcp.tool()
async def list_tasks() -> str:
    """List all tasks in the current plan with computed schedule."""
    return _dump(await repo().get_plan())


@mcp.tool()
async def get_task(task_id: int) -> str:
    """Get one task by id (with schedule fields)."""
    task = await repo().get_task(task_id)
    if task is None:
        return json.dumps({"error": f"Task {task_id} not found"})
    return json.dumps(task.public_dict(), ensure_ascii=False)


@mcp.tool()
async def add_task(
    name: str,
    description: str = "",
    assignee: str = "",
    duration_days: int = 1,
    predecessor_ids: list[int] | None = None,
    allow_duplicate: bool = False,
) -> str:
    """Add a task and recalculate the CPM schedule. Duplicate names need allow_duplicate."""
    try:
        plan = await repo().add_task(
            name=name,
            description=description,
            assignee=assignee,
            duration_days=duration_days,
            predecessor_ids=predecessor_ids or [],
            allow_duplicate=allow_duplicate,
        )
        return _dump(plan)
    except (ScheduleError, ValueError) as exc:
        return json.dumps({"error": str(exc)})


@mcp.tool()
async def update_task(
    task_id: int,
    name: str | None = None,
    description: str | None = None,
    assignee: str | None = None,
    duration_days: int | None = None,
) -> str:
    """Update task fields and recalculate the schedule."""
    try:
        plan = await repo().update_task(
            task_id,
            name=name,
            description=description,
            assignee=assignee,
            duration_days=duration_days,
        )
        return _dump(plan)
    except (ScheduleError, ValueError) as exc:
        return json.dumps({"error": str(exc)})


@mcp.tool()
async def add_predecessors(task_id: int, predecessor_ids: list[int]) -> str:
    """Add predecessors to a task without removing existing ones, then recalculate."""
    try:
        plan = await repo().add_predecessors(task_id, predecessor_ids)
        return _dump(plan)
    except (ScheduleError, ValueError) as exc:
        return json.dumps({"error": str(exc)})


@mcp.tool()
async def set_predecessors(task_id: int, predecessor_ids: list[int]) -> str:
    """Replace predecessor list for a task and recalculate."""
    try:
        plan = await repo().set_predecessors(task_id, predecessor_ids)
        return _dump(plan)
    except (ScheduleError, ValueError) as exc:
        return json.dumps({"error": str(exc)})


@mcp.tool()
async def shift_tasks(task_ids: list[int], days: int) -> str:
    """Delay task starts by N days (lag after predecessors) and recalculate."""
    try:
        plan = await repo().shift_tasks(task_ids, days)
        return _dump(plan)
    except (ScheduleError, ValueError) as exc:
        return json.dumps({"error": str(exc)})


@mcp.tool()
async def reassign_tasks(task_ids: list[int], assignee: str) -> str:
    """Set assignee for multiple tasks."""
    try:
        plan = await repo().reassign_tasks(task_ids, assignee)
        return _dump(plan)
    except (ScheduleError, ValueError) as exc:
        return json.dumps({"error": str(exc)})


@mcp.tool()
async def delete_task(task_id: int) -> str:
    """Delete a task (and drop it from others' predecessors), then recalculate."""
    try:
        plan = await repo().delete_task(task_id)
        return _dump(plan)
    except (ScheduleError, ValueError) as exc:
        return json.dumps({"error": str(exc)})


@mcp.tool()
async def recalc_schedule() -> str:
    """Recompute CPM dates from project_start and predecessors."""
    return _dump(await repo().recalc_schedule())


async def health(_: Request) -> JSONResponse:
    return JSONResponse({"status": "ok", "service": "mcp"})


def create_app():
    global _repo

    mcp_app = mcp.streamable_http_app()
    mcp_app.routes.insert(0, Route("/health", endpoint=health, methods=["GET"]))
    original_lifespan = mcp_app.router.lifespan_context

    @asynccontextmanager
    async def lifespan(app):
        global _repo
        _repo = await create_repository(DATABASE_URL)
        await _repo.ensure_seeded()
        async with original_lifespan(app):
            yield

    mcp_app.router.lifespan_context = lifespan
    return mcp_app


app = create_app()
