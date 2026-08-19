from datetime import date, timedelta

import pytest

from plan_core.cpm import ScheduleError, compute_schedule
from plan_core.models import Plan, Task


def test_simple_chain_dates():
    plan = Plan(
        project_start=date(2026, 1, 1),
        tasks=[
            Task(id=1, name="A", duration_days=2, predecessor_ids=[]),
            Task(id=2, name="B", duration_days=3, predecessor_ids=[1]),
        ],
    )
    out = compute_schedule(plan)
    a, b = out.tasks
    assert a.start == date(2026, 1, 1)
    assert a.finish == date(2026, 1, 2)
    assert b.start == date(2026, 1, 3)
    assert b.finish == date(2026, 1, 5)
    assert a.is_critical and b.is_critical


def test_parallel_and_critical_path():
    plan = Plan(
        project_start=date(2026, 1, 1),
        tasks=[
            Task(id=1, name="A", duration_days=5, predecessor_ids=[]),
            Task(id=2, name="B", duration_days=2, predecessor_ids=[]),
            Task(id=3, name="C", duration_days=1, predecessor_ids=[1, 2]),
        ],
    )
    out = compute_schedule(plan)
    by = {t.id: t for t in out.tasks}
    assert by[1].is_critical
    assert not by[2].is_critical
    assert by[3].is_critical
    assert by[3].start == by[1].finish + timedelta(days=1)


def test_cycle_detected():
    plan = Plan(
        project_start=date(2026, 1, 1),
        tasks=[
            Task(id=1, name="A", duration_days=1, predecessor_ids=[2]),
            Task(id=2, name="B", duration_days=1, predecessor_ids=[1]),
        ],
    )
    with pytest.raises(ScheduleError, match="Cycle"):
        compute_schedule(plan)


def test_unknown_predecessor():
    plan = Plan(
        project_start=date(2026, 1, 1),
        tasks=[Task(id=1, name="A", duration_days=1, predecessor_ids=[99])],
    )
    with pytest.raises(ScheduleError, match="Unknown predecessor"):
        compute_schedule(plan)


def test_lag_delays_start():
    plan = Plan(
        project_start=date(2026, 1, 1),
        tasks=[
            Task(id=1, name="A", duration_days=1, predecessor_ids=[]),
            Task(id=2, name="B", duration_days=1, predecessor_ids=[1], lag_days=2),
        ],
    )
    out = compute_schedule(plan)
    # A: start/finish Jan 1; B base = Jan 2; + lag 2 → Jan 4
    assert out.tasks[1].start == date(2026, 1, 4)
