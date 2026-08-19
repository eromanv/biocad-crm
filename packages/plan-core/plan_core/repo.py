from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import delete, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from plan_core.cpm import ScheduleError, compute_schedule
from plan_core.db import (
    init_db,
    make_engine,
    make_session_factory,
    plan_meta,
    task_predecessors,
    tasks,
)
from plan_core.models import Plan, Task
from plan_core.seed import build_seed_plan


class PlanRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]):
        self._sf = session_factory

    async def ensure_seeded(self) -> Plan:
        async with self._sf() as session:
            count = await session.scalar(select(tasks.c.id).limit(1))
            if count is None:
                await self._replace_plan(session, build_seed_plan())
                await session.commit()
        return await self.get_plan()

    async def get_plan(self) -> Plan:
        async with self._sf() as session:
            start = await session.scalar(
                select(plan_meta.c.project_start).where(plan_meta.c.id == 1)
            )
            if start is None:
                return await self.ensure_seeded()

            task_rows = (
                (await session.execute(select(tasks).order_by(tasks.c.sort_order, tasks.c.id)))
                .mappings()
                .all()
            )
            pred_rows = (await session.execute(select(task_predecessors))).all()
            preds: dict[int, list[int]] = {}
            for tid, pid in pred_rows:
                preds.setdefault(tid, []).append(pid)

            raw_tasks = [
                Task(
                    id=r["id"],
                    name=r["name"],
                    description=r["description"] or "",
                    assignee=r["assignee"] or "",
                    duration_days=r["duration_days"],
                    lag_days=r["lag_days"] or 0,
                    predecessor_ids=sorted(preds.get(r["id"], [])),
                )
                for r in task_rows
            ]
            return compute_schedule(Plan(project_start=start, tasks=raw_tasks))

    async def get_task(self, task_id: int) -> Task | None:
        plan = await self.get_plan()
        for t in plan.tasks:
            if t.id == task_id:
                return t
        return None

    async def replace_plan(self, plan: Plan) -> Plan:
        scheduled = compute_schedule(plan)
        async with self._sf() as session:
            await self._replace_plan(session, scheduled)
            await session.commit()
        return await self.get_plan()

    async def reset_to_seed(self) -> Plan:
        return await self.replace_plan(build_seed_plan())

    async def add_task(
        self,
        *,
        name: str,
        description: str = "",
        assignee: str = "",
        duration_days: int = 1,
        predecessor_ids: list[int] | None = None,
    ) -> Plan:
        plan = await self.get_plan()
        new_id = max((t.id for t in plan.tasks), default=0) + 1
        tasks_list = list(plan.tasks) + [
            Task(
                id=new_id,
                name=name,
                description=description,
                assignee=assignee,
                duration_days=duration_days,
                predecessor_ids=list(predecessor_ids or []),
            )
        ]
        return await self.replace_plan(Plan(project_start=plan.project_start, tasks=tasks_list))

    async def update_task(
        self,
        task_id: int,
        *,
        name: str | None = None,
        description: str | None = None,
        assignee: str | None = None,
        duration_days: int | None = None,
    ) -> Plan:
        plan = await self.get_plan()
        found = False
        updated: list[Task] = []
        for t in plan.tasks:
            if t.id != task_id:
                updated.append(t)
                continue
            found = True
            updated.append(
                t.model_copy(
                    update={
                        k: v
                        for k, v in {
                            "name": name,
                            "description": description,
                            "assignee": assignee,
                            "duration_days": duration_days,
                        }.items()
                        if v is not None
                    }
                )
            )
        if not found:
            raise ScheduleError(f"Task {task_id} not found")
        return await self.replace_plan(Plan(project_start=plan.project_start, tasks=updated))

    async def set_predecessors(self, task_id: int, predecessor_ids: list[int]) -> Plan:
        plan = await self.get_plan()
        ids = {t.id for t in plan.tasks}
        if task_id not in ids:
            raise ScheduleError(f"Task {task_id} not found")
        for p in predecessor_ids:
            if p not in ids:
                raise ScheduleError(f"Unknown predecessor id {p}")
        updated = [
            t.model_copy(update={"predecessor_ids": list(predecessor_ids)})
            if t.id == task_id
            else t
            for t in plan.tasks
        ]
        return await self.replace_plan(Plan(project_start=plan.project_start, tasks=updated))

    async def reschedule_task(
        self,
        task_id: int,
        *,
        new_start: date,
        duration_days: int,
    ) -> Plan:
        """Move/resize a task: set lag from earliest CPM start and update duration."""
        if duration_days < 1:
            raise ScheduleError("duration must be >= 1")
        plan = await self.get_plan()
        target = next((t for t in plan.tasks if t.id == task_id), None)
        if target is None:
            raise ScheduleError(f"Task {task_id} not found")

        by_id = {t.id: t for t in plan.tasks}
        if target.predecessor_ids:
            pred_finish = max(by_id[p].finish for p in target.predecessor_ids if by_id[p].finish)
            base = pred_finish + timedelta(days=1)
        else:
            base = plan.project_start

        lag_days = max(0, (new_start - base).days)
        updated = [
            t.model_copy(update={"lag_days": lag_days, "duration_days": duration_days})
            if t.id == task_id
            else t
            for t in plan.tasks
        ]
        return await self.replace_plan(Plan(project_start=plan.project_start, tasks=updated))

    async def shift_tasks(self, task_ids: list[int], days: int) -> Plan:
        """Delay task starts by increasing lag_days (CPM offset after predecessors)."""
        if days == 0:
            return await self.get_plan()
        plan = await self.get_plan()
        id_set = set(task_ids)
        updated = [
            t.model_copy(update={"lag_days": max(0, t.lag_days + days)}) if t.id in id_set else t
            for t in plan.tasks
        ]
        missing = id_set - {t.id for t in plan.tasks}
        if missing:
            raise ScheduleError(f"Unknown task ids: {sorted(missing)}")
        return await self.replace_plan(Plan(project_start=plan.project_start, tasks=updated))

    async def reassign_tasks(self, task_ids: list[int], assignee: str) -> Plan:
        plan = await self.get_plan()
        id_set = set(task_ids)
        missing = id_set - {t.id for t in plan.tasks}
        if missing:
            raise ScheduleError(f"Unknown task ids: {sorted(missing)}")
        updated = [
            t.model_copy(update={"assignee": assignee}) if t.id in id_set else t for t in plan.tasks
        ]
        return await self.replace_plan(Plan(project_start=plan.project_start, tasks=updated))

    async def delete_task(self, task_id: int) -> Plan:
        plan = await self.get_plan()
        if task_id not in {t.id for t in plan.tasks}:
            raise ScheduleError(f"Task {task_id} not found")
        updated = []
        for t in plan.tasks:
            if t.id == task_id:
                continue
            preds = [p for p in t.predecessor_ids if p != task_id]
            updated.append(t.model_copy(update={"predecessor_ids": preds}))
        return await self.replace_plan(Plan(project_start=plan.project_start, tasks=updated))

    async def recalc_schedule(self) -> Plan:
        return await self.get_plan()

    async def set_project_start(self, project_start: date) -> Plan:
        plan = await self.get_plan()
        return await self.replace_plan(Plan(project_start=project_start, tasks=plan.tasks))

    async def _replace_plan(self, session: AsyncSession, plan: Plan) -> None:
        # Validate graph before write
        compute_schedule(plan)
        await session.execute(delete(task_predecessors))
        await session.execute(delete(tasks))
        await session.execute(delete(plan_meta))
        await session.execute(plan_meta.insert().values(id=1, project_start=plan.project_start))
        for order, t in enumerate(plan.tasks):
            await session.execute(
                tasks.insert().values(
                    id=t.id,
                    name=t.name,
                    description=t.description,
                    assignee=t.assignee,
                    duration_days=t.duration_days,
                    lag_days=t.lag_days,
                    sort_order=order,
                )
            )
        for t in plan.tasks:
            for p in t.predecessor_ids:
                await session.execute(
                    task_predecessors.insert().values(task_id=t.id, predecessor_id=p)
                )
        if plan.tasks:
            await session.execute(
                text(
                    "SELECT setval(pg_get_serial_sequence('tasks', 'id'), "
                    "(SELECT COALESCE(MAX(id), 1) FROM tasks))"
                )
            )


async def create_repository(database_url: str) -> PlanRepository:
    engine = make_engine(database_url)
    await init_db(engine)
    return PlanRepository(make_session_factory(engine))
