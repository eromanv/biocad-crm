from datetime import date

import pytest

from plan_core.cpm import ScheduleError
from plan_core.excel import export_plan_to_bytes, import_plan_from_bytes
from plan_core.seed import build_seed_plan


def test_excel_round_trip():
    original = build_seed_plan()
    raw = export_plan_to_bytes(original)
    imported = import_plan_from_bytes(raw, project_start=original.project_start)
    assert imported.project_start == original.project_start
    assert len(imported.tasks) == len(original.tasks)
    for a, b in zip(original.tasks, imported.tasks, strict=True):
        assert a.name == b.name
        assert a.description == b.description
        assert a.assignee == b.assignee
        assert a.duration_days == b.duration_days
        assert a.predecessor_ids == b.predecessor_ids
        assert a.start == b.start
        assert a.finish == b.finish
        assert a.is_critical == b.is_critical


def test_import_bad_predecessor_name():
    from io import BytesIO

    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.append(["задача", "описание", "исполнитель", "длительность", "предшественники"])
    ws.append(["A", "", "X", 1, ""])
    ws.append(["B", "", "Y", 1, "Missing"])
    buf = BytesIO()
    wb.save(buf)
    with pytest.raises(ScheduleError, match="unknown predecessor"):
        import_plan_from_bytes(buf.getvalue(), project_start=date(2026, 1, 1))


def test_import_cycle_in_excel():
    from io import BytesIO

    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.append(["задача", "описание", "исполнитель", "длительность", "предшественники"])
    ws.append(["A", "", "", 1, "B"])
    ws.append(["B", "", "", 1, "A"])
    buf = BytesIO()
    wb.save(buf)
    with pytest.raises(ScheduleError, match="Cycle"):
        import_plan_from_bytes(buf.getvalue(), project_start=date(2026, 1, 1))
