"""从用户 prompt 中识别任务编号。

支持的写法：`TASK-123` / `task 123` / `TASK_123`（大小写不敏感），以及 `#123`。
返回按出现位置排序的规范任务编号（TASK-001 三位补零），供 UserPromptSubmit 切换任务。
"""

from __future__ import annotations

import re

_TASK_WORD_RE = re.compile(r"\btask[-_ ]?(\d{1,6})\b", re.IGNORECASE)
_HASH_RE = re.compile(r"(?<![\w])#(\d{1,6})\b")


def format_task_code(number: int) -> str:
    return f"TASK-{number:03d}"


def extract_task_codes(prompt: str) -> list[str]:
    """按出现先后返回 prompt 中提到的任务编号（去重、规范化）。"""
    if not prompt:
        return []
    hits: list[tuple[int, str]] = []
    for m in _TASK_WORD_RE.finditer(prompt):
        hits.append((m.start(), format_task_code(int(m.group(1)))))
    for m in _HASH_RE.finditer(prompt):
        hits.append((m.start(), format_task_code(int(m.group(1)))))
    hits.sort(key=lambda pair: pair[0])
    seen: set[str] = set()
    ordered: list[str] = []
    for _, code in hits:
        if code not in seen:
            seen.add(code)
            ordered.append(code)
    return ordered
