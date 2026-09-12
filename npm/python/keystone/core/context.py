"""上下文渲染：把项目/任务/规范渲染成注入给 CodeBuddy 的 Markdown。

纯函数、不接触文件系统 —— 数据由 store/ 或未来的服务端 API 提供。
"""

from __future__ import annotations

from keystone.core import policy
from keystone.core.statemachine import PRE_CONFIRM_STATUSES

SPEC_LABELS = {
    "architecture": "架构规范",
    "coding": "编码规范",
    "general-ban": "通用禁止事项",
}


def _fmt_project_line(project: dict) -> str:
    parts = [f"**{project.get('name', '<unnamed>')}**"]
    lang = project.get("language")
    if lang:
        parts.append(f"语言 {lang}")
    fw = project.get("framework")
    if fw:
        parts.append(f"框架 {fw}")
    bt = project.get("build_tool")
    if bt:
        parts.append(f"构建工具 {bt}")
    return " · ".join(parts)


def render_session_start(project: dict, specs: list[tuple[str, str]]) -> str:
    """SessionStart：项目基础资料 + 规范 + 禁止事项。"""
    lines = ["<keystone-context>", "# Keystone 项目上下文", "", "## 项目", _fmt_project_line(project)]
    labels = {"build_command": "构建命令", "test_command": "测试命令"}
    for key in ("build_command", "test_command"):
        if project.get(key):
            lines.append(f"- {labels[key]}：`{project[key]}`")
    for category, content in specs:
        label = SPEC_LABELS.get(category, category)
        if content and content.strip():
            lines += ["", f"## {label}", content.strip()]
    lines += ["", "</keystone-context>"]
    return "\n".join(lines)


def render_task(project: dict, task: dict, note: str | None = None) -> str:
    """UserPromptSubmit：任务描述 + 验收标准 + 当前阶段要求。"""
    status = task.get("status", "TODO")
    lines = [
        "<keystone-task>",
        f"# 当前任务：{task.get('code')} {task.get('title', '')}",
        f"- 状态：{status}",
    ]
    if task.get("pending_confirmation"):
        lines.append(
            "- 性质：待确认任务（由你的 prompt 自动登记，非正式任务）。"
            "若确属开发任务请沿状态机推进；若只是提问可忽略或删除该任务目录。"
        )
    desc = (task.get("description_md") or "").strip()
    if desc:
        lines += ["", "## 任务描述", desc]
    criteria = task.get("acceptance_criteria") or []
    if criteria:
        lines += ["", "## 验收标准"]
        lines += [f"- [ ] {c}" for c in criteria]
    lines += ["", "## 当前阶段要求", policy.STAGE_REQUIREMENTS.get(status, "")]
    if project.get("test_command"):
        lines += ["", f"验证命令：`{project['test_command']}`"]
    if note:
        lines += ["", f"> {note}"]
    lines += ["", "</keystone-task>"]
    return "\n".join(lines)


def render_task_selection(tasks: list[dict]) -> str:
    """无活动任务且存在可选任务时，要求用户选择；不自动创建正式任务。"""
    lines = [
        "<keystone-task>",
        "# Keystone：当前会话没有绑定任务",
        "",
        "项目里已有以下任务，请用户明确选择其一（在 prompt 中给出任务编号，如 `TASK-001`），"
        "或用 `keystone task create` 新建任务。不要在未确认前修改代码。",
        "",
    ]
    for t in tasks:
        lines.append(f"- {t.get('code')} [{t.get('status')}] {t.get('title', '')}")
    lines += ["", "</keystone-task>"]
    return "\n".join(lines)


def render_task_missing(code: str, tasks: list[dict]) -> str:
    lines = [
        "<keystone-task>",
        f"# Keystone：任务 {code} 不存在",
        "",
        "用户 prompt 中提到的任务编号未找到。可用任务：",
        "",
    ]
    if tasks:
        lines += [f"- {t.get('code')} [{t.get('status')}] {t.get('title', '')}" for t in tasks]
    else:
        lines.append("（项目暂无任务，可用 `keystone task create` 创建）")
    lines += ["", "</keystone-task>"]
    return "\n".join(lines)


def render_stop_checklist(project: dict, task: dict | None) -> str:
    """Stop：结束前检查清单（提醒与强制模式共用文案主体）。"""
    lines = ["<keystone-checklist>", "# Keystone：结束前检查清单"]
    if task is not None:
        status = task.get("status", "TODO")
        lines += [
            "",
            f"当前任务：{task.get('code')} {task.get('title', '')}（{status}）",
        ]
        if status in PRE_CONFIRM_STATUSES:
            lines.append("该任务尚未完成计划确认。")
        elif status == "IMPLEMENTING":
            lines.append("任务仍处于开发中。")
        elif status == "VERIFYING":
            lines.append("任务验证尚未完成。")
    verify_cmd = (
        f"（`{project['test_command']}`）" if project.get("test_command") else ""
    )
    lines += [
        "",
        "结束前请逐项确认：",
        "1. 是否完成任务目标；",
        "2. 本次修改了哪些文件，是否都在任务边界内；",
        f"3. 是否执行了适用的验证命令{verify_cmd}；",
        "4. 验证结果如何；",
        "5. 未解决的问题和潜在风险。",
    ]
    if task is not None and task.get("status") == "VERIFYING":
        lines += [
            "",
            "验证完成后用 `keystone task advance` 推进到 COMPLETED 再结束；"
            "无法验证时请明确说明原因。",
        ]
    lines += ["", "</keystone-checklist>"]
    return "\n".join(lines)


def render_pre_compact(project: dict, task: dict | None, specs: list[tuple[str, str]]) -> str:
    """PreCompact：上下文压缩前恢复关键信息（精简版）。"""
    lines = [
        "<keystone-context>",
        "# Keystone：上下文压缩恢复摘要",
        "",
        f"- 当前项目：{_fmt_project_line(project)}",
    ]
    if project.get("test_command"):
        lines.append(f"- 验证命令：`{project['test_command']}`")
    spec_names = [SPEC_LABELS.get(c, c) for c, _ in specs]
    if spec_names:
        lines.append(f"- 项目规范：{ '、'.join(spec_names) }（完整内容见 .keystone/specs/，需遵守）")
    if task is not None:
        status = task.get("status", "TODO")
        lines += [
            f"- 当前任务：{task.get('code')} {task.get('title', '')}（{status}）",
            f"- 阶段要求：{policy.STAGE_REQUIREMENTS.get(status, '')}",
        ]
        criteria = task.get("acceptance_criteria") or []
        if criteria:
            lines.append("- 验收标准：" + "；".join(criteria))
    else:
        lines.append("- 当前任务：无（会话未绑定任务）")
    lines += ["", "</keystone-context>"]
    return "\n".join(lines)
