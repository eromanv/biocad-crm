"""Biocad FastAPI backend — REST, Excel, SSE chat via OpenRouter → MCP."""

from __future__ import annotations

import json
import os
import time
from contextlib import asynccontextmanager
from datetime import date

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel, Field, field_validator

from chat_agent import chat_enabled, key_configured, run_chat
from plan_core.cpm import ScheduleError
from plan_core.excel import export_plan_to_bytes, import_plan_from_bytes
from plan_core.repo import PlanRepository, create_repository

DATABASE_URL = os.environ.get(
    "DATABASE_URL", "postgresql+asyncpg://biocad:biocad@localhost:5433/biocad"
)

CHAT_MAX_INPUT_LEN = max(1, int(os.environ.get("CHAT_MAX_INPUT_LEN", "500")))
CHAT_RATE_LIMIT = max(1, int(os.environ.get("CHAT_RATE_LIMIT", "10")))
CHAT_RATE_WINDOW = 60  # seconds

_repo: PlanRepository | None = None
_chat_timestamps: dict[str, list[float]] = {}


def repo() -> PlanRepository:
    if _repo is None:
        raise HTTPException(
            status_code=503,
            detail="База данных ещё не готова. Подождите немного и обновите страницу.",
        )
    return _repo


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return "unknown"


def _check_rate_limit(ip: str) -> None:
    now = time.time()
    window = _chat_timestamps.setdefault(ip, [])
    window[:] = [t for t in window if now - t < CHAT_RATE_WINDOW]
    if len(window) >= CHAT_RATE_LIMIT:
        raise HTTPException(
            status_code=429,
            detail="Слишком много сообщений. Подождите минуту.",
        )
    window.append(now)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    global _repo
    _repo = await create_repository(DATABASE_URL)
    await _repo.ensure_seeded()
    yield


app = FastAPI(title="Biocad Backend", version="0.1.0", lifespan=lifespan)
_cors_origins = [
    origin.strip()
    for origin in os.getenv("CORS_ORIGINS", "http://localhost:5174").split(",")
    if origin.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    message: str = Field(min_length=1)

    @field_validator("message")
    @classmethod
    def _trim_and_limit(cls, v: str) -> str:
        text = v.strip()
        if not text:
            raise ValueError("Сообщение не может быть пустым.")
        if len(text) > CHAT_MAX_INPUT_LEN:
            raise ValueError(f"Сообщение слишком длинное (макс. {CHAT_MAX_INPUT_LEN} символов).")
        return text


class RescheduleRequest(BaseModel):
    start: date
    duration_days: int = Field(ge=1)


@app.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "service": "backend",
        "openrouter_configured": key_configured(),
        "chat_enabled": chat_enabled(),
    }


@app.get("/api/plan")
async def get_plan() -> dict:
    plan = await repo().get_plan()
    return plan.public_dict()


@app.post("/api/plan/import")
async def import_plan(
    file: UploadFile = File(...),
    project_start: date | None = None,
) -> dict:
    data = await file.read()
    if not data:
        raise HTTPException(
            status_code=400,
            detail="Файл пустой. Выберите Excel со списком задач.",
        )
    try:
        current = await repo().get_plan()
        start = project_start or current.project_start
        plan = import_plan_from_bytes(data, project_start=start)
        saved = await repo().replace_plan(plan)
        return saved.public_dict()
    except ScheduleError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/plan/export")
async def export_plan() -> Response:
    plan = await repo().get_plan()
    raw = export_plan_to_bytes(plan)
    return Response(
        content=raw,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="plan.xlsx"'},
    )


@app.post("/api/plan/reset")
async def reset_plan() -> dict:
    plan = await repo().reset_to_seed()
    return plan.public_dict()


@app.get("/api/tasks/{task_id}")
async def get_task(task_id: int) -> dict:
    task = await repo().get_task(task_id)
    if task is None:
        raise HTTPException(
            status_code=404,
            detail=f"Задача №{task_id} не найдена.",
        )
    return task.public_dict()


@app.post("/api/tasks/{task_id}/reschedule")
async def reschedule_task(task_id: int, body: RescheduleRequest) -> dict:
    """Move/resize a task on the Gantt (updates lag + duration, CPM recalc)."""
    try:
        plan = await repo().reschedule_task(
            task_id,
            new_start=body.start,
            duration_days=body.duration_days,
        )
        return plan.public_dict()
    except ScheduleError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/chat")
async def chat(body: ChatRequest, request: Request) -> StreamingResponse:
    if not chat_enabled():
        raise HTTPException(
            status_code=503,
            detail=("Чат отключён (CHAT_ENABLED=false). Включите в .env и перезапустите backend."),
        )
    if not key_configured():
        raise HTTPException(
            status_code=503,
            detail=(
                "Чат недоступен: не задан ключ OpenRouter. "
                "Добавьте OPENROUTER_API_KEY в .env и перезапустите backend."
            ),
        )

    _check_rate_limit(_client_ip(request))

    async def event_stream():
        async for payload in run_chat(body.message, repo().get_plan):
            yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
        yield 'data: {"type": "done"}\n\n'

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
