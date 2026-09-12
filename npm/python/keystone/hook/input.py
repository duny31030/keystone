"""Hook stdin 解析：带超时守护地读取 JSON，并做字段兼容归一。

字段命名兼容 camelCase 变体与常见别名（依据 trellis 在 CodeBuddy/Claude/ZCode
上验证过的实际 payload 形态）；cwd/session 另接受平台注入的环境变量兜底。
"""

from __future__ import annotations

import json
import os
import sys
import threading
from pathlib import Path

STDIN_READ_TIMEOUT = 2.0

# 同一字段的多种命名（trellis hooks 的兼容策略：snake_case 优先）
_FIELD_ALIASES = {
    "session_id": ("session_id", "sessionId", "sessionID", "conversation_id"),
    "transcript_path": ("transcript_path", "transcriptPath", "transcript"),
    "cwd": ("cwd", "workspace", "project_dir", "projectDir"),
    "hook_event_name": ("hook_event_name", "hookEventName", "event"),
    "prompt": ("prompt", "user_prompt", "userPrompt"),
    "tool_name": ("tool_name", "toolName"),
    "tool_input": ("tool_input", "toolInput", "toolArgs"),
    "tool_response": ("tool_response", "toolResponse", "response"),
    "reason": ("reason",),
}


def read_hook_input(timeout: float = STDIN_READ_TIMEOUT) -> dict:
    """从 stdin 读取 hook JSON。

    宿主平台不关闭 stdin 时不能永久阻塞：用守护线程限时读取。
    任何失败（超时/EOF/非法 JSON）都返回空 dict，让事件按 no-op 处理。
    """
    result: dict = {}

    def _read() -> None:
        try:
            raw = sys.stdin.read()
            if raw and raw.strip():
                parsed = json.loads(raw)
                if isinstance(parsed, dict):
                    result.update(parsed)
        except Exception:
            pass

    reader = threading.Thread(target=_read, daemon=True)
    reader.start()
    reader.join(timeout)
    return result


def _nested_candidates(data: dict) -> list[dict]:
    """部分平台把字段包在 input/properties/event 等内层对象里。"""
    nested = []
    for key in ("input", "properties", "event", "hook_input", "hookInput"):
        value = data.get(key)
        if isinstance(value, dict):
            nested.append(value)
    return nested


def _pick(data: dict, field: str):
    for alias in _FIELD_ALIASES.get(field, (field,)):
        if alias in data and data[alias] not in (None, ""):
            return data[alias]
    for inner in _nested_candidates(data):
        for alias in _FIELD_ALIASES.get(field, (field,)):
            if alias in inner and inner[alias] not in (None, ""):
                return inner[alias]
    return None


def parse_fields(data: dict) -> dict:
    """归一化 hook 输入字段；环境变量作为 cwd/session 的兜底。"""
    cwd = _pick(data, "cwd") or os.environ.get("CODEBUDDY_PROJECT_DIR") or os.getcwd()
    session_id = _pick(data, "session_id") or os.environ.get("CODEBUDDY_SESSION_ID") or ""
    tool_input = _pick(data, "tool_input")
    stop_active = data.get("stop_hook_active", data.get("stopHookActive", False))
    return {
        "session_id": str(session_id) if session_id else "",
        "transcript_path": _pick(data, "transcript_path") or "",
        "hook_event_name": _pick(data, "hook_event_name") or "",
        "cwd": str(cwd),
        "cwd_path": Path(str(cwd)).expanduser(),
        "prompt": str(_pick(data, "prompt") or ""),
        "tool_name": str(_pick(data, "tool_name") or ""),
        "tool_input": tool_input if isinstance(tool_input, dict) else {},
        "tool_response": _pick(data, "tool_response"),
        "reason": str(_pick(data, "reason") or ""),
        "stop_hook_active": bool(stop_active),
        "raw": data,
    }
