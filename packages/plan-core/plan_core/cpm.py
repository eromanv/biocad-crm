from __future__ import annotations

from datetime import date, timedelta

from plan_core.models import Plan, Task


class ScheduleError(ValueError):
    """Invalid dependency graph or unknown predecessor references."""


def _topo_order(tasks: dict[int, Task]) -> list[int]:
    ids = set(tasks)
    for t in tasks.values():
        for p in t.predecessor_ids:
            if p not in ids:
                raise ScheduleError(f"Unknown predecessor id {p} for task {t.id}")
            if p == t.id:
                raise ScheduleError(f"Task {t.id} cannot be its own predecessor")

    indeg = {i: 0 for i in ids}
    succ: dict[int, list[int]] = {i: [] for i in ids}
    for t in tasks.values():
        for p in t.predecessor_ids:
            succ[p].append(t.id)
            indeg[t.id] += 1

    queue = sorted(i for i, d in indeg.items() if d == 0)
    order: list[int] = []
    while queue:
        n = queue.pop(0)
        order.append(n)
        for s in sorted(succ[n]):
            indeg[s] -= 1
            if indeg[s] == 0:
                queue.append(s)
                queue.sort()

    if len(order) != len(ids):
        raise ScheduleError("Cycle detected in predecessor graph")
    return order


def compute_schedule(plan: Plan) -> Plan:
    """Forward/backward CPM. Finish is inclusive (1-day task: start == finish)."""
    if not plan.tasks:
        return plan.model_copy(deep=True)

    by_id = {t.id: t.model_copy(deep=True) for t in plan.tasks}
    order = _topo_order(by_id)

    es: dict[int, date] = {}
    ef: dict[int, date] = {}

    for tid in order:
        t = by_id[tid]
        if t.predecessor_ids:
            pred_finish = max(ef[p] for p in t.predecessor_ids)
            # Next day after last predecessor finishes
            base = pred_finish + timedelta(days=1)
        else:
            base = plan.project_start
        start = base + timedelta(days=t.lag_days)
        finish = start + timedelta(days=t.duration_days - 1)
        es[tid] = start
        ef[tid] = finish

    project_end = max(ef.values())
    ls: dict[int, date] = {}
    lf: dict[int, date] = {}

    for tid in reversed(order):
        t = by_id[tid]
        successors = [s for s in by_id.values() if tid in s.predecessor_ids]
        if not successors:
            late_finish = project_end
        else:
            # Must finish day before earliest successor start (accounting for their lag)
            cand: list[date] = []
            for s in successors:
                # s.start = max(pred finishes)+1 + lag; reverse: lf(pred) = ls(s) - 1
                cand.append(ls[s.id] - timedelta(days=1))
            late_finish = min(cand)
        late_start = late_finish - timedelta(days=t.duration_days - 1)
        lf[tid] = late_finish
        ls[tid] = late_start

    scheduled: list[Task] = []
    for t in plan.tasks:
        tid = t.id
        nt = by_id[tid]
        nt.start = es[tid]
        nt.finish = ef[tid]
        nt.is_critical = es[tid] == ls[tid]
        scheduled.append(nt)

    return Plan(project_start=plan.project_start, tasks=scheduled)
