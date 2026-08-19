from __future__ import annotations

from datetime import date
from typing import Any

from pydantic import BaseModel, Field, field_validator


class Task(BaseModel):
    id: int
    name: str
    description: str = ""
    assignee: str = ""
    duration_days: int = Field(ge=1)
    predecessor_ids: list[int] = Field(default_factory=list)
    # Internal: delays ES after predecessors (used by shift_tasks). Not in Excel.
    lag_days: int = Field(default=0, ge=0)
    start: date | None = None
    finish: date | None = None
    is_critical: bool = False

    @field_validator("predecessor_ids", mode="before")
    @classmethod
    def _dedupe_preds(cls, v: Any) -> list[int]:
        if not v:
            return []
        seen: set[int] = set()
        out: list[int] = []
        for item in v:
            i = int(item)
            if i not in seen:
                seen.add(i)
                out.append(i)
        return out

    def public_dict(self) -> dict[str, Any]:
        """API contract fields (omit internal lag_days)."""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "assignee": self.assignee,
            "duration_days": self.duration_days,
            "predecessor_ids": list(self.predecessor_ids),
            "start": self.start.isoformat() if self.start else None,
            "finish": self.finish.isoformat() if self.finish else None,
            "is_critical": self.is_critical,
        }


class Plan(BaseModel):
    project_start: date
    tasks: list[Task] = Field(default_factory=list)

    def public_dict(self) -> dict[str, Any]:
        return {
            "project_start": self.project_start.isoformat(),
            "tasks": [t.public_dict() for t in self.tasks],
        }
