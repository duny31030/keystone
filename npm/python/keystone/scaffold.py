"""项目脚手架、CodeBuddy hook 配置合并与生命周期变更计划。"""

from __future__ import annotations

import difflib
import json
from dataclasses import dataclass
from pathlib import Path

from keystone.adapters.codebuddy import TOOL_MATCHER
from keystone.adapters.registry import get_adapter
from keystone.store.layout import KeystoneLayout
from keystone.store.project import save_project
from keystone.store.specs import SPEC_CATEGORIES, write_templates as write_spec_templates
from keystone.util import atomic_write_json

RETIRED_EVENTS = ("PostToolUse", "PreCompact")
EXPECTED_EVENTS = ("SessionStart", "UserPromptSubmit", "PreToolUse", "Stop", "SessionEnd")
_HOOK_TIMEOUT = 15
GITIGNORE_MARKER = "# Keystone runtime state (managed by keystone init)"
GITIGNORE_ENTRY = ".keystone/.state/"
GITIGNORE_BLOCK = f"{GITIGNORE_MARKER}\n{GITIGNORE_ENTRY}\n"


@dataclass(frozen=True)
class PlannedChange:
    action: str
    path: Path
    diff: str = ""


@dataclass(frozen=True)
class InitPlan:
    layout: KeystoneLayout
    changes: tuple[PlannedChange, ...]
    settings: dict
    settings_path: Path
    gitignore_content: str
    creates_project: bool


@dataclass(frozen=True)
class UninstallPlan:
    target_root: Path
    changes: tuple[PlannedChange, ...]
    settings: dict | None
    settings_path: Path
    gitignore_content: str | None


def render_json(data: dict) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2) + "\n"


def _unified_diff(path: Path, before: str, after: str) -> str:
    return "".join(
        difflib.unified_diff(
            before.splitlines(keepends=True),
            after.splitlines(keepends=True),
            fromfile=f"a/{path.name}",
            tofile=f"b/{path.name}",
        )
    )


def build_hooks_block(prefix: str) -> dict:
    """Compatibility wrapper for the default CodeBuddy adapter."""
    return get_adapter("codebuddy").build_hooks(prefix)


def _is_keystone_command(hook: object) -> bool:
    from keystone.adapters.base import is_keystone_hook
    return is_keystone_hook(hook)


def _without_keystone_hooks(rule: object) -> dict | None:
    from keystone.adapters.base import without_keystone_hooks
    return without_keystone_hooks(rule)


def _remove_keystone_hooks(rules: object) -> list:
    from keystone.adapters.base import remove_keystone_hooks
    return remove_keystone_hooks(rules)


def merge_settings(existing: dict | None, prefix: str) -> dict:
    """Compatibility wrapper for the default CodeBuddy adapter."""
    return get_adapter("codebuddy").merge_settings(existing, prefix)


def remove_keystone_settings(existing: dict) -> dict:
    """Compatibility wrapper for the default CodeBuddy adapter."""
    return get_adapter("codebuddy").remove_keystone_settings(existing)


def planned_gitignore_content(content: str) -> str:
    if GITIGNORE_ENTRY in content:
        return content
    if content and not content.endswith("\n"):
        content += "\n"
    return content + ("\n" if content else "") + GITIGNORE_BLOCK


def remove_managed_gitignore_block(content: str) -> str:
    """只删除完整 Keystone managed block，用户自己维护的同名行不受影响。"""
    return content.replace(GITIGNORE_BLOCK, "")


def plan_init(target_root: Path, project: dict, prefix: str, platform: str = "codebuddy") -> InitPlan:
    adapter = get_adapter(platform)
    layout = KeystoneLayout(target_root)
    changes: list[PlannedChange] = []
    creates_project = not layout.initialized
    if creates_project:
        changes += [
            PlannedChange("CREATE", layout.project_json),
            PlannedChange("CREATE", layout.tasks_dir),
            PlannedChange("CREATE", layout.state_dir),
        ]
    else:
        changes.append(PlannedChange("UNCHANGED", layout.project_json))
    for category in SPEC_CATEGORIES:
        path = layout.specs_dir / f"{category}.md"
        changes.append(PlannedChange("UNCHANGED" if path.exists() else "CREATE", path))

    settings_path = target_root / adapter.settings_relative_path
    settings_before = settings_path.read_text(encoding="utf-8") if settings_path.is_file() else ""
    existing = json.loads(settings_before) if settings_before else None
    settings = adapter.merge_settings(existing, prefix)
    settings_after = render_json(settings)
    settings_action = "CREATE" if not settings_path.exists() else "UPDATE" if settings_after != settings_before else "UNCHANGED"
    changes.append(PlannedChange(settings_action, settings_path, _unified_diff(settings_path, settings_before, settings_after)))

    gitignore = target_root / ".gitignore"
    gitignore_before = gitignore.read_text(encoding="utf-8") if gitignore.is_file() else ""
    gitignore_after = planned_gitignore_content(gitignore_before)
    gitignore_action = "CREATE" if not gitignore.exists() else "UPDATE" if gitignore_after != gitignore_before else "UNCHANGED"
    changes.append(PlannedChange(gitignore_action, gitignore, _unified_diff(gitignore, gitignore_before, gitignore_after)))
    return InitPlan(layout, tuple(changes), settings, settings_path, gitignore_after, creates_project)


