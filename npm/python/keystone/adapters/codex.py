"""Codex context-only platform adapter.

Codex write-deny, Stop and SessionEnd hooks are intentionally unsupported here.
They require separate host-level verification before Keystone can make policy claims.
"""

from __future__ import annotations

from keystone.adapters.base import JsonHookAdapter, PlatformCapabilities


class CodexAdapter(JsonHookAdapter):
    name = "codex"
    display_name = "Codex"
    settings_relative_path = ".codex/hooks.json"
    expected_events = ("UserPromptSubmit",)
    retired_events: tuple[str, ...] = ()
    capabilities = PlatformCapabilities(True, False, "unsupported", False)

    def build_hooks(self, runner_command: str) -> dict:
        return {
            "UserPromptSubmit": [
                {
                    "hooks": [
                        {
                            "type": "command",
                            "command": f"{runner_command} --platform codex user-prompt-submit",
                            "timeout": 15,
                        }
                    ]
                }
            ]
        }

    def render_deny(self, reason: str) -> dict:
        raise RuntimeError("Codex context-only adapter does not support tool denial")

    def capability_warnings(self) -> tuple[str, ...]:
        return (
            "Codex MVP 仅提供 UserPromptSubmit context；不提供 file-tool deny、strict gate、Stop 或 SessionEnd",
            "需在用户级 config 启用 [features] hooks = true（旧版可用 codex_hooks = true）",
            "需将项目设为 trusted，并在 interactive Codex 中运行 /hooks 审批 Keystone command",
            "这些用户级前置条件不会由 Keystone 读取或修改",
        )
