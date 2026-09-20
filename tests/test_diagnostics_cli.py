"""本地诊断与生命周期 CLI 测试。"""

from __future__ import annotations

import json

from keystone.cli import main as keystone_main
from keystone.store import tasks
from keystone.store.layout import KeystoneLayout


def test_init_dry_run_makes_no_changes(tmp_path, capsys):
    (tmp_path / "pom.xml").write_text("<project/>", encoding="utf-8")
    assert keystone_main(["init", "--dir", str(tmp_path), "-y", "--dry-run"]) == 0
    output = capsys.readouterr().out
    assert "CREATE" in output and "不会写入文件" in output
    assert not (tmp_path / ".keystone").exists()
    assert not (tmp_path / ".codebuddy").exists()
    assert not (tmp_path / ".gitignore").exists()


def test_status_summarizes_initialized_project(project_dir, monkeypatch, capsys):
    monkeypatch.chdir(project_dir)
    layout = KeystoneLayout(project_dir)
    tasks.create_task(layout, "pending", pending_confirmation=True)
    task = tasks.create_task(layout, "done")
    for target in ("PLANNING", "PLAN_CONFIRMED", "IMPLEMENTING", "VERIFYING", "COMPLETED"):
        tasks.transition_task(layout, task["code"], target)
    assert keystone_main(["status", "--dir", str(project_dir)]) == 0
    output = capsys.readouterr().out
    assert "Project: demo" in output
    assert "2 total" in output
    assert "1 completed" in output
    assert "1 pending confirmation" in output
    assert "Hooks: 5/5" in output


def test_status_uninitialized_returns_1(tmp_path, capsys):
    assert keystone_main(["status", "--dir", str(tmp_path)]) == 1
    assert "keystone init" in capsys.readouterr().err


def test_status_fails_for_invalid_settings(project_dir, capsys):
    (project_dir / ".codebuddy/settings.json").write_text("{bad", encoding="utf-8")
    assert keystone_main(["status", "--dir", str(project_dir)]) == 1
    assert "keystone doctor" in capsys.readouterr().err


def test_doctor_clean_project_passes(project_dir, capsys):
    assert keystone_main(["doctor", "--dir", str(project_dir)]) == 0
    output = capsys.readouterr().out
    assert "PASS project" in output
    assert "5 Keystone registrations" not in output
    assert "已实际触发" not in output
    assert "0 fail" in output


def test_doctor_warns_missing_ignore_and_enforce(project_dir, capsys):
    project = project_dir / ".keystone/project.json"
    data = json.loads(project.read_text(encoding="utf-8"))
    data["stop_mode"] = "enforce"
    project.write_text(json.dumps(data), encoding="utf-8")
    (project_dir / ".gitignore").write_text("", encoding="utf-8")
    assert keystone_main(["doctor", "--dir", str(project_dir)]) == 0
    output = capsys.readouterr().out
    assert "WARN stop_mode" in output
    assert "尚未实机验证" in output
    assert "WARN gitignore" in output


def test_doctor_fails_for_invalid_settings(project_dir, capsys):
    settings = project_dir / ".codebuddy/settings.json"
    settings.write_text("{bad", encoding="utf-8")
    assert keystone_main(["doctor", "--dir", str(project_dir)]) == 1
    assert "FAIL settings" in capsys.readouterr().out


def test_uninstall_default_preserves_project_gitignore_and_third_party_hook(project_dir, capsys):
    settings = project_dir / ".codebuddy/settings.json"
    data = json.loads(settings.read_text(encoding="utf-8"))
    data["hooks"]["Stop"][0]["hooks"].append({"command": "vendor-hook keep"})
    settings.write_text(json.dumps(data), encoding="utf-8")
    assert keystone_main(["uninstall", "--dir", str(project_dir)]) == 0
    after = json.loads(settings.read_text(encoding="utf-8"))
    assert after["hooks"]["Stop"] == [{"hooks": [{"command": "vendor-hook keep"}]}]
    assert (project_dir / ".keystone/project.json").is_file()
    assert ".keystone/.state/" in (project_dir / ".gitignore").read_text(encoding="utf-8")


def test_uninstall_dry_run_writes_nothing(project_dir, capsys):
    settings = project_dir / ".codebuddy/settings.json"
    before = settings.read_text(encoding="utf-8")
    assert keystone_main(["uninstall", "--dir", str(project_dir), "--dry-run", "--purge"]) == 0
    assert "REMOVE" in capsys.readouterr().out
    assert settings.read_text(encoding="utf-8") == before
    assert (project_dir / ".keystone/project.json").is_file()


def test_uninstall_purge_requires_yes_noninteractive(project_dir, capsys, monkeypatch):
    monkeypatch.setattr("sys.stdin.isatty", lambda: False)
    assert keystone_main(["uninstall", "--dir", str(project_dir), "--purge"]) == 1
    assert (project_dir / ".keystone").is_dir()
    assert "--yes" in capsys.readouterr().err


def test_uninstall_purge_yes_removes_managed_content(project_dir, capsys):
    assert keystone_main(["uninstall", "--dir", str(project_dir), "--purge", "--yes"]) == 0
    assert not (project_dir / ".keystone").exists()
    assert ".keystone/.state/" not in (project_dir / ".gitignore").read_text(encoding="utf-8")
    assert (project_dir / ".codebuddy/settings.json").is_file()
