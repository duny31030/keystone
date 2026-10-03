"""Shared JSON command-hook adapter helpers."""

from __future__ import annotations

import json
import shlex
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True)
class PlatformCapabilities:
    context_injection: bool
    file_tool_deny: bool
    stop_block: str  # verified | experimental | unsupported
    session_end: bool


class PlatformAdapter(Protocol):
    name: str
    display_name: str
    settings_relative_path: str
    expected_events: tuple[str, ...]
    retired_events: tuple[str, ...]
    capabilities: PlatformCapabilities

    def expected_registration_count(self, event: str) -> int: ...
    def capability_warnings(self) -> tuple[str, ...]: ...
    def build_hooks(self, runner_command: str) -> dict: ...
    def merge_settings(self, existing: dict | None, runner_command: str) -> dict: ...
    def remove_keystone_settings(self, existing: dict) -> dict: ...
    def registered_commands(self, settings: dict) -> dict[str, list[str]]: ...
    def render_deny(self, reason: str) -> dict: ...
    def environment_defaults(self) -> dict[str, str]: ...


def is_keystone_command(command: str) -> bool:
    try:
        tokens = shlex.split(command)
    except ValueError:
        return False
    return bool(tokens) and (
        tokens[0] == "keystone-hook"
        or (len(tokens) >= 3 and tokens[:3] == ["python3", "-m", "keystone.hook"])
    )


def is_keystone_hook(hook: object) -> bool:
    return isinstance(hook, dict) and is_keystone_command(str(hook.get("command", "")))


def without_keystone_hooks(rule: object) -> dict | None:
    if not isinstance(rule, dict):
        return rule
    command_hooks = rule.get("hooks")
    if not isinstance(command_hooks, list):
        return rule
    kept = [hook for hook in command_hooks if not is_keystone_hook(hook)]
    if not kept:
        return None
    result = dict(rule)
    result["hooks"] = kept
    return result


def remove_keystone_hooks(rules: object) -> list:
    if not isinstance(rules, list):
        return []
    return [result for rule in rules if (result := without_keystone_hooks(rule)) is not None]


class JsonHookAdapter:
    """Base for platforms with hooks -> event -> command-rule JSON settings."""

    settings_relative_path: str
    expected_events: tuple[str, ...]
    retired_events: tuple[str, ...]

    def merge_settings(self, existing: dict | None, runner_command: str) -> dict:
        merged = json.loads(json.dumps(existing)) if existing else {}
        hooks = merged.setdefault("hooks", {})
        if not isinstance(hooks, dict):
            raise ValueError(f"{self.settings_relative_path} 的 hooks 必须是 JSON object")
        for event in self.retired_events:
            if event in hooks:
                kept = remove_keystone_hooks(hooks[event])
                if kept:
                    hooks[event] = kept
                else:
                    del hooks[event]
        for event, rules in self.build_hooks(runner_command).items():
            hooks[event] = remove_keystone_hooks(hooks.get(event, [])) + rules
        return merged

    def remove_keystone_settings(self, existing: dict) -> dict:
        merged = json.loads(json.dumps(existing))
        hooks = merged.get("hooks")
        if hooks is None:
            return merged
        if not isinstance(hooks, dict):
            raise ValueError(f"{self.settings_relative_path} 的 hooks 必须是 JSON object")
        for event in list(hooks):
            kept = remove_keystone_hooks(hooks[event])
            if kept:
                hooks[event] = kept
            else:
                del hooks[event]
        return merged

    def registered_commands(self, settings: dict) -> dict[str, list[str]]:
        result: dict[str, list[str]] = {}
        hooks = settings.get("hooks", {})
        if not isinstance(hooks, dict):
            return result
        for event, rules in hooks.items():
            if not isinstance(rules, list):
                continue
            for rule in rules:
                if not isinstance(rule, dict):
                    continue
                for hook in rule.get("hooks", []):
                    if is_keystone_hook(hook):
                        result.setdefault(str(event), []).append(str(hook.get("command", "")))
        return result

    def environment_defaults(self) -> dict[str, str]:
        return {}

    def expected_registration_count(self, event: str) -> int:
        return 3 if event == "SessionStart" else 1

    def capability_warnings(self) -> tuple[str, ...]:
        return ()
