import { useEffect, useRef, useState } from "react";
import type { ChatMessage } from "../types";

type ChatPanelProps = {
  messages: ChatMessage[];
  streaming: boolean;
  onSend: (text: string) => void;
};

export function ChatPanel({ messages, streaming, onSend }: ChatPanelProps) {
  const [draft, setDraft] = useState("");
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, streaming]);

  const submit = (e: { preventDefault: () => void }) => {
    e.preventDefault();
    const text = draft.trim();
    if (!text || streaming) return;
    setDraft("");
    onSend(text);
  };

  return (
    <aside className="chat-panel">
      <div className="chat-header">
        <h2>Чат с планом</h2>
        <p className="muted">
          На естественном языке: сдвинуть задачи, сменить исполнителей, добавить
          зависимости.
        </p>
      </div>

      <div className="chat-messages" aria-live="polite">
        {messages.length === 0 && (
          <div className="chat-placeholder">
            <p>Примеры:</p>
            <ul>
              <li>«Сдвинь все задачи Ивана на 3 дня»</li>
              <li>«Добавь задачу QA после разработки»</li>
              <li>«Назначь тестирование на Марию»</li>
            </ul>
          </div>
        )}
        {messages.map((m) => (
          <div
            key={m.id}
            className={`chat-bubble chat-${m.role}${m.isError ? " chat-error" : ""}`}
            role={m.isError ? "alert" : undefined}
          >
            {m.content ||
              (m.role === "assistant" && streaming ? (
                <span className="typing">Думаю…</span>
              ) : (
                ""
              ))}
          </div>
        ))}
        <div ref={bottomRef} />
      </div>

      <form className="chat-composer" onSubmit={submit}>
        <textarea
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          placeholder="Напишите, что изменить в плане…"
          rows={2}
          disabled={streaming}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              submit(e);
            }
          }}
        />
        <button
          type="button"
          className="btn btn-primary"
          disabled={streaming || !draft.trim()}
          onClick={(e) => submit(e)}
        >
          {streaming ? "…" : "Отправить"}
        </button>
      </form>
    </aside>
  );
}
