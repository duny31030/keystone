"""CodeBuddy platform adapter. Behavior matches the pre-adapter implementation."""

from __future__ import annotations

from keystone.adapters.base import JsonHookAdapter, PlatformCapabilities

TOOL_MATCHER = (
    "Write|Edit|MultiEdit|NotebookEdit|write_to_file|replace_in_file|apply_patch|"
    "str_replace_editor|str_replace_based_edit_tool|create_file|edit_file|save_file|"
    "Bash|execute_command|run_command|run_terminal_cmd|terminal|shell"
)


class CodeBuddyAdapter(JsonHookAdapter):
    name = "codebuddy"
    display_name = "CodeBuddy"
    settings_relative_path = ".codebuddy/settings.json"
    expected_events = ("SessionStart", "UserPromptSubmit", "PreToolUse", "Stop", "SessionEnd")
    retired_events = ("PostToolUse", "PreCompact")
    capabilities = PlatformCapabilities(True, True, "experimental", True)

    def build_hooks(self, runner_command: str) -> dict:
        def rule(event: str) -> dict:
            return {"type": "command", "command": f"{runner_command} {event}", "timeout": 15}

        return {
            "SessionStart": [
                {"matcher": matcher, "hooks": [rule("session-start")]}
                for matcher in ("startup", "clear", "compact")
            ],
            "UserPromptSubmit": [{"hooks": [rule("user-prompt-submit")]}],
            "PreToolUse": [{"matcher": TOOL_MATCHER, "hooks": [rule("pre-tool-use")]}],
            "Stop": [{"hooks": [rule("stop")]}],
            "SessionEnd": [{"hooks": [rule("session-end")]}],
        }

    def render_deny(self, reason: str) -> dict:
        return {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "reason": reason,
            }
        }

    def environment_defaults(self) -> dict[str, str]:
        return {"cwd": "CODEBUDDY_PROJECT_DIR", "session_id": "CODEBUDDY_SESSION_ID"}