def apply_init_plan(plan: InitPlan, project: dict) -> tuple[Path, bool, bool]:
    if plan.creates_project:
        plan.layout.tasks_dir.mkdir(parents=True, exist_ok=True)
        plan.layout.state_dir.mkdir(parents=True, exist_ok=True)
        save_project(plan.layout, project)
    write_spec_templates(plan.layout)
    settings_path = plan.settings_path
    existing_text = settings_path.read_text(encoding="utf-8") if settings_path.is_file() else ""
    settings_changed = render_json(plan.settings) != existing_text
    if settings_changed:
        atomic_write_json(settings_path, plan.settings)
    gitignore = plan.layout.root / ".gitignore"
    existing_ignore = gitignore.read_text(encoding="utf-8") if gitignore.is_file() else ""
    gitignore_changed = plan.gitignore_content != existing_ignore
    if gitignore_changed:
        gitignore.write_text(plan.gitignore_content, encoding="utf-8")
    return settings_path, settings_changed, gitignore_changed


def plan_uninstall(target_root: Path, purge: bool, platform: str = "codebuddy") -> UninstallPlan:
    adapter = get_adapter(platform)
    changes: list[PlannedChange] = []
    settings_path = target_root / adapter.settings_relative_path
    settings = None
    if settings_path.is_file():
        before = settings_path.read_text(encoding="utf-8")
        settings = adapter.remove_keystone_settings(json.loads(before))
        after = render_json(settings)
        action = "UPDATE" if after != before else "UNCHANGED"
        changes.append(PlannedChange(action, settings_path, _unified_diff(settings_path, before, after)))

    gitignore_content = None
    if purge:
        layout = KeystoneLayout(target_root)
        if layout.dir.exists():
            changes.append(PlannedChange("REMOVE", layout.dir))
        gitignore = target_root / ".gitignore"
        if gitignore.is_file():
            before = gitignore.read_text(encoding="utf-8")
            gitignore_content = remove_managed_gitignore_block(before)
            action = "UPDATE" if gitignore_content != before else "UNCHANGED"
            changes.append(PlannedChange(action, gitignore, _unified_diff(gitignore, before, gitignore_content)))
    return UninstallPlan(target_root, tuple(changes), settings, settings_path, gitignore_content)


def apply_uninstall_plan(plan: UninstallPlan) -> None:
    settings_path = plan.settings_path
    if plan.settings is not None and any(c.path == settings_path and c.action == "UPDATE" for c in plan.changes):
        atomic_write_json(settings_path, plan.settings)
    layout = KeystoneLayout(plan.target_root)
    if any(c.path == layout.dir and c.action == "REMOVE" for c in plan.changes):
        import shutil
        shutil.rmtree(layout.dir)
    gitignore = plan.target_root / ".gitignore"
    if plan.gitignore_content is not None and any(c.path == gitignore and c.action == "UPDATE" for c in plan.changes):
        gitignore.write_text(plan.gitignore_content, encoding="utf-8")


def write_codebuddy_settings(target_root: Path, prefix: str) -> tuple[Path, bool]:
    """Compatibility wrapper for legacy callers using the default adapter."""
    adapter = get_adapter("codebuddy")
    path = target_root / adapter.settings_relative_path
    existed = path.is_file()
    existing = json.loads(path.read_text(encoding="utf-8")) if existed else None
    atomic_write_json(path, adapter.merge_settings(existing, prefix))
    return path, existed


def ensure_gitignore(target_root: Path) -> bool:
    path = target_root / ".gitignore"
    before = path.read_text(encoding="utf-8") if path.is_file() else ""
    after = planned_gitignore_content(before)
    if after == before:
        return False
    path.write_text(after, encoding="utf-8")
    return True


def detect_language(target_root: Path) -> str | None:
    markers = {"java": ("pom.xml", "build.gradle", "build.gradle.kts", "settings.gradle"), "python": ("pyproject.toml", "requirements.txt", "setup.py", "setup.cfg", "pytest.ini")}
    for lang, files in markers.items():
        if any((target_root / file).is_file() for file in files):
            return lang
    return None


def scaffold_keystone(target_root: Path, project: dict) -> tuple[KeystoneLayout, bool]:
    layout = KeystoneLayout(target_root)
    if layout.initialized:
        return layout, False
    layout.tasks_dir.mkdir(parents=True, exist_ok=True)
    layout.state_dir.mkdir(parents=True, exist_ok=True)
    save_project(layout, project)
    write_spec_templates(layout)
    return layout, True
