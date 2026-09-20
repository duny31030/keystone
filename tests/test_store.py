"""存储层测试：任务 CRUD/流转、会话绑定、事件追加。"""

from __future__ import annotations

import json

import pytest

from keystone.errors import KeystoneError
from keystone.store import sessions, tasks


def test_create_task_increments_code(layout):
    t1 = tasks.create_task(layout, "第一个任务", description="做点什么")
    t2 = tasks.create_task(layout, "第二个任务")
    assert t1["code"] == "TASK-001"
    assert t2["code"] == "TASK-002"
    assert (layout.task_dir("TASK-001") / "prd.md").is_file()
    assert t1["description_md"].startswith("# 第一个任务")
    assert t1["acceptance_criteria"] == []


def test_create_task_with_criteria_and_pending(layout):
    t = tasks.create_task(layout, "带验收", acceptance_criteria=["编译通过", "测试通过"],
                          pending_confirmation=True)
    assert t["acceptance_criteria"] == ["编译通过", "测试通过"]
    assert t["pending_confirmation"] is True


def test_transition_records_audit(layout):
    t = tasks.create_task(layout, "流转审计")
    tasks.transition_task(layout, t["code"], "PLANNING", reason="开始分析")
    t = tasks.load_task(layout, t["code"])
    assert t["status"] == "PLANNING"
    assert t["transitions"][-1]["reason"] == "开始分析"
    assert t["transitions"][0]["to"] == "TODO"


def test_illegal_transition_rejected(layout):
    t = tasks.create_task(layout, "非法流转")
    with pytest.raises(KeystoneError):
        tasks.transition_task(layout, t["code"], "COMPLETED")
    # 状态未被改动
    assert tasks.load_task(layout, t["code"])["status"] == "TODO"


def test_find_and_list(layout):
    tasks.create_task(layout, "A")
    tasks.create_task(layout, "B")
    assert tasks.find_task(layout, "TASK-001")["title"] == "A"
    assert tasks.find_task(layout, "TASK-009") is None
    assert [t["code"] for t in tasks.list_tasks(layout)] == ["TASK-001", "TASK-002"]


def test_invalid_code_rejected(layout):
    with pytest.raises(KeystoneError):
        tasks.load_task(layout, "TASK-1")
    with pytest.raises(KeystoneError):
        tasks.load_task(layout, "../escape")


def test_session_binding_roundtrip(layout):
    assert sessions.get_binding(layout, "s1") is None
    sessions.bind_session(layout, "s1", "TASK-001")
    sessions.bind_session(layout, "s2", "TASK-002")
    sessions.bind_session(layout, "s1", "TASK-003")
    assert sessions.get_binding(layout, "s1") == "TASK-003"
    assert sessions.get_binding(layout, "s2") == "TASK-002"
    sessions.unbind_session(layout, "s1")
    assert sessions.get_binding(layout, "s1") is None
    assert sessions.get_binding(layout, "s2") == "TASK-002"


def test_session_end_event_append_metadata(layout):
    sessions.append_event(
        layout,
        {"event": "SessionEnd", "reason": "clear", "session_id": "s1", "task": "TASK-001"},
    )
    lines = layout.events_jsonl.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    event = json.loads(lines[0])
    assert event["event"] == "SessionEnd"
    assert event["reason"] == "clear"
    assert event["session_id"] == "s1"
    assert event["task"] == "TASK-001"
    assert "at" in event
