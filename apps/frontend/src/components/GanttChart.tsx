import { useMemo, useRef, useState } from "react";
import { Gantt, ViewMode } from "gantt-task-react";
import type { Task as GanttLibTask } from "gantt-task-react";
import "gantt-task-react/dist/index.css";
import type { Task } from "../types";
import { RuTaskListHeader } from "./RuTaskListHeader";
import {
  daysBetween,
  formatDate,
  toDateOnlyIso,
  toGanttTasks,
} from "../lib/gantt";

type GanttChartProps = {
  tasks: Task[];
  busy?: boolean;
  onTaskClick: (taskId: string) => void;
  onReschedule: (
    taskId: string,
    start: string,
    durationDays: number,
  ) => Promise<void>;
};

const VIEW_MODES: { label: string; mode: ViewMode }[] = [
  { label: "День", mode: ViewMode.Day },
  { label: "Неделя", mode: ViewMode.Week },
  { label: "Месяц", mode: ViewMode.Month },
];

/** Ignore bar click right after drag — library often fires click on mouseup. */
const CLICK_SUPPRESS_MS = 500;

export function GanttChart({
  tasks,
  busy = false,
  onTaskClick,
  onReschedule,
}: GanttChartProps) {
  const [viewMode, setViewMode] = useState<ViewMode>(ViewMode.Day);
  const ganttTasks = useMemo(() => toGanttTasks(tasks), [tasks]);
  const [localTasks, setLocalTasks] = useState(ganttTasks);
  // Update local tasks when source data changes, but not during drag
  const prevGanttTasks = useRef(ganttTasks);
  if (prevGanttTasks.current !== ganttTasks) {
    prevGanttTasks.current = ganttTasks;
    setLocalTasks(ganttTasks);
  }
  const suppressClickUntil = useRef(0);

  const columnWidth =
    viewMode === ViewMode.Month ? 220 : viewMode === ViewMode.Week ? 160 : 65;

  if (tasks.length === 0) {
    return (
      <div className="gantt-empty">
        <p className="empty-title">В плане пока нет задач</p>
        <p className="muted">
          Загрузите Excel или нажмите «Сбросить к демо» в шапке.
        </p>
      </div>
    );
  }

  const openTask = (taskId: string) => {
    if (Date.now() < suppressClickUntil.current) return;
    onTaskClick(taskId);
  };

  const handleDateChange = async (moved: GanttLibTask): Promise<boolean> => {
    if (busy) return false;
    suppressClickUntil.current = Date.now() + CLICK_SUPPRESS_MS;
    // Optimistically update local tasks so library doesn't remount
    setLocalTasks((prev) =>
      prev.map((t) => (t.id === moved.id ? { ...t, start: moved.start, end: moved.end } : t)),
    );
    const duration = Math.max(1, daysBetween(moved.start, moved.end));
    const start = toDateOnlyIso(moved.start);
    try {
      await onReschedule(moved.id, start, duration);
      suppressClickUntil.current = Date.now() + CLICK_SUPPRESS_MS;
      return true;
    } catch {
      // Revert on error
      setLocalTasks(ganttTasks);
      suppressClickUntil.current = Date.now() + CLICK_SUPPRESS_MS;
      return false;
    }
  };

  return (
    <div className="gantt-panel">
      <div className="gantt-view-bar">
        <span className="gantt-legend">
          <span className="swatch critical" /> Критический путь
          <span className="swatch normal" /> Остальные
          <span className="gantt-hint">
            Перетащите полоску · клик — детали
          </span>
        </span>
        <div className="view-toggle" role="group" aria-label="Масштаб шкалы">
          {VIEW_MODES.map(({ label, mode }) => (
            <button
              key={label}
              type="button"
              className={viewMode === mode ? "is-active" : ""}
              onClick={() => setViewMode(mode)}
            >
              {label}
            </button>
          ))}
        </div>
      </div>
      <div className={`gantt-scroll${busy ? " is-busy" : ""}`}>
        <Gantt
          tasks={localTasks}
          viewMode={viewMode}
          columnWidth={columnWidth}
          listCellWidth="160px"
          barFill={70}
          rowHeight={40}
          locale="ru"
          TaskListHeader={RuTaskListHeader}
          onClick={(task) => openTask(task.id)}
          onDoubleClick={(task) => openTask(task.id)}
          onDateChange={handleDateChange}
          onProgressChange={() => false}
          onDelete={() => false}
          TooltipContent={({ task }) => {
            const days = daysBetween(task.start, task.end);
            const suffix =
              days === 1 ? "день" : days >= 2 && days <= 4 ? "дня" : "дней";
            return (
              <div style={{ padding: "0.5rem 0.75rem", fontSize: "0.85rem", background: "#fff", borderRadius: "0.4rem", boxShadow: "0 2px 8px rgba(0,0,0,0.15)" }}>
                <b>{task.name}</b>
                <br />
                {formatDate(task.start)} — {formatDate(task.end)}
                <br />
                Длительность: {days} {suffix}
              </div>
            );
          }}
        />
      </div>
    </div>
  );
}
