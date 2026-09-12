"""keystone init / task CLI 测试 + settings.json 合并幂等验证。"""

from __future__ import annotations

import json

import pytest

from keystone import scaffold
from keystone.cli import main as keystone_main


def test_init_creates_everything(tmp_path, capsys):
    code = keystone_main(["init", "--dir", str(tmp_path), "--lang", "python",
                          "--name", "order-service", "-y"])
    assert code == 0
    layout = tmp_path / ".keystone"
    assert (layout / "project.json").is_file()
    assert (layout / "specs" / "coding.md").is_file()
    assert (layout / "tasks").is_dir()
    assert (tmp_path / ".codebuddy" / "settings.json").is_file()
    gitignore = (tmp_path / ".gitignore").read_text(encoding="utf-8")
    assert ".keystone/.state/" in gitignore
    project = json.loads((layout / "project.json").read_text(encoding="utf-8"))
    assert project["test_command"] == "pytest"
    assert project["name"] == "order-service"


def test_init_detects_language_from_markers(tmp_path, capsys):
    (tmp_path / "pom.xml").write_text("<project/>", encoding="utf-8")
    code = keystone_main(["init", "--dir", str(tmp_path), "-y"])
    assert code == 0
    project = json.loads((tmp_path / ".keystone" / "project.json").read_text(encoding="utf-8"))
    assert project["language"] == "java"
    assert project["test_command"] == "mvn test"


def test_init_settings_merge_preserves_foreign_hooks(tmp_path, capsys):
    settings = tmp_path / ".codebuddy" / "settings.json"
    settings.parent.mkdir()
    foreign = {
        "hooks": {
            "UserPromptSubmit": [
                {"hooks": [{"type": "command", "command": "python3 .trellis/hooks/x.py",
                            "timeout": 15}]}
            ]
        }
    }
    settings.write_text(json.dumps(foreign), encoding="utf-8")

    assert keystone_main(["init", "--dir", str(tmp_path), "--lang", "python", "-y"]) == 0
    merged = json.loads(settings.read_text(encoding="utf-8"))
    ups_rules = merged["hooks"]["UserPromptSubmit"]
    assert any("trellis" in h["command"]
               for r in ups_rules for h in r.get("hooks", []))
    assert any("keystone" in h["command"]
               for r in ups_rules for h in r.get("hooks", []))


def test_init_idempotent_no_duplicate_hooks(tmp_path, capsys):
    assert keystone_main(["init", "--dir", str(tmp_path), "--lang", "python", "-y"]) == 0
    before = json.loads((tmp_path / ".codebuddy" / "settings.json").read_text(encoding="utf-8"))
    # 重跑 init 不覆盖 project.json，也不产生重复 hook 条目
    assert keystone_main(["init", "--dir", str(tmp_path), "--lang", "python", "-y"]) == 0
    after = json.loads((tmp_path / ".codebuddy" / "settings.json").read_text(encoding="utf-8"))
    assert before == after
    gitignore = (tmp_path / ".gitignore").read_text(encoding="utf-8")
    assert gitignore.count(".keystone/.state/") == 1


def test_merge_settings_unit():
    existing = {"hooks": {"Stop": [{"hooks": [{"command": "other-tool stop"}]}]}}
    merged = scaffold.merge_settings(existing, "keystone-hook")
    assert merged["hooks"]["Stop"][0]["hooks"][0]["command"] == "other-tool stop"
    assert "keystone-hook stop" in merged["hooks"]["Stop"][1]["hooks"][0]["command"]
    # SessionStart 三 matcher
    assert [r["matcher"] for r in merged["hooks"]["SessionStart"]] == ["startup", "clear", "compact"]


def _run_task(argv, capsys):
    code = keystone_main(argv)
    return code, capsys.readouterr().out


def test_task_lifecycle_cli(project_dir, capsys, monkeypatch):
    monkeypatch.chdir(project_dir)  # task 子命令从 cwd 向上找 .keystone/
    code, out = _run_task(["task", "create", "实现登录", "-d", "手机号登录",
                           "-a", "接口通;测试过"], capsys)
    assert code == 0
    assert "TASK-001" in out

    code, out = _run_task(["task", "list"], capsys)
    assert "TASK-001" in out and "实现登录" in out

    code, out = _run_task(["task", "show", "TASK-001"], capsys)
    assert "手机号登录" in out and "接口通" in out

    code, out = _run_task(["task", "advance", "TASK-001"], capsys)  # TODO → PLANNING
    assert "PLANNING" in out
    code, out = _run_task(["task", "advance", "TASK-001"], capsys)  # → PLAN_CONFIRMED
    assert "PLAN_CONFIRMED" in out
    code, out = _run_task(["task", "advance", "TASK-001"], capsys)  # → IMPLEMENTING
    assert "IMPLEMENTING" in out
    code, out = _run_task(["task", "advance", "TASK-001"], capsys)  # → VERIFYING
    assert "VERIFYING" in out
    code, out = _run_task(["task", "complete", "TASK-001"], capsys)
    assert "COMPLETED" in out

    code, out = _run_task(["task", "reopen", "TASK-001"], capsys)
    assert "IMPLEMENTING" in out


def test_task_illegal_transition_exits_1(project_dir, capsys, monkeypatch):
    monkeypatch.chdir(project_dir)
    code, _ = _run_task(["task", "create", "A"], capsys)
    assert code == 0
    code, out = _run_task(["task", "advance", "TASK-001", "--to", "COMPLETED"], capsys)
    assert code == 1


def test_task_outside_project_fails(tmp_path, capsys, monkeypatch):
    monkeypatch.chdir(tmp_path)
    with pytest.raises(SystemExit) as exc:
        keystone_main(["task", "list"])
    assert exc.value.code == 1
