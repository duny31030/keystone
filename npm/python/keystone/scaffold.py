"""keystone init 的落地动作：.keystone 脚手架、CodeBuddy settings.json 合并、gitignore 追加。

合并语义：settings.json 中只增删 command 含 "keystone" 的 hook 条目，
其余条目（trellis、用户手工配置等）原样保留，可反复执行（幂等）。
"""

from __future__ import annotations

import json
from pathlib import Path

from keystone.store.layout import CODEBUDDY_SETTINGS, KEYSTONE_DIR, KeystoneLayout
from keystone.store.project import save_project
from keystone.store.specs import write_templates as write_spec_templates
from keystone.util import atomic_write_json

# PreToolUse 的 matcher：写类与执行类工具的宽松 alternation
TOOL_MATCHER = (
    "Write|Edit|MultiEdit|NotebookEdit|write_to_file|replace_in_file|apply_patch|"
    "str_replace_editor|str_replace_based_edit_tool|create_file|edit_file|save_file|"
    "Bash|execute_command|run_command|run_terminal_cmd|terminal|shell"
)

# 真实 CodeBuddy 验证未确认的旧版默认注册。重跑 init 时只清理 Keystone
# 自己的规则，绝不影响同一事件下的用户或其他工具 hook。
RETIRED_EVENTS = ("PostToolUse", "PreCompact")

_HOOK_TIMEOUT = 15


def _render_command(prefix: str, event: str) -> str:
    if "{event}" in prefix:
        return prefix.format(event=event)
    return f"{prefix} {event}"


def build_hooks_block(prefix: str) -> dict:
    """已在真实 CodeBuddy 中验证的默认 hooks 注册块。"""

    def rule(event: str) -> dict:
        return {
            "type": "command",
            "command": _render_command(prefix, event),
            "timeout": _HOOK_TIMEOUT,
        }

    return {
        "SessionStart": [
            {"matcher": matcher, "hooks": [rule("session-start")]}
            for matcher in ("startup", "clear", "compact")
        ],
        "UserPromptSubmit": [{"hooks": [rule("user-prompt-submit")]}],
        "PreToolUse": [{"matcher": TOOL_MATCHER, "hooks": [rule("pre-tool-use")]}],
        "Stop": [{"hooks": [rule("stop")]}],
        "SessionEnd": [{"hooks": [rule("session-end")]}],
    }


def _is_keystone_command(hook: object) -> bool:
    return isinstance(hook, dict) and "keystone" in str(hook.get("command", ""))


def _without_keystone_hooks(rule: object) -> dict | None:
    """从一条规则中移除 Keystone commands，保留共存的第三方 commands。"""
    if not isinstance(rule, dict):
        return rule
    command_hooks = rule.get("hooks")
    if not isinstance(command_hooks, list):
        return rule
    kept_hooks = [hook for hook in command_hooks if not _is_keystone_command(hook)]
    if not kept_hooks:
        return None
    retained = dict(rule)
    retained["hooks"] = kept_hooks
    return retained


def _remove_keystone_hooks(rules: object) -> list:
    if not isinstance(rules, list):
        return []
    return [retained for rule in rules if (retained := _without_keystone_hooks(rule)) is not None]


def merge_settings(existing: dict | None, prefix: str) -> dict:
    """合入已验证 hooks，并清理旧 Keystone 的退役事件注册。"""
    ours = build_hooks_block(prefix)
    merged = json.loads(json.dumps(existing)) if existing else {}
    hooks = merged.setdefault("hooks", {})

    for event in RETIRED_EVENTS:
        if event not in hooks:
            continue
        kept = _remove_keystone_hooks(hooks[event])
        if kept:
            hooks[event] = kept
        else:
            del hooks[event]

    for event, rules in ours.items():
        kept = _remove_keystone_hooks(hooks.get(event, []))
        hooks[event] = kept + rules
    return merged


def write_codebuddy_settings(target_root: Path, prefix: str) -> tuple[Path, bool]:
    """写 .codebuddy/settings.json；返回 (路径, 是否已存在过)。"""
    settings_path = target_root / CODEBUDDY_SETTINGS
    existing = None
    existed = settings_path.is_file()
    if existed:
        existing = json.loads(settings_path.read_text(encoding="utf-8"))
    merged = merge_settings(existing, prefix)
    atomic_write_json(settings_path, merged)
    return settings_path, existed


GITIGNORE_MARKER = "# Keystone runtime state (managed by keystone init)"
GITIGNORE_ENTRY = ".keystone/.state/"


def ensure_gitignore(target_root: Path) -> bool:
    """向目标项目 .gitignore 追加运行时状态忽略项；已配置则跳过。返回是否修改。"""
    gitignore = target_root / ".gitignore"
    content = gitignore.read_text(encoding="utf-8") if gitignore.is_file() else ""
    if GITIGNORE_ENTRY in content:
        return False
    if content and not content.endswith("\n"):
        content += "\n"
    block = f"{GITIGNORE_MARKER}\n{GITIGNORE_ENTRY}\n"
    with open(gitignore, "a", encoding="utf-8") as f:
        f.write(("\n" + block) if content else block)
    return True


def detect_language(target_root: Path) -> str | None:
    """按标志文件猜测项目语言；无法判断返回 None。"""
    markers = {
        "java": ("pom.xml", "build.gradle", "build.gradle.kts", "settings.gradle"),
        "python": ("pyproject.toml", "requirements.txt", "setup.py", "setup.cfg", "pytest.ini"),
    }
    for lang, files in markers.items():
        if any((target_root / f).is_file() for f in files):
            return lang
    return None


def scaffold_keystone(target_root: Path, project: dict) -> tuple[KeystoneLayout, bool]:
    """生成 .keystone/ 目录（project.json + specs 模板 + tasks/）。

    已有 project.json 时不覆盖（幂等重入）。返回 (layout, 是否新建)。
    """
    layout = KeystoneLayout(target_root)
    if layout.initialized:
        return layout, False
    layout.tasks_dir.mkdir(parents=True, exist_ok=True)
    layout.state_dir.mkdir(parents=True, exist_ok=True)
    save_project(layout, project)
    write_spec_templates(layout)
    return layout, True
