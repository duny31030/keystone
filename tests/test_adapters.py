"""Platform adapter configuration and renderer tests."""

from __future__ import annotations

import json

from keystone.adapters.registry import get_adapter, supported_platforms
from keystone.hook.output import render_for_platform


def test_registry_exposes_supported_platforms():
    assert supported_platforms() == ("claude", "codebuddy", "codex")
    assert get_adapter().name == "codebuddy"
    assert get_adapter("claude").settings_relative_path == ".claude/settings.json"
    assert get_adapter("codex").settings_relative_path == ".codex/hooks.json"


def test_codebuddy_default_hooks_are_unchanged():
    adapter = get_adapter("codebuddy")
    hooks = adapter.build_hooks("keystone-hook")
    assert tuple(hooks) == ("SessionStart", "UserPromptSubmit", "PreToolUse", "Stop", "SessionEnd")
    assert [rule["matcher"] for rule in hooks["SessionStart"]] == ["startup", "clear", "compact"]
    assert hooks["PreToolUse"][0]["matcher"]
    assert hooks["PreToolUse"][0]["hooks"][0]["timeout"] == 15


def test_claude_hook_config_is_platform_specific():
    adapter = get_adapter("claude")
    hooks = adapter.build_hooks("keystone-hook")
    assert [rule["matcher"] for rule in hooks["SessionStart"]] == ["startup", "resume", "clear", "compact", "fork"]
    assert hooks["PreToolUse"][0]["matcher"] == "Write|Edit|MultiEdit|NotebookEdit"
    assert [rule["matcher"] for rule in hooks["SessionEnd"]] == ["clear", "resume", "logout", "prompt_input_exit", "other"]
    assert hooks["PreToolUse"][0]["hooks"][0]["command"] == "keystone-hook --platform claude pre-tool-use"


def test_claude_merge_preserves_vendor_and_is_idempotent():
    adapter = get_adapter("claude")
    existing = {
        "env": {"X": "1"},
        "hooks": {
            "Stop": [{"hooks": [{"command": "vendor stop"}]}],
            "Other": [{"matcher": "x", "hooks": [{"command": "vendor other"}]}],
        },
    }
    merged = adapter.merge_settings(existing, "keystone-hook")
    assert merged["env"] == {"X": "1"}
    assert merged["hooks"]["Stop"][0]["hooks"][0]["command"] == "vendor stop"
    assert merged["hooks"]["Other"] == existing["hooks"]["Other"]
    assert adapter.merge_settings(merged, "keystone-hook") == merged


def test_claude_uninstall_keeps_mixed_vendor_rule():
    adapter = get_adapter("claude")
    settings = adapter.merge_settings(None, "keystone-hook")
    settings["hooks"]["Stop"][0]["hooks"].append({"command": "vendor stop"})
    removed = adapter.remove_keystone_settings(settings)
    assert removed["hooks"]["Stop"] == [{"hooks": [{"command": "vendor stop"}]}]
    assert "SessionStart" not in removed["hooks"]


def test_renderer_uses_claude_deny_reason_field():
    payload = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "reason": "planning gate",
        }
    }
    claude = render_for_platform(payload, "claude")
    specific = claude["hookSpecificOutput"]
    assert specific["permissionDecisionReason"] == "planning gate"
    assert "reason" not in specific
    assert render_for_platform(payload, "codebuddy") == payload
