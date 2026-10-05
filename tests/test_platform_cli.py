"""Platform-specific init, dry-run, doctor and uninstall CLI tests."""

from __future__ import annotations

import json

from keystone.cli import main as keystone_main


def test_claude_init_writes_only_claude_settings(tmp_path, capsys):
    (tmp_path / "pyproject.toml").write_text("[project]\nname='demo'\n", encoding="utf-8")
    assert keystone_main(["init", "--dir", str(tmp_path), "--platform", "claude", "-y"]) == 0
    assert (tmp_path / ".claude/settings.json").is_file()
    assert not (tmp_path / ".codebuddy/settings.json").exists()


def test_claude_init_dry_run_writes_nothing(tmp_path, capsys):
    (tmp_path / "pyproject.toml").write_text("[project]\nname='demo'\n", encoding="utf-8")
    assert keystone_main(["init", "--dir", str(tmp_path), "--platform", "claude", "-y", "--dry-run"]) == 0
    output = capsys.readouterr().out
    assert ".claude/settings.json" in output
    assert not (tmp_path / ".keystone").exists()
    assert not (tmp_path / ".claude").exists()


def test_claude_doctor_reports_verified_headless_capability(project_dir, capsys):
    assert keystone_main(["init", "--dir", str(project_dir), "--platform", "claude", "-y"]) == 0
    capsys.readouterr()
    assert keystone_main(["doctor", "--dir", str(project_dir), "--platform", "claude"]) == 0
    output = capsys.readouterr().out
    assert ".claude/settings.json" not in output
    assert "headless" in output
    assert "不承诺 Bash/MCP 写入保护" in output


def test_claude_doctor_fix_does_not_touch_codebuddy(project_dir, capsys):
    codebuddy = project_dir / ".codebuddy/settings.json"
    before = codebuddy.read_text(encoding="utf-8")
    assert keystone_main(["doctor", "--dir", str(project_dir), "--platform", "claude", "--fix"]) == 0
    assert (project_dir / ".claude/settings.json").is_file()
    assert codebuddy.read_text(encoding="utf-8") == before


def test_claude_uninstall_only_removes_claude_entries(tmp_path, capsys):
    (tmp_path / "pyproject.toml").write_text("[project]\nname='demo'\n", encoding="utf-8")
    assert keystone_main(["init", "--dir", str(tmp_path), "--platform", "codebuddy", "-y"]) == 0
    assert keystone_main(["init", "--dir", str(tmp_path), "--platform", "claude", "-y"]) == 0
    codebuddy_before = (tmp_path / ".codebuddy/settings.json").read_text(encoding="utf-8")
    assert keystone_main(["uninstall", "--dir", str(tmp_path), "--platform", "claude"]) == 0
    assert (tmp_path / ".codebuddy/settings.json").read_text(encoding="utf-8") == codebuddy_before
    claude = json.loads((tmp_path / ".claude/settings.json").read_text(encoding="utf-8"))
    assert claude["hooks"] == {}
