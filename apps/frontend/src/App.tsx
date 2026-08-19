import { useCallback, useEffect, useMemo, useState } from "react";
import {
  exportPlan,
  fetchPlan,
  fetchTask,
  importPlan,
  rescheduleTask,
  resetPlan,
  sendChatMessage,
} from "./api";
import { ChatPanel } from "./components/ChatPanel";
import { GanttChart } from "./components/GanttChart";
import { TaskModal } from "./components/TaskModal";
import { Toolbar } from "./components/Toolbar";
import { humanizeUnknown } from "./lib/errors";
import type { ChatMessage, Plan, Task } from "./types";

function newId(): string {
  return crypto.randomUUID();
}

export default function App() {
  const [plan, setPlan] = useState<Plan | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState<string | null>(null);
  const [statusTone, setStatusTone] = useState<"info" | "error">("info");

  const [selectedTask, setSelectedTask] = useState<Task | null>(null);
  const [modalLoading, setModalLoading] = useState(false);
  const [modalError, setModalError] = useState<string | null>(null);
  const [modalOpen, setModalOpen] = useState(false);

  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [streaming, setStreaming] = useState(false);

  const taskNameById = useMemo(() => {
    const map = new Map<string, string>();
    for (const t of plan?.tasks ?? []) {
      map.set(t.id, t.name);
    }
    return map;
  }, [plan]);

  const refreshPlan = useCallback(async () => {
    const next = await fetchPlan();
    setPlan(next);
    return next;
  }, []);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const next = await fetchPlan();
        if (!cancelled) {
          setPlan(next);
          setLoadError(null);
        }
      } catch (err) {
        if (!cancelled) {
          setLoadError(humanizeUnknown(err, "Не удалось загрузить план."));
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const withBusy = async (label: string, fn: () => Promise<void>) => {
    setBusy(true);
    setStatusTone("info");
    setStatus(label);
    try {
      await fn();
      setStatus(null);
    } catch (err) {
      setStatusTone("error");
      setStatus(humanizeUnknown(err, "Действие не выполнено."));
    } finally {
      setBusy(false);
    }
  };

  const handleImport = (file: File) =>
    withBusy("Загружаем Excel…", async () => {
      const next = await importPlan(file);
      setPlan(next);
      setLoadError(null);
    });

  const handleExport = () =>
    withBusy("Готовим Excel…", async () => {
      await exportPlan();
    });

  const handleReset = () =>
    withBusy("Восстанавливаем демо-план…", async () => {
      const next = await resetPlan();
      setPlan(next);
      setLoadError(null);
    });

  const handleReschedule = async (
    taskId: string,
    start: string,
    durationDays: number,
  ) => {
    setBusy(true);
    setStatusTone("info");
    setStatus("Обновляем расписание…");
    try {
      const next = await rescheduleTask(taskId, start, durationDays);
      setPlan(next);
      setStatus(null);
    } catch (err) {
      setStatusTone("error");
      setStatus(humanizeUnknown(err, "Не удалось сдвинуть задачу."));
      throw err;
    } finally {
      setBusy(false);
    }
  };

  const handleTaskClick = async (taskId: string) => {
    setModalOpen(true);
    setModalError(null);
    const fromPlan = plan?.tasks.find((t) => t.id === taskId) ?? null;
    setSelectedTask(fromPlan);
    setModalLoading(true);
    try {
      const detail = await fetchTask(taskId);
      setSelectedTask(detail);
    } catch (err) {
      if (!fromPlan) {
        setModalError(
          humanizeUnknown(err, "Не удалось открыть детали задачи."),
        );
      }
    } finally {
      setModalLoading(false);
    }
  };

  const closeModal = () => {
    setModalOpen(false);
    setSelectedTask(null);
    setModalError(null);
  };

  const handleSend = async (text: string) => {
    const userMsg: ChatMessage = { id: newId(), role: "user", content: text };
    const assistantId = newId();
    setMessages((prev) => [
      ...prev,
      userMsg,
      { id: assistantId, role: "assistant", content: "" },
    ]);
    setStreaming(true);

    try {
      await sendChatMessage(text, {
        onToken: (chunk) => {
          setMessages((prev) =>
            prev.map((m) =>
              m.id === assistantId
                ? { ...m, content: m.content + chunk, isError: false }
                : m,
            ),
          );
        },
        onPlanUpdated: async (maybePlan) => {
          if (maybePlan?.tasks) {
            setPlan(maybePlan);
          } else {
            try {
              await refreshPlan();
            } catch (err) {
              setStatusTone("error");
              setStatus(
                humanizeUnknown(
                  err,
                  "План изменился, но обновить диаграмму не удалось.",
                ),
              );
            }
          }
        },
        onError: (message) => {
          setMessages((prev) =>
            prev.map((m) =>
              m.id === assistantId
                ? {
                    ...m,
                    content: m.content || message,
                    isError: true,
                  }
                : m,
            ),
          );
        },
      });
    } catch (err) {
      const msg = humanizeUnknown(err, "Не удалось отправить сообщение.");
      setMessages((prev) =>
        prev.map((m) =>
          m.id === assistantId
            ? { ...m, content: m.content || msg, isError: true }
            : m,
        ),
      );
    } finally {
      setStreaming(false);
    }
  };

  const bannerError = Boolean(loadError || statusTone === "error");
  const bannerText = loadError ?? status;

  return (
    <div className="shell">
      <Toolbar
        plan={plan}
        busy={busy || streaming}
        onImport={handleImport}
        onExport={handleExport}
        onReset={handleReset}
      />

      <div className="workspace">
        <section className="gantt-area" aria-label="Диаграмма Ганта">
          {plan ? (
            <GanttChart
              tasks={plan.tasks}
              busy={busy || streaming}
              onTaskClick={handleTaskClick}
              onReschedule={handleReschedule}
            />
          ) : (
            <div className="gantt-empty">
              <p className="empty-title">
                {loadError ? "План недоступен" : "Загружаем план…"}
              </p>
              {loadError && (
                <p className="muted">
                  Проверьте, что backend на порту 8001 запущен, затем нажмите
                  «Повторить».
                </p>
              )}
            </div>
          )}
        </section>
        <ChatPanel
          messages={messages}
          streaming={streaming}
          onSend={handleSend}
        />
      </div>

      {modalOpen && (
        <TaskModal
          task={selectedTask}
          taskNameById={taskNameById}
          loading={modalLoading}
          error={modalError}
          onClose={closeModal}
        />
      )}

      {bannerText && (
        <div
          className={`toast ${bannerError ? "toast-error" : "toast-info"}`}
          role={bannerError ? "alert" : "status"}
        >
          <span className="toast-text">{bannerText}</span>
          {loadError && (
            <button
              type="button"
              className="btn btn-ghost"
              onClick={() =>
                withBusy("Загружаем план…", async () => {
                  await refreshPlan();
                  setLoadError(null);
                })
              }
            >
              Повторить
            </button>
          )}
          {!loadError && statusTone === "error" && (
            <button
              type="button"
              className="btn btn-ghost"
              onClick={() => setStatus(null)}
            >
              Скрыть
            </button>
          )}
        </div>
      )}
    </div>
  );
}
