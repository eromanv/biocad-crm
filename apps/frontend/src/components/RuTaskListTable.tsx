import type { Task as GanttLibTask } from "gantt-task-react";
import { formatDate } from "../lib/gantt";

type Props = {
  rowHeight: number;
  rowWidth: string;
  fontFamily: string;
  fontSize: string;
  locale: string;
  tasks: GanttLibTask[];
  selectedTaskId?: string;
  setSelectedTask?: (taskId: string) => void;
  onExpanderClick: (task: GanttLibTask) => void;
};

/** Inclusive finish from gantt-task-react exclusive end. */
function inclusiveEnd(endExclusive: Date): Date {
  const d = new Date(endExclusive);
  d.setDate(d.getDate() - 1);
  return d;
}

/**
 * Task list that formats dates from the tasks the parent passes in.
 * Avoids stale left-table dates when gantt-task-react keeps outdated barTasks.
 */
export function createRuTaskListTable(getTasks: () => GanttLibTask[]) {
  return function RuTaskListTable({
    rowHeight,
    rowWidth,
    fontFamily,
    fontSize,
    tasks: rows,
    onExpanderClick,
  }: Props) {
    const byId = new Map(getTasks().map((t) => [t.id, t]));

    return (
      <div className="_3ZbQT" style={{ fontFamily, fontSize }}>
        {rows.map((row) => {
          const src = byId.get(row.id) ?? row;
          let expanderSymbol = "";
          if (row.hideChildren === false) expanderSymbol = "▼";
          else if (row.hideChildren === true) expanderSymbol = "▶";

          return (
            <div
              className="_34SS0"
              style={{ height: rowHeight }}
              key={`${row.id}-row`}
            >
              <div
                className="_3lLk3"
                style={{ minWidth: rowWidth, maxWidth: rowWidth }}
                title={row.name}
              >
                <div className="_nI1Xw">
                  <div
                    className={expanderSymbol ? "_2QjE6" : "_2TfEi"}
                    onClick={() => onExpanderClick(row)}
                  >
                    {expanderSymbol}
                  </div>
                  <div>{row.name}</div>
                </div>
              </div>
              <div
                className="_3lLk3"
                style={{ minWidth: rowWidth, maxWidth: rowWidth }}
              >
                &nbsp;{formatDate(src.start)}
              </div>
              <div
                className="_3lLk3"
                style={{ minWidth: rowWidth, maxWidth: rowWidth }}
              >
                &nbsp;{formatDate(inclusiveEnd(src.end))}
              </div>
            </div>
          );
        })}
      </div>
    );
  };
}
