from __future__ import annotations

from datetime import date

from plan_core.cpm import compute_schedule
from plan_core.models import Plan, Task

SEED_PROJECT_START = date(2026, 8, 17)


def build_seed_plan() -> Plan:
    """8–12 linked tasks for a feature delivery demo."""
    raw = [
        Task(
            id=1,
            name="Анализ требований",
            description="Собрать и уточнить ТЗ",
            assignee="Анна",
            duration_days=3,
            predecessor_ids=[],
        ),
        Task(
            id=2,
            name="Дизайн API",
            description="Контракт REST и MCP",
            assignee="Борис",
            duration_days=2,
            predecessor_ids=[1],
        ),
        Task(
            id=3,
            name="Схема БД",
            description="Таблицы плана и задач",
            assignee="Борис",
            duration_days=2,
            predecessor_ids=[1],
        ),
        Task(
            id=4,
            name="plan-core CPM",
            description="Модели и расписание",
            assignee="Виктор",
            duration_days=3,
            predecessor_ids=[2, 3],
        ),
        Task(
            id=5,
            name="Backend REST",
            description="FastAPI эндпоинты",
            assignee="Виктор",
            duration_days=4,
            predecessor_ids=[4],
        ),
        Task(
            id=6,
            name="MCP tools",
            description="Тулы редактирования плана",
            assignee="Дарья",
            duration_days=3,
            predecessor_ids=[4],
        ),
        Task(
            id=7,
            name="Чат OpenRouter",
            description="SSE + tool-calling",
            assignee="Дарья",
            duration_days=3,
            predecessor_ids=[5, 6],
        ),
        Task(
            id=8,
            name="Frontend диаграмма",
            description="Диаграмма и модалка",
            assignee="Елена",
            duration_days=5,
            predecessor_ids=[2],
        ),
        Task(
            id=9,
            name="Интеграция UI",
            description="Чат и Excel в интерфейсе",
            assignee="Елена",
            duration_days=3,
            predecessor_ids=[7, 8],
        ),
        Task(
            id=10,
            name="Тесты",
            description="CPM, Excel, API smoke",
            assignee="Анна",
            duration_days=2,
            predecessor_ids=[5, 6],
        ),
        Task(
            id=11,
            name="Документация",
            description="README и roadmap",
            assignee="Анна",
            duration_days=2,
            predecessor_ids=[9, 10],
        ),
    ]
    return compute_schedule(Plan(project_start=SEED_PROJECT_START, tasks=raw))
