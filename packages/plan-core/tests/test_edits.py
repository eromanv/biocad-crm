from datetime import date

import pytest

from plan_core.cpm import ScheduleError, compute_schedule
from plan_core.edits import (
    duplicate_name_error,
    find_duplicate_tasks,
    merge_predecessor_ids,
    normalize_task_name,
)
from plan_core.models import Plan, Task
from plan_core.seed import build_seed_plan


def test_normalize_task_name_strips_and_casefolds():
    assert normalize_task_name("  Тесты  ") == normalize_task_name("тесты")


def test_find_duplicate_tasks_matches_seed_tests():
    plan = build_seed_plan()
    matches = find_duplicate_tasks(plan.tasks, "тесты")
    assert [t.id for t in matches] == [10]
    assert find_duplicate_tasks(plan.tasks, "Нет такой") == []


def test_duplicate_name_error_lists_ids():
    matches = [Task(id=10, name="Тесты", duration_days=2)]
    text = duplicate_name_error("тесты", matches)
    assert "10" in text
    assert "allow_duplicate=true" in text


def test_merge_predecessor_ids_appends_without_dropping_existing():
    assert merge_predecessor_ids([5, 6], [3]) == [5, 6, 3]
    assert merge_predecessor_ids([5, 6], [5, 3]) == [5, 6, 3]


def test_add_predecessor_unknown_id_detected_by_cpm():
    plan = Plan(
        project_start=date(2026, 1, 1),
        tasks=[
            Task(id=1, name="A", duration_days=1, predecessor_ids=[]),
            Task(
                id=2,
                name="B",
                duration_days=1,
                predecessor_ids=merge_predecessor_ids([], [99]),
            ),
        ],
    )
    with pytest.raises(ScheduleError, match="Unknown predecessor"):
        compute_schedule(plan)


def test_add_predecessor_cycle_detected_by_cpm():
    plan = Plan(
        project_start=date(2026, 1, 1),
        tasks=[
            Task(id=1, name="A", duration_days=1, predecessor_ids=[2]),
            Task(id=2, name="B", duration_days=1, predecessor_ids=[1]),
        ],
    )
    with pytest.raises(ScheduleError, match="Cycle"):
        compute_schedule(plan)
