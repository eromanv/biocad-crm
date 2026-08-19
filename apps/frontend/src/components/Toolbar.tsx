import type { Plan } from "../types";

type ToolbarProps = {
  plan: Plan | null;
  busy: boolean;
  onImport: (file: File) => void;
  onExport: () => void;
  onReset: () => void;
};

function formatStart(iso: string): string {
  const d = iso.slice(0, 10);
  const [y, m, day] = d.split("-");
  if (!y || !m || !day) return iso;
  return `${day}.${m}.${y}`;
}

export function Toolbar({ plan, busy, onImport, onExport, onReset }: ToolbarProps) {
  return (
    <header className="toolbar">
      <div className="toolbar-brand">
        <span className="brand-mark">Biocad</span>
        {plan && (
          <span className="brand-meta">
            Старт {formatStart(plan.project_start)} · {plan.tasks.length}{" "}
            {pluralTasks(plan.tasks.length)}
          </span>
        )}
      </div>

      <div className="toolbar-actions">
        <label className={`btn btn-secondary ${busy ? "is-disabled" : ""}`}>
          Загрузить Excel
          <input
            type="file"
            accept=".xlsx,.xls,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            hidden
            disabled={busy}
            onChange={(e) => {
              const file = e.target.files?.[0];
              e.target.value = "";
              if (file) onImport(file);
            }}
          />
        </label>
        <button
          type="button"
          className="btn btn-secondary"
          disabled={busy || !plan}
          onClick={onExport}
        >
          Экспорт
        </button>
        <button
          type="button"
          className="btn btn-ghost"
          disabled={busy}
          onClick={onReset}
        >
          Сбросить к демо
        </button>
      </div>
    </header>
  );
}

function pluralTasks(n: number): string {
  const mod10 = n % 10;
  const mod100 = n % 100;
  if (mod10 === 1 && mod100 !== 11) return "задача";
  if (mod10 >= 2 && mod10 <= 4 && (mod100 < 12 || mod100 > 14)) return "задачи";
  return "задач";
}
