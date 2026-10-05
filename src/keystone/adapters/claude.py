"""Claude Code platform adapter. All registered hooks verified in headless (claude -p) sessions 2026-10-05."""

from __future__ import annotations

from keystone.adapters.base import JsonHookAdapter, PlatformCapabilities

CLAUDE_FILE_TOOL_MATCHER = "Write|Edit|MultiEdit|NotebookEdit"


class ClaudeAdapter(JsonHookAdapter):
    name = "claude"
    display_name = "Claude Code"
    settings_relative_path = ".claude/settings.json"
    expected_events = ("SessionStart", "UserPromptSubmit", "PreToolUse", "Stop", "SessionEnd")
    retired_events: tuple[str, ...] = ()
    capabilities = PlatformCapabilities(True, True, "verified", True)

    def build_hooks(self, runner_command: str) -> dict:
        def rule(event: str) -> dict:
            return {
                "type": "command",
                "command": f"{runner_command} --platform claude {event}",
                "timeout": 15,
            }

        return {
            "SessionStart": [
                {"matcher": matcher, "hooks": [rule("session-start")]}
                for matcher in ("startup", "resume", "clear", "compact", "fork")
            ],
            "UserPromptSubmit": [{"hooks": [rule("user-prompt-submit")]}],
            "PreToolUse": [{"matcher": CLAUDE_FILE_TOOL_MATCHER, "hooks": [rule("pre-tool-use")]}],
            "Stop": [{"hooks": [rule("stop")]}],
            "SessionEnd": [
                {"matcher": matcher, "hooks": [rule("session-end")]}
                for matcher in ("clear", "resume", "logout", "prompt_input_exit", "other")
            ],
        }

    def render_deny(self, reason: str) -> dict:
        return {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": reason,
            }
        }

    def environment_defaults(self) -> dict[str, str]:
        return {"cwd": "CLAUDE_PROJECT_DIR", "session_id": "CLAUDE_SESSION_ID"}

    def expected_registration_count(self, event: str) -> int:
        return 5 if event in {"SessionStart", "SessionEnd"} else 1

    def capability_warnings(self) -> tuple[str, ...]:
        return (
            "Claude Hook 已在 headless（claude -p）真实会话验证：context、file-tool deny、Stop enforce、SessionEnd 均生效",
            "交互式 TUI 模式尚未覆盖验证；仅拦截原生文件工具，不承诺 Bash/MCP 写入保护",
        )
