"""上下文渲染测试。"""

from __future__ import annotations

from keystone.core import context
from keystone.store.project import make_project


def make_project_dict(**over) -> dict:
    project = make_project(slug="demo", name="demo-service", language="python",
                           test_command="pytest")
    project.update(over)
    return project


SPECS = [
    ("architecture", "分层架构：api / service / dao"),
    ("coding", "命名用 snake_case"),
    ("general-ban", "禁止提交密钥"),
]


def test_session_start_contains_specs_and_commands():
    text = context.render_session_start(make_project_dict(), SPECS)
    assert text.startswith("<keystone-context>")
    assert "demo-service" in text
    assert "pytest" in text
    assert "## 架构规范" in text and "分层架构" in text
    assert "## 通用禁止事项" in text and "禁止提交密钥" in text
    assert text.endswith("</keystone-context>")


def test_session_start_skips_empty_specs():
    text = context.render_session_start(make_project_dict(), [("coding", "")])
    assert "编码规范" not in text


def test_task_block_contains_acceptance_and_stage():
    task = {"code": "TASK-001", "title": "加一个接口", "status": "PLANNING",
            "pending_confirmation": False,
            "acceptance_criteria": ["接口返回 200", "有测试覆盖"],
            "description_md": "给 order 加一个查询接口"}
    text = context.render_task(make_project_dict(), task)
    assert "<keystone-task>" in text
    assert "TASK-001 加一个接口" in text
    assert "- [ ] 接口返回 200" in text
    assert "不要修改任何代码或文件" in text  # PLANNING 阶段要求


def test_task_pending_flag_note():
    task = {"code": "TASK-001", "title": "t", "status": "TODO",
            "pending_confirmation": True, "acceptance_criteria": [], "description_md": ""}
    text = context.render_task(make_project_dict(), task)
    assert "待确认任务" in text


def test_task_selection_lists_tasks():
    tasks = [{"code": "TASK-001", "status": "IMPLEMENTING", "title": "A"},
             {"code": "TASK-002", "status": "TODO", "title": "B"}]
    text = context.render_task_selection(tasks)
    assert "没有绑定任务" in text
    assert "TASK-001" in text and "TASK-002" in text


def test_stop_checklist_items():
    task = {"code": "TASK-001", "title": "x", "status": "VERIFYING",
            "acceptance_criteria": ["c1"], "description_md": ""}
    text = context.render_stop_checklist(make_project_dict(), task)
    assert "<keystone-checklist>" in text
    assert "是否完成任务目标" in text
    assert "验证结果" in text
    assert "pytest" in text
    assert "推进到 COMPLETED" in text
