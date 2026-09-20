"""plan.md 生成与 PLANNING → PLAN_CONFIRMED 校验测试。"""

from __future__ import annotations

import pytest

from keystone.errors import KeystoneError
from keystone.store import tasks


def test_write_plan_creates_template(layout):
    t = tasks.create_task(layout, "需要计划")
    tasks.write_plan(layout, t["code"])
    plan = tasks.plan_path(layout, t["code"])
    assert plan.is_file()
    content = plan.read_text(encoding="utf-8")
    assert "# 计划" in content
    assert "## 目标" in content
    assert "## 影响范围" in content
    assert "## 实施步骤" in content
    assert "## 验证方案" in content
    assert "## 风险与未决事项" in content


def test_write_plan_rejects_overwrite(layout):
    t = tasks.create_task(layout, "已有计划")
    tasks.write_plan(layout, t["code"])
    with pytest.raises(KeystoneError, match="已有计划文件"):
        tasks.write_plan(layout, t["code"])


def test_has_plan_false_for_missing(layout):
    t = tasks.create_task(layout, "无计划")
    assert not tasks.has_plan(layout, t["code"])


def test_has_plan_false_for_empty_file(layout):
    t = tasks.create_task(layout, "空计划")
    tasks.plan_path(layout, t["code"]).write_text("", encoding="utf-8")
    assert not tasks.has_plan(layout, t["code"])


def test_has_plan_true_for_non_empty(layout):
    t = tasks.create_task(layout, "有计划")
    tasks.write_plan(layout, t["code"])
    assert tasks.has_plan(layout, t["code"])


def test_transition_rejects_planning_to_confirmed_without_plan(layout):
    t = tasks.create_task(layout, "无计划")
    tasks.transition_task(layout, t["code"], "PLANNING")
    with pytest.raises(KeystoneError, match="没有计划文件"):
        tasks.transition_task(layout, t["code"], "PLAN_CONFIRMED")
    assert tasks.load_task(layout, t["code"])["status"] == "PLANNING"


def test_transition_allows_planning_to_confirmed_with_plan(layout):
    t = tasks.create_task(layout, "有计划")
    tasks.transition_task(layout, t["code"], "PLANNING")
    tasks.write_plan(layout, t["code"])
    t = tasks.transition_task(layout, t["code"], "PLAN_CONFIRMED")
    assert t["status"] == "PLAN_CONFIRMED"


def test_transition_other_paths_do_not_require_plan(layout):
    t = tasks.create_task(layout, "其他流转")
    tasks.transition_task(layout, t["code"], "PLANNING")
    tasks.write_plan(layout, t["code"])
    tasks.transition_task(layout, t["code"], "PLAN_CONFIRMED")
    tasks.transition_task(layout, t["code"], "IMPLEMENTING")
    tasks.transition_task(layout, t["code"], "VERIFYING")
    tasks.transition_task(layout, t["code"], "COMPLETED")
    assert tasks.load_task(layout, t["code"])["status"] == "COMPLETED"


def test_load_task_includes_plan_metadata(layout):
    t = tasks.create_task(layout, "元数据")
    assert t["has_plan"] is False
    assert "plan.md" in t["plan_path"]
    tasks.write_plan(layout, t["code"])
    t = tasks.load_task(layout, t["code"])
    assert t["has_plan"] is True
