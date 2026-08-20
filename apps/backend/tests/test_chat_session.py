import asyncio

import pytest

from chat_session import ChatSession, ChatSessionStore, new_session_id, valid_session_id


def test_new_session_id_is_urlsafe_and_valid():
    sid = new_session_id()
    assert valid_session_id(sid)
    assert not valid_session_id(None)
    assert not valid_session_id("short")
    assert not valid_session_id("bad id with spaces!!!!")


def test_append_trims_and_caps_history():
    session = ChatSession(max_messages=3, max_content_len=20)
    session.append("user", "  one  ")
    session.append("assistant", "x" * 50)
    session.append("user", "")
    session.append("user", "two")
    session.append("user", "three")
    assert [t.content for t in session.messages] == [
        "xxxxxxxxxxxxxxxxxxx…",
        "two",
        "three",
    ]
    hist = session.history_before_last_user()
    assert [h["content"] for h in hist] == ["xxxxxxxxxxxxxxxxxxx…", "two"]


def test_store_expires_sessions_by_ttl():
    now = 100.0
    store = ChatSessionStore(ttl_seconds=10, max_sessions=10, time_fn=lambda: now)
    first = store.get_or_create("a" * 16)
    first.append("user", "hello")
    now = 111.0
    second = store.get_or_create("b" * 16)
    assert first is not store.get_or_create("a" * 16)
    assert second is store.get_or_create("b" * 16)


def test_store_evicts_oldest_when_full():
    now = 1.0
    store = ChatSessionStore(ttl_seconds=1000, max_sessions=2, time_fn=lambda: now)
    store.get_or_create("a" * 16).append("user", "a")
    now = 2.0
    store.get_or_create("b" * 16).append("user", "b")
    now = 3.0
    store.get_or_create("c" * 16).append("user", "c")
    assert "a" * 16 not in store
    assert "b" * 16 in store
    assert "c" * 16 in store


def test_session_clear_resets_history_and_focus():
    session = ChatSession(last_task_id=6)
    session.append("user", "hi")
    session.append("assistant", "ok")
    session.clear()
    assert list(session.messages) == []
    assert session.last_task_id is None


def test_store_clear_resets_existing_session():
    store = ChatSessionStore(ttl_seconds=1000, max_sessions=10)
    sid = "a" * 16
    sess = store.get_or_create(sid)
    sess.append("user", "hello")
    sess.last_task_id = 3
    assert store.clear(sid) is True
    assert list(sess.messages) == []
    assert sess.last_task_id is None
    assert store.clear("missing-session-id!") is False


@pytest.mark.asyncio
async def test_session_lock_serializes_updates():
    session = ChatSession()
    order: list[str] = []

    async def worker(tag: str) -> None:
        async with session.lock:
            order.append(f"start-{tag}")
            await asyncio.sleep(0.02)
            order.append(f"end-{tag}")

    await asyncio.gather(worker("x"), worker("y"))
    starts_before_other_end = order in (
        ["start-x", "end-x", "start-y", "end-y"],
        ["start-y", "end-y", "start-x", "end-x"],
    )
    assert starts_before_other_end
