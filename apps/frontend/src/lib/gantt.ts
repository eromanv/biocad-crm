import type { Task as GanttLibTask } from "gantt-task-react";
import type { Task } from "../types";

/** Calendar-day difference (local dates), end exclusive relative to start. */
export function daysBetween(start: Date, end: Date): number {
  const a = Date.UTC(start.getFullYear(), start.getMonth(), start.getDate());
  const b = Date.UTC(end.getFullYear(), end.getMonth(), end.getDate());
  return Math.round((b - a) / 86_400_000);
}

export function toDateOnlyIso(value: Date): string {
  const y = value.getFullYear();
  const m = String(value.getMonth() + 1).padStart(2, "0");
  const d = String(value.getDate()).padStart(2, "0");
  return `${y}-${m}-${d}`;
}

/** Map API tasks → gantt-task-react Task shape (end is exclusive). */
export function toGanttTasks(tasks: Task[]): GanttLibTask[] {
  return tasks.map((t) => {
    const start = parseDate(t.start);
    const end = new Date(start);
    end.setDate(end.getDate() + Math.max(t.duration_days, 1));
    return {
      id: t.id,
      name: t.name,
      start,
      end,
      progress: t.is_critical ? 100 : 0,
      type: "task" as const,
      dependencies: t.predecessor_ids,
      styles: t.is_critical
        ? {
            backgroundColor: "#e11d48",
            backgroundSelectedColor: "#be123c",
            progressColor: "#e11d48",
            progressSelectedColor: "#be123c",
          }
        : {
            backgroundColor: "#0d9488",
            backgroundSelectedColor: "#0f766e",
            progressColor: "#0d9488",
            progressSelectedColor: "#0f766e",
          },
    };
  });
}

export function parseDate(value: string): Date {
  // Accept ISO date or datetime; force local midnight for date-only strings
  if (/^\d{4}-\d{2}-\d{2}$/.test(value)) {
    const [y, m, d] = value.split("-").map(Number);
    return new Date(y, m - 1, d);
  }
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) {
    return new Date();
  }
  return d;
}

export function formatDate(value: string | Date): string {
  const d = typeof value === "string" ? parseDate(value) : value;
  return d.toLocaleDateString("ru-RU", {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

/** Fingerprint so Gantt remounts when schedule changes (library keeps internal state). */
export function scheduleKey(tasks: Task[]): string {
  return tasks.map((t) => `${t.id}:${t.start}:${t.finish}:${t.duration_days}`).join("|");
}
