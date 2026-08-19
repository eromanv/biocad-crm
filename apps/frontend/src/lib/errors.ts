/** Turn API / network / domain errors into short Russian copy for the UI. */

const STATUS_HINTS: Record<number, string> = {
  400: "Запрос отклонён — проверьте данные и попробуйте снова.",
  404: "Нужный ресурс не найден.",
  409: "Конфликт данных. Обновите план и повторите действие.",
  413: "Файл слишком большой.",
  415: "Неподдерживаемый формат файла. Нужен Excel (.xlsx).",
  422: "Данные не прошли проверку.",
  429: "Слишком много запросов. Подождите немного.",
  500: "Внутренняя ошибка сервера. Попробуйте позже.",
  502: "Сервер временно недоступен.",
  503: "Сервис временно недоступен.",
  504: "Сервер не ответил вовремя.",
};

/** Known backend / domain phrases → human Russian. */
const PHRASE_MAP: Array<[RegExp, string | ((m: RegExpMatchArray) => string)]> = [
  [
    /OPENROUTER_API_KEY|not configured/i,
    "Чат недоступен: не задан ключ OpenRouter. Добавьте OPENROUTER_API_KEY в .env и перезапустите backend.",
  ],
  [
    /CHAT_ENABLED=false|чат отключён/i,
    "Чат отключён (CHAT_ENABLED=false). Включите в .env и перезапустите backend.",
  ],
  [
    /слишком длинное|max\.?\s*\d+\s*символ/i,
    "Сообщение слишком длинное. Сократите текст и отправьте снова.",
  ],
  [
    /слишком много сообщений/i,
    "Слишком много сообщений. Подождите минуту и попробуйте снова.",
  ],
  [
    /Database not ready/i,
    "База данных ещё поднимается. Подождите пару секунд и нажмите «Повторить».",
  ],
  [/Empty file/i, "Файл пустой. Выберите Excel со списком задач."],
  [/Excel is empty/i, "В Excel нет данных. Добавьте строки с задачами."],
  [/No tasks found in Excel/i, "В Excel не найдено ни одной задачи."],
  [
    /Missing required columns/i,
    "В Excel не хватает обязательных колонок: задача, описание, исполнитель, длительность, предшественники.",
  ],
  [
    /Cycle detected/i,
    "В зависимостях задач есть цикл — план нельзя рассчитать. Исправьте предшественников.",
  ],
  [
    /Row (\d+):\s*empty task name/i,
    (m) => `Строка ${m[1]}: пустое название задачи.`,
  ],
  [
    /Row (\d+):\s*invalid duration/i,
    (m) => `Строка ${m[1]}: некорректная длительность (нужно целое число дней).`,
  ],
  [
    /Row (\d+):\s*duration must be >= 1/i,
    (m) => `Строка ${m[1]}: длительность должна быть не меньше 1 дня.`,
  ],
  [
    /Row (\d+):\s*unknown predecessor ['"]?([^'"]+)['"]?/i,
    (m) => `Строка ${m[1]}: неизвестный предшественник «${m[2]}».`,
  ],
  [
    /Duplicate task name:\s*(.+)/i,
    (m) => `Дублируется название задачи: «${m[1].trim()}».`,
  ],
  [
    /Unknown predecessor id\s+(\S+)/i,
    (m) => `Неизвестный предшественник: ${m[1]}.`,
  ],
  [
    /cannot be its own predecessor/i,
    "Задача не может ссылаться сама на себя как на предшественника.",
  ],
  [/Task (\d+) not found/i, (m) => `Задача №${m[1]} не найдена.`],
  [/Unknown task ids:\s*(.+)/i, (m) => `Неизвестные задачи: ${m[1]}.`],
  [
    /Failed to fetch|NetworkError|Load failed|fetch failed/i,
    "Не удалось связаться с сервером. Проверьте, что backend запущен на порту 8001.",
  ],
  [/Chat response had no body/i, "Сервер вернул пустой ответ чата."],
  [/Aborted|AbortError/i, "Запрос отменён."],
  [
    /Stopped after too many tool rounds/i,
    "Агент слишком долго крутился вокруг инструментов и остановился. Упростите запрос.",
  ],
  [
    /insufficient.?quota|rate.?limit|429/i,
    "Лимит запросов к модели исчерпан. Попробуйте позже или смените модель в .env.",
  ],
  [
    /Incorrect API key|invalid.?api.?key|401/i,
    "Ключ OpenRouter отклонён. Проверьте OPENROUTER_API_KEY в .env.",
  ],
];

function extractDetail(body: unknown): string | null {
  if (!body || typeof body !== "object") return null;
  const obj = body as Record<string, unknown>;

  const detail = obj.detail ?? obj.message ?? obj.error;
  if (typeof detail === "string" && detail.trim()) return detail.trim();

  if (Array.isArray(detail)) {
    const parts = detail
      .map((item) => {
        if (typeof item === "string") return item;
        if (item && typeof item === "object") {
          const row = item as { msg?: string; loc?: unknown[]; message?: string };
          const where = Array.isArray(row.loc)
            ? row.loc.filter((x) => x !== "body").join(".")
            : "";
          const msg = row.msg ?? row.message ?? "";
          return where ? `${where}: ${msg}` : msg;
        }
        return "";
      })
      .filter(Boolean);
    if (parts.length) return parts.join("; ");
  }

  if (typeof obj.title === "string") return obj.title;
  return null;
}

export function humanizeMessage(raw: string, status?: number): string {
  const text = raw.trim();
  if (!text && status != null) {
    return STATUS_HINTS[status] ?? `Ошибка запроса (${status}).`;
  }

  for (const [re, mapped] of PHRASE_MAP) {
    const m = text.match(re);
    if (m) return typeof mapped === "function" ? mapped(m) : mapped;
  }

  // Already Russian / short enough — keep as-is
  if (/[А-Яа-яЁё]/.test(text) && text.length < 280) return text;

  if (status != null && STATUS_HINTS[status]) {
    // Technical English leftover — prefer status hint + short excerpt
    if (/^[A-Za-z0-9_./:\- "'`]+$/.test(text) && text.length > 80) {
      return STATUS_HINTS[status];
    }
  }

  return text || (status != null ? `Ошибка запроса (${status}).` : "Что-то пошло не так.");
}

export async function readHttpError(res: Response): Promise<string> {
  let raw = res.statusText || "";
  try {
    const body: unknown = await res.json();
    raw = extractDetail(body) ?? raw;
  } catch {
    try {
      const text = await res.text();
      if (text.trim()) raw = text.trim().slice(0, 400);
    } catch {
      /* ignore */
    }
  }
  return humanizeMessage(raw, res.status);
}

export function humanizeUnknown(err: unknown, fallback = "Действие не выполнено."): string {
  if (err instanceof Error) return humanizeMessage(err.message);
  if (typeof err === "string") return humanizeMessage(err);
  return fallback;
}
