import type { Plan, Task } from "./types";
import { humanizeMessage, readHttpError } from "./lib/errors";

/**
 * API base URL resolution:
 * - Empty / relative → same-origin (Vite proxy `/api` → backend:8001)
 * - Absolute VITE_API_URL → used as-is (compose sets http://localhost:8001)
 */
function resolveApiBase(): string {
  const raw = import.meta.env.VITE_API_URL;
  if (raw === undefined || raw === "" || raw === "/") {
    return "";
  }
  return raw.replace(/\/$/, "");
}

const API_BASE = resolveApiBase();

function url(path: string): string {
  return `${API_BASE}${path}`;
}

async function parseError(res: Response): Promise<never> {
  throw new Error(await readHttpError(res));
}

export async function fetchPlan(): Promise<Plan> {
  const res = await fetch(url("/api/plan"));
  if (!res.ok) await parseError(res);
  return normalizePlan(await res.json());
}

export async function fetchTask(id: string): Promise<Task> {
  const res = await fetch(url(`/api/tasks/${encodeURIComponent(id)}`));
  if (!res.ok) await parseError(res);
  return normalizeTask((await res.json()) as Record<string, unknown>);
}

export async function importPlan(file: File): Promise<Plan> {
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(url("/api/plan/import"), {
    method: "POST",
    body: form,
  });
  if (!res.ok) await parseError(res);
  return normalizePlan(await res.json());
}

export async function exportPlan(): Promise<void> {
  const res = await fetch(url("/api/plan/export"));
  if (!res.ok) await parseError(res);
  const blob = await res.blob();
  const disposition = res.headers.get("Content-Disposition");
  const match = disposition?.match(/filename="?([^"]+)"?/i);
  const filename = match?.[1] ?? "plan.xlsx";
  const href = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = href;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(href);
}

export async function resetPlan(): Promise<Plan> {
  const res = await fetch(url("/api/plan/reset"), { method: "POST" });
  if (!res.ok) await parseError(res);
  return normalizePlan(await res.json());
}

export async function rescheduleTask(
  taskId: string,
  start: string,
  durationDays: number,
): Promise<Plan> {
  const res = await fetch(url(`/api/tasks/${encodeURIComponent(taskId)}/reschedule`), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ start, duration_days: durationDays }),
  });
  if (!res.ok) await parseError(res);
  return normalizePlan(await res.json());
}

function normalizeTask(raw: Record<string, unknown>): Task {
  const preds = Array.isArray(raw.predecessor_ids) ? raw.predecessor_ids : [];
  return {
    id: String(raw.id),
    name: String(raw.name ?? ""),
    description: String(raw.description ?? ""),
    assignee: String(raw.assignee ?? ""),
    duration_days: Number(raw.duration_days) || 1,
    predecessor_ids: preds.map((p) => String(p)),
    start: String(raw.start ?? ""),
    finish: String(raw.finish ?? ""),
    is_critical: Boolean(raw.is_critical),
  };
}

function normalizePlan(raw: unknown): Plan {
  const obj = raw as { project_start?: string; tasks?: unknown[] };
  return {
    project_start: String(obj.project_start ?? ""),
    tasks: Array.isArray(obj.tasks)
      ? obj.tasks.map((t) => normalizeTask(t as Record<string, unknown>))
      : [],
  };
}

/**
 * SSE chat contract (backend):
 * - `event: token`  data: plain text chunk (or JSON `{"text":"..."}`)
 * - `event: message` / default: JSON `{"type":"token","text":"..."}` or `{"type":"plan_updated"}`
 * - `event: plan_updated`  data: optional Plan JSON or empty → client refetches GET /api/plan
 * - `event: error`  data: error message
 * - `event: done`  stream complete
 */
export type ChatSseHandlers = {
  onToken: (text: string) => void;
  onPlanUpdated: (plan?: Plan) => void;
  onError: (message: string) => void;
};

export async function sendChatMessage(
  message: string,
  handlers: ChatSseHandlers,
  signal?: AbortSignal,
): Promise<void> {
  const timeout = AbortSignal.timeout(120_000);
  const linked = signal ? AbortSignal.any([signal, timeout]) : timeout;

  const res = await fetch(url("/api/chat"), {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Accept: "text/event-stream",
      "Cache-Control": "no-cache",
    },
    body: JSON.stringify({ message }),
    signal: linked,
  });

  if (!res.ok) {
    await parseError(res);
    return;
  }

  if (!res.body) {
    throw new Error(humanizeMessage("Chat response had no body"));
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  const dispatch = (eventName: string, data: string) => {
    const trimmed = data.trim();
    if (!trimmed && eventName !== "plan_updated") return;

    if (eventName === "token" || eventName === "delta") {
      try {
        const parsed = JSON.parse(trimmed) as { text?: string; content?: string };
        handlers.onToken(parsed.text ?? parsed.content ?? trimmed);
      } catch {
        handlers.onToken(trimmed);
      }
      return;
    }

    if (eventName === "plan_updated") {
      if (!trimmed || trimmed === "{}") {
        handlers.onPlanUpdated();
        return;
      }
      try {
        const parsed = JSON.parse(trimmed) as {
          tasks?: Task[];
          project_start?: string;
          plan?: Plan;
        };
        const plan: Plan | undefined =
          Array.isArray(parsed.tasks) && parsed.project_start
            ? normalizePlan(parsed)
            : parsed.plan
              ? normalizePlan(parsed.plan)
              : undefined;
        handlers.onPlanUpdated(plan);
      } catch {
        handlers.onPlanUpdated();
      }
      return;
    }

    if (eventName === "error") {
      try {
        const parsed = JSON.parse(trimmed) as { message?: string; detail?: string };
        handlers.onError(
          humanizeMessage(parsed.message ?? parsed.detail ?? trimmed),
        );
      } catch {
        handlers.onError(humanizeMessage(trimmed));
      }
      return;
    }

    if (eventName === "done" || eventName === "end") {
      return;
    }

    // Default / message: try JSON envelope
    try {
      const parsed = JSON.parse(trimmed) as {
        type?: string;
        text?: string;
        content?: string;
        message?: string;
        plan?: Plan;
      };
      if (parsed.type === "token" || parsed.type === "delta") {
        handlers.onToken(parsed.text ?? parsed.content ?? "");
      } else if (parsed.type === "plan_updated") {
        handlers.onPlanUpdated(parsed.plan ? normalizePlan(parsed.plan) : undefined);
      } else if (parsed.type === "error") {
        handlers.onError(
          humanizeMessage(parsed.message ?? parsed.content ?? "Chat error"),
        );
      } else if (parsed.text || parsed.content) {
        handlers.onToken(parsed.text ?? parsed.content ?? "");
      }
    } catch {
      // Plain text token on unnamed event
      if (eventName === "message" || eventName === "") {
        handlers.onToken(trimmed);
      }
    }
  };

  const flushBlock = (block: string) => {
    if (!block.trim()) return;
    let eventName = "message";
    const dataLines: string[] = [];
    for (const line of block.split(/\r?\n/)) {
      if (line.startsWith("event:")) {
        eventName = line.slice(6).trim();
      } else if (line.startsWith("data:")) {
        dataLines.push(line.slice(5).replace(/^ /, ""));
      }
    }
    dispatch(eventName, dataLines.join("\n"));
  };

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const parts = buffer.split(/\r?\n\r?\n/);
    buffer = parts.pop() ?? "";
    for (const part of parts) {
      flushBlock(part);
    }
  }
  if (buffer.trim()) {
    flushBlock(buffer);
  }
}

export { API_BASE };
