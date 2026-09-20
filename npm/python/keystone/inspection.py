"""本地 Keystone 项目的只读检查与摘要。"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from keystone.core.statemachine import STATUSES
from keystone.scaffold import EXPECTED_EVENTS, RETIRED_EVENTS, _is_keystone_command, build_hooks_block, merge_settings, remove_keystone_settings
from keystone.store.layout import CODEBUDDY_SETTINGS, KeystoneLayout, find_layout
from keystone.store.specs import SPEC_CATEGORIES, write_templates as write_spec_templates


@dataclass(frozen=True)
class JsonView:
    path: Path
    state: str
    value: object | None = None
    error: str = ""


def inspect_json(path: Path, expected: type = dict) -> JsonView:
    if not path.is_file():
        return JsonView(path, "missing")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return JsonView(path, "invalid", error=str(exc))
    if not isinstance(value, expected):
        return JsonView(path, "wrong-type", value=value, error=f"expected {expected.__name__}")
    return JsonView(path, "ok", value=value)


def resolve_layout(target: Path) -> KeystoneLayout | None:
    return find_layout(target)


def hook_commands(settings: dict) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    hooks = settings.get("hooks", {})
    if not isinstance(hooks, dict):
        return result
    for event, rules in hooks.items():
        if not isinstance(rules, list):
            continue
        for rule in rules:
            if not isinstance(rule, dict):
                continue
            for hook in rule.get("hooks", []):
                if _is_keystone_command(hook):
                    result.setdefault(str(event), []).append(str(hook.get("command", "")))
    return result


def inspect_project(target: Path) -> dict:
    layout = resolve_layout(target)
    if layout is None:
        return {"layout": None, "project": JsonView(target / ".keystone/project.json", "missing")}
    project = inspect_json(layout.project_json)
    settings = inspect_json(layout.root / CODEBUDDY_SETTINGS)
    sessions = inspect_json(layout.sessions_json)
    tasks: list[tuple[Path, JsonView]] = []
    if layout.tasks_dir.is_dir():
        for directory in sorted(layout.tasks_dir.iterdir()):
            if directory.is_dir():
                tasks.append((directory, inspect_json(directory / "task.json")))
    return {"layout": layout, "project": project, "settings": settings, "sessions": sessions, "tasks": tasks}


def doctor_findings(target: Path) -> list[tuple[str, str, str]]:
    info = inspect_project(target)
    layout = info["layout"]
    if layout is None:
        return [("FAIL", "project", "未找到 .keystone/project.json；在项目根目录执行 keystone init")]
    findings: list[tuple[str, str, str]] = []
    project: JsonView = info["project"]
    if project.state != "ok":
        return [("FAIL", "project", f"project.json {project.state}: {project.error or '缺失'}")]
    data = project.value
    assert isinstance(data, dict)
    findings.append(("PASS", "project", f"{data.get('name', '<unnamed>')} ({data.get('language', '?')})"))
    for field, valid in (("language", {"java", "python"}), ("policy_mode", {"permissive", "strict"}), ("stop_mode", {"reminder", "enforce"})):
        if data.get(field) not in valid:
            findings.append(("FAIL", field, f"无效值：{data.get(field)!r}"))
    if data.get("stop_mode") == "enforce":
        findings.append(("WARN", "stop_mode", "enforce 的 CodeBuddy 宿主阻止行为尚未实机验证"))
    for category in SPEC_CATEGORIES:
        path = layout.specs_dir / f"{category}.md"
        findings.append(("PASS" if path.is_file() else "WARN", "spec", str(path.relative_to(layout.root))))
    findings.append(("PASS" if layout.tasks_dir.is_dir() else "WARN", "tasks", "tasks directory"))
    findings.append(("PASS" if layout.state_dir.is_dir() else "WARN", "runtime", ".state directory"))
    gitignore = layout.root / ".gitignore"
    ignored = gitignore.is_file() and ".keystone/.state/" in gitignore.read_text(encoding="utf-8")
    findings.append(("PASS" if ignored else "WARN", "gitignore", "runtime state ignored" if ignored else "缺少 .keystone/.state/ 忽略项"))
    settings: JsonView = info["settings"]
    if settings.state == "missing":
        findings.append(("WARN", "settings", "未找到 .codebuddy/settings.json；运行 keystone init 修复"))
    elif settings.state != "ok" or not isinstance(settings.value, dict) or not isinstance(settings.value.get("hooks", {}), dict):
        findings.append(("FAIL", "settings", f"settings.json {settings.state if settings.state != 'ok' else 'hooks 必须是 object'}"))
    else:
        registered = hook_commands(settings.value)
        for event in EXPECTED_EVENTS:
            count = len(registered.get(event, []))
            findings.append(("PASS" if count == 1 or event == "SessionStart" and count == 3 else "WARN", "hook", f"{event}: {count} Keystone registrations"))
        for event in RETIRED_EVENTS:
            if registered.get(event):
                findings.append(("WARN", "hook", f"存在退役 Keystone {event} 注册；运行 keystone init 清理"))
    for directory, task in info["tasks"]:
        if task.state != "ok" or not isinstance(task.value, dict):
            findings.append(("WARN", "task", f"{directory.name}/task.json {task.state}"))
            continue
        if task.value.get("code") != directory.name or task.value.get("status") not in STATUSES:
            findings.append(("WARN", "task", f"{directory.name} 编号或状态无效"))
    sessions: JsonView = info["sessions"]
    if sessions.state not in ("missing", "ok"):
        findings.append(("WARN", "sessions", f"sessions.json {sessions.state}"))
    return findings


def doctor_fix(target: Path, prefix: str = "keystone-hook") -> list[str]:
    """自动修复 doctor 发现的可安全修复问题，返回修复动作列表。"""
    from keystone.util import atomic_write_json
    from keystone.scaffold import GITIGNORE_BLOCK, GITIGNORE_ENTRY, GITIGNORE_MARKER

    info = inspect_project(target)
    layout = info["layout"]
    if layout is None:
        return []
    fixed: list[str] = []

    # 修复 settings.json：补齐缺失的 hook 注册，清理退役条目
    settings_path = layout.root / CODEBUDDY_SETTINGS
    settings_view = info["settings"]
    if settings_view.state == "missing" or settings_view.state == "ok":
        existing = settings_view.value if settings_view.state == "ok" else None
        merged = merge_settings(existing, prefix)
        if existing != merged:
            atomic_write_json(settings_path, merged)
            fixed.append(f"更新 {settings_path.name}（补齐/清理 Keystone hook 注册）")

    # 修复 .gitignore：补 managed block
    gitignore_path = layout.root / ".gitignore"
    if gitignore_path.is_file():
        content = gitignore_path.read_text(encoding="utf-8")
        if GITIGNORE_ENTRY not in content:
            if content and not content.endswith("\n"):
                content += "\n"
            content += "\n" + GITIGNORE_BLOCK
            gitignore_path.write_text(content, encoding="utf-8")
            fixed.append("补 .gitignore 的 .keystone/.state/ 忽略项")
    else:
        gitignore_path.write_text(GITIGNORE_BLOCK, encoding="utf-8")
        fixed.append("创建 .gitignore 并添加 .keystone/.state/ 忽略项")

    # 修复 .keystone/ 目录结构：创建缺失的目录
    for directory in (layout.tasks_dir, layout.state_dir):
        if not directory.is_dir():
            directory.mkdir(parents=True, exist_ok=True)
            fixed.append(f"创建目录 {directory.relative_to(layout.root)}")

    # 修复规范模板：生成缺失的模板文件
    created_specs = write_spec_templates(layout)
    for path in created_specs:
        fixed.append(f"生成规范模板 {path.relative_to(layout.root)}")

    return fixed
