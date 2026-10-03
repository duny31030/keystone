"""Claude/CodeBuddy JSON HookOutput 构造与输出。"""

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


def render_for_platform(payload: dict, platform: str) -> dict:
    """Translate only fields where CodeBuddy and Claude differ."""
    if platform != "claude":
        return payload
    output = json.loads(json.dumps(payload))
    specific = output.get("hookSpecificOutput")
    if isinstance(specific, dict) and specific.get("permissionDecision") == "deny":
        if "reason" in specific:
            specific["permissionDecisionReason"] = specific.pop("reason")
    return output


def emit(output: dict) -> None:
    print(json.dumps(output, ensure_ascii=False), flush=True)


def debug(message: str) -> None:
    """调试输出走 stderr，仅在 KEYSTONE_DEBUG=1 时打印，不污染协议 stdout。"""
    if os.environ.get("KEYSTONE_DEBUG") == "1":
        print(f"[keystone] {message}", file=sys.stderr)
