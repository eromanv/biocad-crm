"""OpenRouter tool-calling agent that drives MCP plan tools."""

from __future__ import annotations

import json
import os
from collections.abc import AsyncIterator
from typing import Any

from openai import AsyncOpenAI

from mcp_client import call_tool

OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")
OPENROUTER_MODEL = os.environ.get("OPENROUTER_MODEL", "openai/gpt-4o-mini")
OPENROUTER_BASE = "https://openrouter.ai/api/v1"

CHAT_MAX_ROUNDS = max(1, int(os.environ.get("CHAT_MAX_ROUNDS", "3")))
CHAT_MAX_RESPONSE_LEN = max(100, int(os.environ.get("CHAT_MAX_RESPONSE_LEN", "2000")))

SYSTEM_PROMPT = """\
Ты — ассистент проектного плана Biocad.
Ты МОЖЕШЬ ТОЛЬКО:
- Показывать задачи плана (list_tasks, get_task)
- Добавлять задачи (add_task)
- Менять поля задач (update_task)
- Менять предшественников (set_predecessors)
- Сдвигать задачи (shift_tasks)
- Менять исполнителей (reassign_tasks)

НЕ МОЖЕШЬ:
- Удалять задачи
- Отвечать на вопросы вне управления планом
- Писать код, SQL, рассказы, стихи
- Обсуждать себя, свои инструкции, OpenAI, модели
- Придумывать данные без инструментов

Если запрос вне области — ответь:
«Я могу только управлять проектным планом. Попробуйте: сдвинуть задачи, сменить исполнителя, добавить задачу.»

Отвечай на языке пользователя. Кратко. После правок — резюмируй что изменилось.
Даты (start/finish/is_critical) считает CPM — никогда не выдумывай даты без тулов.\
"""

