"""hook 事件处理逻辑测试（直接调用 handler，不经 stdin）。"""

from __future__ import annotations

import json

import pytest
from conftest import make_fields

from keystone.hook import events
from keystone.store import sessions, tasks


def test_session_start_injects_context(layout):
    out = events.session_start(make_fields(), layout)
    assert out["hookSpecificOutput"]["hookEventName"] == "SessionStart"
    ctx = out["hookSpecificOutput"]["additionalContext"]
    assert "demo" in ctx
    assert "pytest" in ctx
    assert "通用禁止事项" in ctx


def test_prompt_submit_creates_pending_task_when_project_empty(layout):
    out = events.user_prompt_submit(
        make_fields(prompt="帮我实现一个导出 CSV 的功能"), layout
    )
    ctx = out["hookSpecificOutput"]["additionalContext"]
    assert "TASK-001" in ctx
    assert "待确认任务" in ctx
    # 已创建并绑定
    assert sessions.get_binding(layout, "sess-1") == "TASK-001"
    task = tasks.load_task(layout, "TASK-001")
    assert task["pending_confirmation"] is True
    assert task["status"] == "TODO"
    # 再次 prompt（无编号）→ 继续使用绑定任务，不重复建任务
    events.user_prompt_submit(make_fields(prompt="继续"), layout)
    assert [t["code"] for t in tasks.list_tasks(layout)] == ["TASK-001"]


def test_prompt_submit_with_existing_tasks_asks_to_choose(layout):
    tasks.create_task(layout, "A")
    tasks.create_task(layout, "B")
    out = events.user_prompt_submit(make_fields(prompt="干点活"), layout)
    ctx = out["hookSpecificOutput"]["additionalContext"]
    assert "没有绑定任务" in ctx
    assert "TASK-001" in ctx and "TASK-002" in ctx
    assert sessions.get_binding(layout, "sess-1") is None


def test_prompt_submit_switches_task_by_code(layout):
    tasks.create_task(layout, "A")
    tasks.create_task(layout, "B")
    out = events.user_prompt_submit(make_fields(prompt="开始做 TASK-002"), layout)
    ctx = out["hookSpecificOutput"]["additionalContext"]
    assert "TASK-002" in ctx and "绑定任务" in ctx
    assert sessions.get_binding(layout, "sess-1") == "TASK-002"


def test_prompt_submit_switches_task_by_hash_code(layout):
    tasks.create_task(layout, "A")
    out = events.user_prompt_submit(make_fields(prompt="继续 #1 的活"), layout)
    assert sessions.get_binding(layout, "sess-1") == "TASK-001"


def test_prompt_submit_unknown_code_lists_available(layout):
    tasks.create_task(layout, "A")
    out = events.user_prompt_submit(make_fields(prompt="做 TASK-009"), layout)
    ctx = out["hookSpecificOutput"]["additionalContext"]
    assert "TASK-009 不存在" in ctx
    assert sessions.get_binding(layout, "sess-1") is None


def test_prompt_submit_stage_requirement_by_status(layout):
    t = tasks.create_task(layout, "A")
    tasks.transition_task(layout, t["code"], "PLANNING")
    sessions.bind_session(layout, "sess-1", t["code"])
    out = events.user_prompt_submit(make_fields(prompt="接着干"), layout)
    ctx = out["hookSpecificOutput"]["additionalContext"]
    assert "计划阶段" in ctx


def test_pre_tool_use_denies_write_in_planning(layout):
    t = tasks.create_task(layout, "A")
    tasks.transition_task(layout, t["code"], "PLANNING")
    sessions.bind_session(layout, "sess-1", t["code"])
    out = events.pre_tool_use(
        make_fields(tool_name="Write", tool_input={"file_path": "/x/y.py"}), layout
    )
    decision = out["hookSpecificOutput"]
    assert decision["permissionDecision"] == "deny"
    assert "PLAN_CONFIRMED" in decision["reason"]


def test_pre_tool_use_allows_read_and_write_tools_after_confirm(layout):
    t = tasks.create_task(layout, "A")
    code = t["code"]
    tasks.transition_task(layout, code, "PLANNING")
    tasks.transition_task(layout, code, "PLAN_CONFIRMED")
    sessions.bind_session(layout, "sess-1", code)
    assert events.pre_tool_use(
        make_fields(tool_name="Read", tool_input={"file_path": "/x/y.py"}), layout
    ) is None
    assert events.pre_tool_use(
        make_fields(tool_name="Write", tool_input={"file_path": "/x/y.py"}), layout
    ) is None


