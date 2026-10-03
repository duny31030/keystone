"""Codex context-only adapter and Pi shared-skills tests."""

from __future__ import annotations

import io
import json

from conftest import make_fields  # noqa: F401

from keystone.adapters.registry import get_adapter
from keystone.cli import main as keystone_main
from keystone.hook import cli as hook_cli
from keystone.skills.catalog import selected_targets


def test_codex_adapter_registers_only_prompt_context():
    adapter = get_adapter("codex")
    hooks = adapter.build_hooks("keystone-hook")
    assert hooks == {
        "UserPromptSubmit": [
            {
                "hooks": [
                    {
                        "type": "command",
                        "command": "keystone-hook --platform codex user-prompt-submit",
                        "timeout": 15,
                    }
                ]
            }
        ]
    }
    assert adapter.capabilities.file_tool_deny is False
    assert adapter.capabilities.stop_block == "unsupported"
    assert adapter.capabilities.session_end is False


def test_codex_merge_and_uninstall_preserve_vendor_rules():
    adapter = get_adapter("codex")
    existing = {
        "hooks": {
            "UserPromptSubmit": [
                {"hooks": [{"command": "vendor prompt"}]},
            ],
            "SubagentStart": [{"matcher": "vendor", "hooks": [{"command": "vendor subagent"}]}],
        },
        "other": {"keep": True},
    }
    merged = adapter.merge_settings(existing, "keystone-hook")
    assert merged["hooks"]["UserPromptSubmit"][0]["hooks"][0]["command"] == "vendor prompt"
    assert adapter.merge_settings(merged, "keystone-hook") == merged
    removed = adapter.remove_keystone_settings(merged)
    assert removed == existing


def test_codex_init_only_writes_codex_settings(tmp_path, capsys):
    (tmp_path / "pyproject.toml").write_text("[project]\nname='demo'\n", encoding="utf-8")
    assert keystone_main(["init", "--dir", str(tmp_path), "--platform", "codex", "-y"]) == 0
    assert (tmp_path / ".codex/hooks.json").is_file()
    assert not (tmp_path / ".codebuddy/settings.json").exists()
    assert not (tmp_path / ".claude/settings.json").exists()
    hooks = json.loads((tmp_path / ".codex/hooks.json").read_text(encoding="utf-8"))["hooks"]
    assert set(hooks) == {"UserPromptSubmit"}


def test_codex_doctor_warns_about_manual_prerequisites(project_dir, capsys):
    assert keystone_main(["init", "--dir", str(project_dir), "--platform", "codex", "-y"]) == 0
    capsys.readouterr()
    assert keystone_main(["doctor", "--dir", str(project_dir), "--platform", "codex"]) == 0
    output = capsys.readouterr().out
    assert "hooks = true" in output
    assert "trusted" in output
    assert "/hooks" in output
    assert "不提供 file-tool deny" in output


def test_codex_uninstall_does_not_touch_other_platforms(tmp_path, capsys):
    (tmp_path / "pyproject.toml").write_text("[project]\nname='demo'\n", encoding="utf-8")
    assert keystone_main(["init", "--dir", str(tmp_path), "--platform", "codebuddy", "-y"]) == 0
    assert keystone_main(["init", "--dir", str(tmp_path), "--platform", "codex", "-y"]) == 0
    codebuddy_before = (tmp_path / ".codebuddy/settings.json").read_text(encoding="utf-8")
    assert keystone_main(["uninstall", "--dir", str(tmp_path), "--platform", "codex"]) == 0
    assert (tmp_path / ".codebuddy/settings.json").read_text(encoding="utf-8") == codebuddy_before
    assert json.loads((tmp_path / ".codex/hooks.json").read_text(encoding="utf-8"))["hooks"] == {}


def test_codex_and_pi_auto_skills_use_shared_agents_target(tmp_path):
    (tmp_path / ".codex").mkdir()
    assert selected_targets(tmp_path, "auto") == ("agents",)
    (tmp_path / ".codex").rmdir()
    (tmp_path / ".pi").mkdir()
    assert selected_targets(tmp_path, "auto") == ("agents",)
    assert selected_targets(tmp_path, "codex") == ("agents",)
    assert selected_targets(tmp_path, "pi") == ("agents",)


def test_codex_runner_injects_prompt_context(project_dir, monkeypatch, capsys):
    from keystone.store import sessions, tasks
    from keystone.store.layout import KeystoneLayout

    layout = KeystoneLayout(project_dir)
    tasks.create_task(layout, "codex context")
    monkeypatch.setattr(
        "sys.stdin",
        io.StringIO(json.dumps({"cwd": str(project_dir), "session_id": "s1", "prompt": "TASK-001 说明当前阶段"})),
    )
    assert hook_cli.main(["--platform", "codex", "user-prompt-submit"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["hookSpecificOutput"]["hookEventName"] == "UserPromptSubmit"
    assert "TASK-001" in out["hookSpecificOutput"]["additionalContext"]
    assert sessions.get_binding(layout, "s1") == "TASK-001"


def test_codex_runner_rejects_unregistered_events(project_dir, capsys):
    assert hook_cli.main(["--platform", "codex", "pre-tool-use"]) == 1
    assert hook_cli.main(["--platform", "codex", "session-start"]) == 1
    assert hook_cli.main(["--platform", "codex", "stop"]) == 1
    assert "不支持事件" in capsys.readouterr().err


def test_codex_doctor_fix_does_not_write_user_level_config(project_dir, capsys, monkeypatch):
    home = project_dir / "fake-home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    assert keystone_main(["init", "--dir", str(project_dir), "--platform", "codex", "-y"]) == 0
    assert keystone_main(["doctor", "--dir", str(project_dir), "--platform", "codex", "--fix"]) == 0
    assert list(home.iterdir()) == []
    assert not (project_dir / ".codex/config.toml").exists()


def test_codex_init_reports_manual_prerequisites(tmp_path, capsys):
    (tmp_path / "pyproject.toml").write_text("[project]\nname='demo'\n", encoding="utf-8")
    assert keystone_main(["init", "--dir", str(tmp_path), "--platform", "codex", "-y"]) == 0
    output = capsys.readouterr().out
    assert "Codex" in output
    assert "hooks = true" in output
