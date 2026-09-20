"""doctor --fix 自动修复测试。"""

from __future__ import annotations

import json

from keystone.cli import main as keystone_main


def test_doctor_fix_repairs_missing_hooks(project_dir, capsys):
    settings = project_dir / ".codebuddy/settings.json"
    settings.write_text(json.dumps({"hooks": {}}), encoding="utf-8")
    assert keystone_main(["doctor", "--dir", str(project_dir), "--fix"]) == 0
    output = capsys.readouterr().out
    assert "已修复" in output
    assert "更新 settings.json" in output
    assert "修复后重新检查" in output
    assert "0 fail" in output
    after = json.loads(settings.read_text(encoding="utf-8"))
    assert "SessionStart" in after["hooks"]
    assert "UserPromptSubmit" in after["hooks"]
    assert "PreToolUse" in after["hooks"]
    assert "Stop" in after["hooks"]
    assert "SessionEnd" in after["hooks"]


def test_doctor_fix_removes_retired_hooks(project_dir, capsys):
    settings = project_dir / ".codebuddy/settings.json"
    data = json.loads(settings.read_text(encoding="utf-8"))
    data["hooks"]["PostToolUse"] = [{"hooks": [{"command": "keystone-hook post-tool-use"}]}]
    data["hooks"]["PreCompact"] = [{"hooks": [{"command": "keystone-hook pre-compact"}]}]
    settings.write_text(json.dumps(data), encoding="utf-8")
    assert keystone_main(["doctor", "--dir", str(project_dir), "--fix"]) == 0
    after = json.loads(settings.read_text(encoding="utf-8"))
    assert "PostToolUse" not in after["hooks"]
    assert "PreCompact" not in after["hooks"]


def test_doctor_fix_preserves_third_party_hooks(project_dir, capsys):
    settings = project_dir / ".codebuddy/settings.json"
    data = json.loads(settings.read_text(encoding="utf-8"))
    data["hooks"]["Stop"][0]["hooks"].append({"command": "vendor-hook keep"})
    settings.write_text(json.dumps(data), encoding="utf-8")
    keystone_main(["doctor", "--dir", str(project_dir), "--fix"])
    after = json.loads(settings.read_text(encoding="utf-8"))
    assert any("vendor-hook keep" in h["command"] for h in after["hooks"]["Stop"][0]["hooks"])


def test_doctor_fix_creates_missing_gitignore(project_dir, capsys):
    gitignore = project_dir / ".gitignore"
    gitignore.unlink()
    assert keystone_main(["doctor", "--dir", str(project_dir), "--fix"]) == 0
    output = capsys.readouterr().out
    assert "创建 .gitignore" in output
    assert ".keystone/.state/" in gitignore.read_text(encoding="utf-8")


def test_doctor_fix_creates_missing_directories(project_dir, capsys):
    import shutil
    shutil.rmtree(project_dir / ".keystone/tasks")
    shutil.rmtree(project_dir / ".keystone/.state")
    assert keystone_main(["doctor", "--dir", str(project_dir), "--fix"]) == 0
    output = capsys.readouterr().out
    assert "创建目录" in output
    assert (project_dir / ".keystone/tasks").is_dir()
    assert (project_dir / ".keystone/.state").is_dir()


def test_doctor_fix_generates_missing_spec_templates(project_dir, capsys):
    import shutil
    shutil.rmtree(project_dir / ".keystone/specs")
    assert keystone_main(["doctor", "--dir", str(project_dir), "--fix"]) == 0
    output = capsys.readouterr().out
    assert "生成规范模板" in output
    assert (project_dir / ".keystone/specs/architecture.md").is_file()
    assert (project_dir / ".keystone/specs/coding.md").is_file()
    assert (project_dir / ".keystone/specs/general-ban.md").is_file()


def test_doctor_fix_does_not_repair_corrupt_json(project_dir, capsys):
    settings = project_dir / ".codebuddy/settings.json"
    settings.write_text("{corrupt", encoding="utf-8")
    assert keystone_main(["doctor", "--dir", str(project_dir), "--fix"]) == 1
    output = capsys.readouterr().out
    assert "FAIL settings" in output
    assert "{corrupt" in settings.read_text(encoding="utf-8")


def test_doctor_fix_clean_project_no_changes(project_dir, capsys):
    assert keystone_main(["doctor", "--dir", str(project_dir), "--fix"]) == 0
    output = capsys.readouterr().out
    assert "无可修复的问题" in output or "0 fail" in output
