"""keystone events list 命令测试。"""

from __future__ import annotations

import json

from keystone.cli import main as keystone_main
from keystone.store import sessions
from keystone.store.layout import KeystoneLayout


def _write_events(layout: KeystoneLayout, events: list[dict]) -> None:
    layout.state_dir.mkdir(parents=True, exist_ok=True)
    with open(layout.events_jsonl, "w", encoding="utf-8") as f:
        for e in events:
            f.write(json.dumps(e, ensure_ascii=False) + "\n")


def test_events_list_empty(project_dir, capsys):
    assert keystone_main(["events", "--dir", str(project_dir)]) == 0
    assert "暂无事件记录" in capsys.readouterr().out


def test_events_accepts_optional_list_alias(project_dir, capsys):
    assert keystone_main(["events", "list", "--dir", str(project_dir)]) == 0
    assert "暂无事件记录" in capsys.readouterr().out


def test_events_list_all(project_dir, capsys):
    layout = KeystoneLayout(project_dir)
    _write_events(layout, [
        {"at": "2026-09-20T10:00:00", "event": "SessionEnd", "reason": "clear", "session_id": "s1", "task": "TASK-001"},
        {"at": "2026-09-20T11:00:00", "event": "SessionEnd", "reason": "logout", "session_id": "s2", "task": None},
    ])
    assert keystone_main(["events", "--dir", str(project_dir)]) == 0
    output = capsys.readouterr().out
    assert "SessionEnd" in output
    assert "TASK-001" in output
    assert "s1" in output
    assert "s2" in output


def test_events_list_filter_by_task(project_dir, capsys):
    layout = KeystoneLayout(project_dir)
    _write_events(layout, [
        {"at": "2026-09-20T10:00:00", "event": "SessionEnd", "reason": "clear", "session_id": "s1", "task": "TASK-001"},
        {"at": "2026-09-20T11:00:00", "event": "SessionEnd", "reason": "logout", "session_id": "s2", "task": "TASK-002"},
    ])
    assert keystone_main(["events", "--dir", str(project_dir), "--task", "TASK-001"]) == 0
    output = capsys.readouterr().out
    assert "TASK-001" in output
    assert "TASK-002" not in output


def test_events_list_filter_by_session(project_dir, capsys):
    layout = KeystoneLayout(project_dir)
    _write_events(layout, [
        {"at": "2026-09-20T10:00:00", "event": "SessionEnd", "reason": "clear", "session_id": "s1", "task": "TASK-001"},
        {"at": "2026-09-20T11:00:00", "event": "SessionEnd", "reason": "logout", "session_id": "s2", "task": "TASK-002"},
    ])
    assert keystone_main(["events", "--dir", str(project_dir), "--session", "s1"]) == 0
    output = capsys.readouterr().out
    assert "s1" in output
    assert "s2" not in output


def test_events_list_filter_by_event_type(project_dir, capsys):
    layout = KeystoneLayout(project_dir)
    _write_events(layout, [
        {"at": "2026-09-20T10:00:00", "event": "SessionEnd", "reason": "clear", "session_id": "s1", "task": "TASK-001"},
    ])
    assert keystone_main(["events", "--dir", str(project_dir), "--event", "SessionEnd"]) == 0
    output = capsys.readouterr().out
    assert "SessionEnd" in output


def test_events_list_no_matches(project_dir, capsys):
    layout = KeystoneLayout(project_dir)
    _write_events(layout, [
        {"at": "2026-09-20T10:00:00", "event": "SessionEnd", "reason": "clear", "session_id": "s1", "task": "TASK-001"},
    ])
    assert keystone_main(["events", "--dir", str(project_dir), "--task", "TASK-999"]) == 0
    assert "暂无匹配" in capsys.readouterr().out


def test_events_list_skips_corrupt_lines(project_dir, capsys):
    layout = KeystoneLayout(project_dir)
    layout.state_dir.mkdir(parents=True, exist_ok=True)
    layout.events_jsonl.write_text(
        '{"at":"2026-09-20T10:00:00","event":"SessionEnd","reason":"clear","session_id":"s1","task":"TASK-001"}\n'
        '{corrupt\n'
        '{"at":"2026-09-20T11:00:00","event":"SessionEnd","reason":"logout","session_id":"s2","task":null}\n',
        encoding="utf-8",
    )
    assert keystone_main(["events", "--dir", str(project_dir)]) == 0
    output = capsys.readouterr().out
    assert "s1" in output
    assert "s2" in output
    assert "corrupt" not in output


def test_events_list_uninitialized_returns_1(tmp_path, capsys):
    assert keystone_main(["events", "--dir", str(tmp_path)]) == 1
    assert "keystone" in capsys.readouterr().err