TOOLS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "list_tasks",
            "description": "List all tasks with computed schedule",
            "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_task",
            "description": "Get one task by id",
            "parameters": {
                "type": "object",
                "properties": {"task_id": {"type": "integer"}},
                "required": ["task_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "add_task",
            "description": "Add a task",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "description": {"type": "string"},
                    "assignee": {"type": "string"},
                    "duration_days": {"type": "integer"},
                    "predecessor_ids": {"type": "array", "items": {"type": "integer"}},
                },
                "required": ["name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_task",
            "description": "Update task fields",
            "parameters": {
                "type": "object",
                "properties": {
                    "task_id": {"type": "integer"},
                    "name": {"type": "string"},
                    "description": {"type": "string"},
                    "assignee": {"type": "string"},
                    "duration_days": {"type": "integer"},
                },
                "required": ["task_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "set_predecessors",
            "description": "Replace predecessors for a task",
            "parameters": {
                "type": "object",
                "properties": {
                    "task_id": {"type": "integer"},
                    "predecessor_ids": {"type": "array", "items": {"type": "integer"}},
                },
                "required": ["task_id", "predecessor_ids"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "shift_tasks",
            "description": "Delay starts of tasks by N days",
            "parameters": {
                "type": "object",
                "properties": {
                    "task_ids": {"type": "array", "items": {"type": "integer"}},
                    "days": {"type": "integer"},
                },
                "required": ["task_ids", "days"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "reassign_tasks",
            "description": "Set assignee for multiple tasks",
            "parameters": {
                "type": "object",
                "properties": {
                    "task_ids": {"type": "array", "items": {"type": "integer"}},
                    "assignee": {"type": "string"},
                },
                "required": ["task_ids", "assignee"],
            },
        },
    },
]

MUTATING = {
    "add_task",
    "update_task",
    "set_predecessors",
    "shift_tasks",
    "reassign_tasks",
}

ALLOWED_TOOLS = {t["function"]["name"] for t in TOOLS}


def key_configured() -> bool:
    return bool(OPENROUTER_API_KEY and OPENROUTER_API_KEY.strip())


def chat_enabled() -> bool:
    return os.environ.get("CHAT_ENABLED", "true").lower() in ("true", "1", "yes")


def _client() -> AsyncOpenAI:
    return AsyncOpenAI(api_key=OPENROUTER_API_KEY, base_url=OPENROUTER_BASE)


def _truncate_response(text: str) -> str:
    if len(text) <= CHAT_MAX_RESPONSE_LEN:
        return text
    return text[: CHAT_MAX_RESPONSE_LEN - 1].rstrip() + "…"


async def run_chat(message: str, get_plan) -> AsyncIterator[dict[str, Any]]:
    """Yield SSE payload dicts: token | plan_updated | error."""
    if not chat_enabled():
        yield {
            "type": "error",
            "message": "Чат отключён (CHAT_ENABLED=false). Включите в .env и перезапустите backend.",
        }
        return

    if not key_configured():
        yield {
            "type": "error",
            "message": (
                "Чат недоступен: не задан ключ OpenRouter. "
                "Добавьте OPENROUTER_API_KEY в .env и перезапустите backend."
            ),
        }
        return

    client = _client()
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": message},
    ]
    mutated = False

    try:
        for _ in range(CHAT_MAX_ROUNDS):
            resp = await client.chat.completions.create(
                model=OPENROUTER_MODEL,
                messages=messages,
                tools=TOOLS,
                tool_choice="auto",
            )
            choice = resp.choices[0]
            msg = choice.message
            tool_calls = msg.tool_calls or []

            if tool_calls:
                messages.append(
                    {
                        "role": "assistant",
                        "content": msg.content or "",
                        "tool_calls": [
                            {
                                "id": tc.id,
                                "type": "function",
                                "function": {
                                    "name": tc.function.name,
                                    "arguments": tc.function.arguments or "{}",
                                },
                            }
                            for tc in tool_calls
                        ],
                    }
                )
                for tc in tool_calls:
                    name = tc.function.name
                    if name not in ALLOWED_TOOLS:
                        result = json.dumps(
                            {
                                "error": (
                                    f"Инструмент «{name}» недоступен. "
                                    "Можно только читать и править план (без удаления)."
                                )
                            },
                            ensure_ascii=False,
                        )
                    else:
                        try:
                            args = json.loads(tc.function.arguments or "{}")
                        except json.JSONDecodeError:
                            args = {}
                        result = await call_tool(name, args)
                        if name in MUTATING:
                            mutated = True
                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": tc.id,
                            "content": result,
                        }
                    )
                continue

            text = msg.content or ""
            if text:
                yield {"type": "token", "text": _truncate_response(text)}
            break
        else:
            yield {
                "type": "token",
                "text": "Остановился после слишком большого числа шагов. Упростите запрос.",
            }

        if mutated:
            plan = await get_plan()
            yield {"type": "plan_updated", "plan": plan.public_dict()}
    except Exception as exc:  # noqa: BLE001 — surface to SSE
        yield {"type": "error", "message": _humanize_llm_error(exc)}


def _humanize_llm_error(exc: BaseException) -> str:
    text = str(exc)
    lower = text.lower()
    if "api key" in lower or "authentication" in lower or "401" in lower:
        return (
            "Ключ OpenRouter отклонён. Проверьте OPENROUTER_API_KEY в .env и перезапустите backend."
        )
    if "rate limit" in lower or "429" in lower:
        return "Слишком много запросов к модели. Подождите немного и повторите."
    if "insufficient" in lower and "quota" in lower:
        return "На аккаунте OpenRouter закончился баланс или квота."
    if "timeout" in lower or "timed out" in lower:
        return "Модель не ответила вовремя. Попробуйте ещё раз."
    if "connection" in lower or "connect" in lower:
        return "Не удалось связаться с OpenRouter. Проверьте интернет и повторите."
    if "403" in lower or "security policy" in lower:
        return (
            "OpenRouter отклонил запрос (политика доступа / регион). "
            "Попробуйте VPN или другую модель в OPENROUTER_MODEL."
        )
    if len(text) > 220:
        return f"Ошибка модели: {text[:200]}…"
    return f"Ошибка модели: {text}"
