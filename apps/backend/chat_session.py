"""In-memory chat sessions keyed by a server-issued cookie."""

from __future__ import annotations

import asyncio
import os
import re
import secrets
import time
from collections import deque
from dataclasses import dataclass, field

CHAT_COOKIE_NAME = os.environ.get("CHAT_COOKIE_NAME", "biocad_chat_sid")
CHAT_SESSION_TTL = max(60, int(os.environ.get("CHAT_SESSION_TTL", "1800")))
CHAT_SESSION_MAX_MESSAGES = max(2, int(os.environ.get("CHAT_SESSION_MAX_MESSAGES", "12")))
CHAT_SESSION_MAX = max(1, int(os.environ.get("CHAT_SESSION_MAX", "1000")))
CHAT_COOKIE_SECURE = os.environ.get("CHAT_COOKIE_SECURE", "false").lower() in (
    "true",
    "1",
    "yes",
)

_SID_RE = re.compile(r"^[A-Za-z0-9_-]{16,64}$")


def new_session_id() -> str:
    return secrets.token_urlsafe(32)


def valid_session_id(value: str | None) -> bool:
    return bool(value) and _SID_RE.match(value or "") is not None


@dataclass
class ChatTurn:
    role: str
    content: str


@dataclass
class ChatSession:
    last_task_id: int | None = None
    last_seen: float = 0.0
    max_messages: int = CHAT_SESSION_MAX_MESSAGES
    max_content_len: int = 2000
    messages: deque[ChatTurn] = field(default_factory=deque)
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    def append(self, role: str, content: str) -> None:
        text = (content or "").strip()
        if not text:
            return
        if len(text) > self.max_content_len:
            text = text[: self.max_content_len - 1].rstrip() + "…"
        self.messages.append(ChatTurn(role=role, content=text))
        while len(self.messages) > self.max_messages:
            self.messages.popleft()

    def clear(self) -> None:
        self.messages.clear()
        self.last_task_id = None

    def history_before_last_user(self) -> list[dict[str, str]]:
        turns = list(self.messages)
        if turns and turns[-1].role == "user":
            turns = turns[:-1]
        return [{"role": t.role, "content": t.content} for t in turns]


class ChatSessionStore:
    def __init__(
        self,
        *,
        ttl_seconds: float = CHAT_SESSION_TTL,
        max_messages: int = CHAT_SESSION_MAX_MESSAGES,
        max_sessions: int = CHAT_SESSION_MAX,
        time_fn=time.monotonic,
    ) -> None:
        self._ttl = ttl_seconds
        self._max_messages = max_messages
        self._max_sessions = max_sessions
        self._time = time_fn
        self._sessions: dict[str, ChatSession] = {}

    def _purge(self, now: float) -> None:
        expired = [sid for sid, sess in self._sessions.items() if now - sess.last_seen > self._ttl]
        for sid in expired:
            del self._sessions[sid]

    def get_or_create(self, sid: str) -> ChatSession:
        now = float(self._time())
        self._purge(now)
        sess = self._sessions.get(sid)
        if sess is None:
            if len(self._sessions) >= self._max_sessions:
                oldest_sid = min(self._sessions, key=lambda key: self._sessions[key].last_seen)
                del self._sessions[oldest_sid]
            sess = ChatSession(last_seen=now, max_messages=self._max_messages)
            self._sessions[sid] = sess
        sess.last_seen = now
        return sess

    def clear(self, sid: str) -> bool:
        """Reset an existing session's history and focus. Returns True if found."""
        sess = self._sessions.get(sid)
        if sess is None:
            return False
        sess.clear()
        sess.last_seen = float(self._time())
        return True

    def __contains__(self, sid: object) -> bool:
        return sid in self._sessions
