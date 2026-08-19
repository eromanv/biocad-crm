import { useEffect, useId, useRef } from "react";
import type { Task } from "../types";
import { formatDate } from "../lib/gantt";

type TaskModalProps = {
  task: Task | null;
  taskNameById: Map<string, string>;
  loading: boolean;
  error: string | null;
  onClose: () => void;
};

export function TaskModal({
  task,
  taskNameById,
  loading,
  error,
  onClose,
}: TaskModalProps) {
  const titleId = useId();
  const closeRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (!task && !loading && !error) return;
    closeRef.current?.focus();
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [task, loading, error, onClose]);

  if (!task && !loading && !error) return null;

  return (
    <div className="modal-backdrop" role="presentation" onClick={onClose}>
      <div
        className="modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="modal-header">
          <h2 id={titleId}>{task?.name ?? "Детали задачи"}</h2>
          <button
            ref={closeRef}
            type="button"
            className="btn btn-ghost modal-close"
            onClick={onClose}
            aria-label="Закрыть"
          >
            ×
          </button>
        </div>

        {loading && <p className="muted">Загружаем…</p>}
        {error && <p className="error-text">{error}</p>}

        {task && (
          <dl className="task-details">
            <div>
              <dt>Описание</dt>
              <dd>{task.description || "—"}</dd>
            </div>
            <div>
              <dt>Исполнитель</dt>
              <dd>{task.assignee || "—"}</dd>
            </div>
            <div>
              <dt>Длительность</dt>
              <dd>
                {task.duration_days}{" "}
                {task.duration_days === 1
                  ? "день"
                  : task.duration_days >= 2 && task.duration_days <= 4
                    ? "дня"
                    : "дней"}
              </dd>
            </div>
            <div>
              <dt>Предшественники</dt>
              <dd>
                {task.predecessor_ids.length === 0
                  ? "—"
                  : task.predecessor_ids
                      .map((id) => taskNameById.get(id) ?? id)
                      .join(", ")}
              </dd>
            </div>
            <div>
              <dt>Начало</dt>
              <dd>{formatDate(task.start)}</dd>
            </div>
            <div>
              <dt>Окончание</dt>
              <dd>{formatDate(task.finish)}</dd>
            </div>
            <div>
              <dt>Критический путь</dt>
              <dd>
                {task.is_critical ? (
                  <span className="badge critical">Да</span>
                ) : (
                  "Нет"
                )}
              </dd>
            </div>
          </dl>
        )}
      </div>
    </div>
  );
}