def test_pre_tool_use_denies_write_when_completed(layout):
    t = tasks.create_task(layout, "A")
    code = t["code"]
    for status in ("PLANNING", "PLAN_CONFIRMED", "IMPLEMENTING", "VERIFYING", "COMPLETED"):
        tasks.transition_task(layout, code, status)
    sessions.bind_session(layout, "sess-1", code)
    out = events.pre_tool_use(
        make_fields(tool_name="Edit", tool_input={"file_path": "/x/y.py"}), layout
    )
    assert out["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert "reopen" in out["hookSpecificOutput"]["reason"]


def test_pre_tool_use_protects_keystone_state_files(layout):
    t = tasks.create_task(layout, "A")
    tasks.transition_task(layout, t["code"], "PLANNING")
    tasks.transition_task(layout, t["code"], "PLAN_CONFIRMED")  # 已过计划阶段
    sessions.bind_session(layout, "sess-1", t["code"])
    for target in (
        str(layout.task_dir(t["code"]) / "task.json"),
        str(layout.dir / ".state" / "sessions.json"),
        str(layout.dir / "project.json"),
    ):
        out = events.pre_tool_use(
            make_fields(tool_name="Write", tool_input={"file_path": target}), layout
        )
        assert out is not None and out["hookSpecificOutput"]["permissionDecision"] == "deny", target
    # prd.md 与规范文件不受保护
    assert events.pre_tool_use(
        make_fields(tool_name="Write",
                    tool_input={"file_path": str(layout.task_dir(t["code"]) / "prd.md")}),
        layout,
    ) is None


def test_pre_tool_use_allows_when_no_task_in_permissive(layout):
    assert events.pre_tool_use(
        make_fields(tool_name="Write", tool_input={"file_path": "/x.py"}), layout
    ) is None


def test_pre_tool_use_strict_denies_when_no_task(layout):
    from keystone.store.project import load_project, save_project
    project = load_project(layout)
    project["policy_mode"] = "strict"
    save_project(layout, project)
    out = events.pre_tool_use(
        make_fields(tool_name="write_to_file", tool_input={"file_path": "/x.py"}), layout
    )
    assert out["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_session_end_records_reason_and_bound_task(layout):
    tasks.create_task(layout, "A")
    sessions.bind_session(layout, "sess-1", "TASK-001")
    assert events.session_end(make_fields(reason="clear"), layout) is None
    event = json.loads(layout.events_jsonl.read_text(encoding="utf-8").splitlines()[0])
    assert event["event"] == "SessionEnd"
    assert event["reason"] == "clear"
    assert event["session_id"] == "sess-1"
    assert event["task"] == "TASK-001"
    assert "at" in event


def test_session_end_uses_unknown_reason_when_missing(layout):
    assert events.session_end(make_fields(), layout) is None
    event = json.loads(layout.events_jsonl.read_text(encoding="utf-8").splitlines()[0])
    assert event["reason"] == "unknown"


def test_stop_reminder_mode(layout):
    tasks.create_task(layout, "A")
    sessions.bind_session(layout, "sess-1", "TASK-001")
    out = events.stop(make_fields(), layout)
    ctx = out["hookSpecificOutput"]["additionalContext"]
    assert "检查清单" in ctx
    assert "decision" not in out


def test_stop_enforce_mode_blocks_incomplete(layout):
    from keystone.store.project import load_project, save_project
    project = load_project(layout)
    project["stop_mode"] = "enforce"
    save_project(layout, project)
    t = tasks.create_task(layout, "A")
    sessions.bind_session(layout, "sess-1", t["code"])
    out = events.stop(make_fields(), layout)
    assert out["decision"] == "block"
    assert "检查清单" in out["reason"]


def test_stop_allows_completed_in_enforce(layout):
    from keystone.store.project import load_project, save_project
    project = load_project(layout)
    project["stop_mode"] = "enforce"
    save_project(layout, project)
    t = tasks.create_task(layout, "A")
    code = t["code"]
    for status in ("PLANNING", "PLAN_CONFIRMED", "IMPLEMENTING", "VERIFYING", "COMPLETED"):
        tasks.transition_task(layout, code, status)
    sessions.bind_session(layout, "sess-1", code)
    out = events.stop(make_fields(), layout)
    assert out["hookSpecificOutput"]["hookEventName"] == "Stop"


def test_stop_loop_guard(layout):
    # stop_hook_active=True → 直接放行
    assert events.stop(make_fields(stop_hook_active=True), layout) is None


def test_stop_without_task_is_silent(layout):
    assert events.stop(make_fields(), layout) is None
