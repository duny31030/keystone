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

# PreToolUse / PostToolUse 的 matcher：写类与执行类工具的宽松 alternation
TOOL_MATCHER = (
    "Write|Edit|MultiEdit|NotebookEdit|write_to_file|replace_in_file|apply_patch|"
    "str_replace_editor|str_replace_based_edit_tool|create_file|edit_file|save_file|"
    "Bash|execute_command|run_command|run_terminal_cmd|terminal|shell"
)

_HOOK_TIMEOUT = 15


def _render_command(prefix: str, event: str) -> str:
    if "{event}" in prefix:
        return prefix.format(event=event)
    return f"{prefix} {event}"


def build_hooks_block(prefix: str) -> dict:
    """CodeBuddy hooks 注册块（PascalCase 事件名，CodeBuddy 未支持的事件不会触发、无害）。"""

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
        "PostToolUse": [{"matcher": TOOL_MATCHER, "hooks": [rule("post-tool-use")]}],
        "Stop": [{"hooks": [rule("stop")]}],
        "SessionEnd": [{"hooks": [rule("session-end")]}],
        "PreCompact": [{"hooks": [rule("pre-compact")]}],
    }


def _is_keystone_rule(rule: dict) -> bool:
    return any(
        "keystone" in str(h.get("command", "")) for h in rule.get("hooks", [])
    )


def merge_settings(existing: dict | None, prefix: str) -> dict:
    """把 keystone 的 hooks 合入既有 settings（先移除旧 keystone 条目再追加）。"""
    ours = build_hooks_block(prefix)
    merged = json.loads(json.dumps(existing)) if existing else {}
    hooks = merged.setdefault("hooks", {})
    for event, rules in ours.items():
        kept = [r for r in hooks.get(event, []) if not _is_keystone_rule(r)]
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
