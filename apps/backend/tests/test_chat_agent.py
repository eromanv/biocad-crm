import json
from datetime import date

from chat_agent import (
    apply_successful_tool,
    build_llm_messages,
    compact_plan,
    resolve_focus_task_id,
    tool_result_has_error,
)
from chat_session import ChatSession
from plan_core.models import Plan, Task
from plan_core.seed import build_seed_plan


def _plan_with_extra_tests() -> Plan:
    plan = build_seed_plan()
    extra = Task(
        id=12,
        name="Тесты",
        description="Новая задача",
        assignee="",
        duration_days=1,
        predecessor_ids=[],
        start=date(2026, 8, 17),
        finish=date(2026, 8, 17),
    )
    return Plan(project_start=plan.project_start, tasks=[*plan.tasks, extra])


def test_compact_plan_omits_descriptions_and_dates():
    snapshot = compact_plan(build_seed_plan())
    sample = snapshot["tasks"][0]
    assert set(sample) == {"id", "name", "assignee", "duration_days", "predecessor_ids"}


def test_tool_error_does_not_mutate_or_steal_focus():
    session = ChatSession(last_task_id=10)
    result = json.dumps({"error": "Задача с именем «Тесты» уже есть (id: 10)."}, ensure_ascii=False)
    mutated = apply_successful_tool(
        "add_task",
        {"name": "Тесты"},
        result,
        prior_ids={10},
        session=session,
    )
    assert mutated is False
    assert session.last_task_id == 10
    assert tool_result_has_error(result)


def test_add_task_focus_uses_created_id():
    session = ChatSession(last_task_id=10)
    plan = _plan_with_extra_tests()
    mutated = apply_successful_tool(
        "add_task",
        {"name": "Тесты", "allow_duplicate": True},
        json.dumps(plan.public_dict(), ensure_ascii=False),
        prior_ids={t.id for t in build_seed_plan().tasks},
        session=session,
    )
    assert mutated is True
    assert session.last_task_id == 12


def test_pronoun_turn_keeps_new_task_as_focus():
    session = ChatSession(last_task_id=12)
    session.append("user", "добавь задачу тесты")
    session.append("assistant", "Уже есть «Тесты» (id 10). Создать ещё одну?")
    session.append("user", "да, создай дубликат")
    session.append("assistant", "Добавлена задача «Тесты» (id 12).")
    session.append(
        "user",
        "сделай её исполнителем Елену и пусть она зависит от задачи Схема БД",
    )
    messages = build_llm_messages(
        _plan_with_extra_tests(),
        session,
        "сделай её исполнителем Елену и пусть она зависит от задачи Схема БД",
    )
    grounding = messages[1]["content"]
    assert "last_task_id: 12" in grounding
    assert "Схема БД" in grounding
    history_text = " ".join(m["content"] for m in messages[2:-1])
    assert "id 12" in history_text
    assert messages[-1]["content"].startswith("сделай её исполнителем")


def test_resolve_add_predecessors_focus_is_dependent_task():
    result = json.dumps({"project_start": "2026-08-17", "tasks": []})
    assert (
        resolve_focus_task_id(
            "add_predecessors",
            {"task_id": 12, "predecessor_ids": [3]},
            result,
            prior_ids={12, 3},
        )
        == 12
    )
