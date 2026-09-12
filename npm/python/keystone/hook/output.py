"""HookOutput 构造与输出。

依据调研确认的 CodeBuddy 契约：
- 注入上下文：{"hookSpecificOutput": {"hookEventName": ..., "additionalContext": ...}}
- PreToolUse 控制决策：hookSpecificOutput.permissionDecision = allow|ask|deny (+ reason)
- Stop 强制阻止：{"decision": "block", "reason": ...}
- 无输出 + exit 0 是合法 no-op；CodeBuddy 对多余字段宽容解析。
"""

from __future__ import annotations

import json
import os
import sys


def additional_context(event_name: str, context: str) -> dict:
    return {
        "hookSpecificOutput": {
            "hookEventName": event_name,
            "additionalContext": context,
        }
    }


def deny_pre_tool_use(reason: str) -> dict:
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "reason": reason,
        }
    }


def block_stop(reason: str) -> dict:
    return {"decision": "block", "reason": reason}


def emit(output: dict) -> None:
    print(json.dumps(output, ensure_ascii=False), flush=True)


def debug(message: str) -> None:
    """调试输出走 stderr，仅在 KEYSTONE_DEBUG=1 时打印，不污染协议 stdout。"""
    if os.environ.get("KEYSTONE_DEBUG") == "1":
        print(f"[keystone] {message}", file=sys.stderr)
