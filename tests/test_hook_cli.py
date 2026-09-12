"""keystone-hook 分发器协议测试（stdin → stdout/退出码）。"""

from __future__ import annotations

import io
import json

import pytest
from conftest import make_fields  # noqa: F401

from keystone.hook import cli as hook_cli


def run_hook(project_dir, event, payload: dict, monkeypatch, capsys):
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(payload)))
    code = hook_cli.main([event])
    out = capsys.readouterr().out.strip()
    return code, (json.loads(out) if out else None)


def test_session_start_pipeline(project_dir, monkeypatch, capsys):
    code, out = run_hook(project_dir, "session-start",
                         {"cwd": str(project_dir), "session_id": "s1"}, monkeypatch, capsys)
    assert code == 0
    assert out["hookSpecificOutput"]["hookEventName"] == "SessionStart"
    assert "pytest" in out["hookSpecificOutput"]["additionalContext"]


def test_pascal_case_event_accepted(project_dir, monkeypatch, capsys):
    code, out = run_hook(project_dir, "SessionStart",
                         {"cwd": str(project_dir)}, monkeypatch, capsys)
    assert code == 0 and out is not None


def test_not_a_keystone_project_is_noop(tmp_path, monkeypatch, capsys):
    code, out = run_hook(tmp_path, "session-start", {"cwd": str(tmp_path)}, monkeypatch, capsys)
    assert code == 0 and out is None


def test_malformed_stdin_fails_open(project_dir, monkeypatch, capsys):
    monkeypatch.setattr("sys.stdin", io.StringIO("not-json{"))
    assert hook_cli.main(["session-start"]) == 0
    assert capsys.readouterr().out.strip() == ""


def test_empty_stdin_fails_open(project_dir, monkeypatch, capsys):
    monkeypatch.setattr("sys.stdin", io.StringIO(""))
    code = hook_cli.main(["user-prompt-submit"])
    assert code == 0
    assert capsys.readouterr().out.strip() == ""


def test_unknown_event_exits_nonzero(project_dir, capsys):
    assert hook_cli.main(["no-such-event"]) == 1
    assert hook_cli.main([]) == 1


def test_corrupt_project_json_fails_open(project_dir, monkeypatch, capsys):
    from keystone.store.layout import KeystoneLayout
    (KeystoneLayout(project_dir).project_json).write_text("{corrupt", encoding="utf-8")
    code, out = run_hook(project_dir, "session-start",
                         {"cwd": str(project_dir)}, monkeypatch, capsys)
    assert code == 0 and out is None


def test_pre_tool_use_deny_pipeline(project_dir, monkeypatch, capsys):
    # 走完整管道：prompt 建任务 → 推进到 PLANNING → 写文件被拒
    from keystone.store import sessions, tasks
    from keystone.store.layout import KeystoneLayout
    layout = KeystoneLayout(project_dir)
    run_hook(project_dir, "user-prompt-submit",
             {"cwd": str(project_dir), "session_id": "s1", "prompt": "做个功能"},
             monkeypatch, capsys)
    tasks.transition_task(layout, "TASK-001", "PLANNING")
    code, out = run_hook(project_dir, "pre-tool-use",
                         {"cwd": str(project_dir), "session_id": "s1",
                          "tool_name": "Write", "tool_input": {"file_path": "/x.py"}},
                         monkeypatch, capsys)
    assert code == 0
    assert out["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert sessions.get_binding(layout, "s1") == "TASK-001"
