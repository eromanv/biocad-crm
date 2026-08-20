"""Pure plan-edit helpers used by the repository (no I/O)."""

from __future__ import annotations

from plan_core.models import Task


def normalize_task_name(name: str) -> str:
    return name.strip().casefold()


def find_duplicate_tasks(tasks: list[Task], name: str) -> list[Task]:
    key = normalize_task_name(name)
    if not key:
        return []
    return [t for t in tasks if normalize_task_name(t.name) == key]


def duplicate_name_error(name: str, matches: list[Task]) -> str:
    ids = ", ".join(str(t.id) for t in matches)
    label = name.strip() or name
    return (
        f"Задача с именем «{label}» уже есть (id: {ids}). "
        "Не создавайте дубликат без подтверждения пользователя. "
        "Спросите: изменить существующую задачу или создать ещё одну с тем же именем. "
        "Для явного дубликата вызовите add_task с allow_duplicate=true."
    )


def merge_predecessor_ids(existing: list[int], added: list[int]) -> list[int]:
    """Append new predecessor ids, preserving order and skipping duplicates."""
    out: list[int] = []
    seen: set[int] = set()
    for item in list(existing) + list(added):
        value = int(item)
        if value in seen:
            continue
        seen.add(value)
        out.append(value)
    return out
