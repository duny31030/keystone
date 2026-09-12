"""运行时状态（gitignored 的 .state/）：会话↔任务绑定、元数据事件日志。

sessions.json 会被多个 hook 进程并发读写（CodeBuddy 可能同时触发
UserPromptSubmit 与 PreToolUse），因此读改写整体放在 flock 临界区内。
"""

from __future__ import annotations

import fcntl
import json
from contextlib import contextmanager

from keystone.store.layout import KeystoneLayout
from keystone.util import atomic_write_json, now_iso, read_json


@contextmanager
def _sessions_locked(layout: KeystoneLayout):
    layout.state_dir.mkdir(parents=True, exist_ok=True)
    lock_path = layout.state_dir / "sessions.lock"
    with open(lock_path, "w") as lock_file:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


def get_binding(layout: KeystoneLayout, session_id: str) -> str | None:
    if not layout.sessions_json.is_file():
        return None
    data = read_json(layout.sessions_json, default={}) or {}
    entry = data.get(session_id)
    return entry.get("task_code") if isinstance(entry, dict) else None


def bind_session(layout: KeystoneLayout, session_id: str, task_code: str) -> None:
    with _sessions_locked(layout):
        data = read_json(layout.sessions_json, default={}) or {}
        data[session_id] = {"task_code": task_code, "updated_at": now_iso()}
        atomic_write_json(layout.sessions_json, data)


def unbind_session(layout: KeystoneLayout, session_id: str) -> None:
    with _sessions_locked(layout):
        data = read_json(layout.sessions_json, default={}) or {}
        if data.pop(session_id, None) is not None:
            atomic_write_json(layout.sessions_json, data)


def append_event(layout: KeystoneLayout, payload: dict) -> None:
    """追加一条元数据事件（JSONL，一行一条，只存元数据不存内容）。"""
    layout.state_dir.mkdir(parents=True, exist_ok=True)
    payload = {"at": now_iso(), **payload}
    line = json.dumps(payload, ensure_ascii=False)
    with open(layout.events_jsonl, "a", encoding="utf-8") as f:
        f.write(line + "\n")
