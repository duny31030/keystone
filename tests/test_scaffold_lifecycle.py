"""脚手架计划与无损卸载单元测试。"""

from __future__ import annotations

import json

from keystone import scaffold
from keystone.store.project import make_project


def test_plan_init_is_read_only_and_lists_expected_changes(tmp_path):
    project = make_project("demo", "demo", "python")
    plan = scaffold.plan_init(tmp_path, project, "keystone-hook")
    assert not (tmp_path / ".keystone").exists()
    assert {change.action for change in plan.changes} == {"CREATE"}
    assert any(change.path.name == "settings.json" and "SessionEnd" in change.diff for change in plan.changes)
    assert any(change.path.name == ".gitignore" for change in plan.changes)


def test_plan_init_preserves_existing_project_and_mixed_hook_rule(tmp_path):
    project = make_project("demo", "demo", "python")
    scaffold.apply_init_plan(scaffold.plan_init(tmp_path, project, "keystone-hook"), project)
    settings = tmp_path / ".codebuddy/settings.json"
    data = json.loads(settings.read_text(encoding="utf-8"))
    data["hooks"]["PostToolUse"] = [{
        "matcher": "Edit",
        "hooks": [
            {"command": "keystone-hook post-tool-use"},
            {"command": "vendor-hook preserve"},
        ],
    }]
    settings.write_text(json.dumps(data), encoding="utf-8")
    before_project = (tmp_path / ".keystone/project.json").read_text(encoding="utf-8")
    plan = scaffold.plan_init(tmp_path, project, "keystone-hook")
    settings_change = next(change for change in plan.changes if change.path == settings)
    assert settings_change.action == "UPDATE"
    assert "vendor-hook preserve" in settings_change.diff
    assert "post-tool-use" in settings_change.diff
    assert (tmp_path / ".keystone/project.json").read_text(encoding="utf-8") == before_project


def test_remove_keystone_settings_preserves_mixed_rules_and_other_events():
    original = {
        "other": True,
        "hooks": {
            "Stop": [{"hooks": [{"command": "keystone-hook stop"}, {"command": "vendor stop"}]}],
            "Other": [{"hooks": [{"command": "vendor keep"}]}],
        },
    }
    result = scaffold.remove_keystone_settings(original)
    assert result["other"] is True
    assert result["hooks"]["Stop"] == [{"hooks": [{"command": "vendor stop"}]}]
    assert result["hooks"]["Other"] == [{"hooks": [{"command": "vendor keep"}]}]


def test_remove_keystone_settings_preserves_vendor_command_with_keystone_name():
    original = {"hooks": {"Stop": [{"hooks": [{"command": "vendor-keystone-helper stop"}]}]}}
    assert scaffold.remove_keystone_settings(original) == original


def test_remove_managed_gitignore_block_leaves_user_rule():
    user_content = ".keystone/.state/\n"
    assert scaffold.remove_managed_gitignore_block(user_content) == user_content
    managed = "node_modules/\n\n" + scaffold.GITIGNORE_BLOCK + "custom/\n"
    result = scaffold.remove_managed_gitignore_block(managed)
    assert scaffold.GITIGNORE_MARKER not in result
    assert ".keystone/.state/" not in result
    assert "node_modules/" in result and "custom/" in result


def test_remove_managed_gitignore_block_preserves_unrelated_whitespace():
    content = "before\n\n\n\n" + scaffold.GITIGNORE_BLOCK + "\n\n\n\nafter\n"
    assert scaffold.remove_managed_gitignore_block(content) == "before\n\n\n\n\n\n\n\nafter\n"


def test_uninstall_plan_is_read_only_and_purge_plans_removal(tmp_path):
    project = make_project("demo", "demo", "python")
    scaffold.apply_init_plan(scaffold.plan_init(tmp_path, project, "keystone-hook"), project)
    before_settings = (tmp_path / ".codebuddy/settings.json").read_text(encoding="utf-8")
    plan = scaffold.plan_uninstall(tmp_path, purge=True)
    assert (tmp_path / ".keystone/project.json").is_file()
    assert (tmp_path / ".codebuddy/settings.json").read_text(encoding="utf-8") == before_settings
    assert any(change.action == "REMOVE" and change.path.name == ".keystone" for change in plan.changes)
    assert any(change.path.name == ".gitignore" and change.action == "UPDATE" for change in plan.changes)
