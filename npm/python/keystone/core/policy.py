"""流程策略：工具名集合、写操作判定、keystone 内部文件保护。

Hook 看到的 tool_name 因平台而异（CodeBuddy / Claude Code 风格、Cursor 风格、
Codeium 风格混用），这里统一做小写归一后匹配。
"""

from __future__ import annotations

# 写文件类工具（PreToolUse 流程控制的管辖范围）
WRITE_TOOLS = frozenset(
    {
        "write",
        "edit",
        "multiedit",
        "notebookedit",
        "write_to_file",
        "replace_in_file",
        "apply_patch",
        "str_replace_editor",
        "str_replace_based_edit_tool",
        "create_file",
        "edit_file",
        "save_file",
    }
)

# 执行命令类工具（第一版仅用于元数据归类；strict 模式预留控制能力）
EXEC_TOOLS = frozenset(
    {
        "bash",
        "execute_command",
        "run_command",
        "run_terminal_cmd",
        "terminal",
        "shell",
    }
)

# tool_input 中可能承载目标路径的字段名
PATH_INPUT_KEYS = (
    "file_path",
    "filePath",
    "path",
    "target_file",
    "targetFile",
    "notebook_path",
    "notebookPath",
)


def normalize_tool_name(name: str) -> str:
    """归一化工具名：去空白、转小写、连字符归一为下划线。"""
    return (name or "").strip().lower().replace("-", "_")


def is_write_tool(tool_name: str) -> bool:
    return normalize_tool_name(tool_name) in WRITE_TOOLS


def is_exec_tool(tool_name: str) -> bool:
    return normalize_tool_name(tool_name) in EXEC_TOOLS


def extract_target_path(tool_input: object) -> str | None:
    """从工具入参中尽力提取目标文件路径（找不到返回 None）。"""
    if not isinstance(tool_input, dict):
        return None
    for key in PATH_INPUT_KEYS:
        value = tool_input.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


POLICY_MODES = ("permissive", "strict")

# 各任务阶段注入给 CodeBuddy 的执行要求（需求文档 §4 状态约束表）
STAGE_REQUIREMENTS = {
    "TODO": (
        "任务尚未开始。请先阅读任务描述与验收标准；"
        "如需实施，先将任务推进到 PLANNING（keystone task advance），"
        "并在计划确认前不要修改任何文件。"
    ),
    "PLANNING": (
        "当前处于计划阶段：先分析需求、影响范围、实施步骤和验证方案，"
        "不要修改任何代码或文件。方案经用户确认后，用 `keystone task advance` "
        "将任务推进到 PLAN_CONFIRMED。"
    ),
    "PLAN_CONFIRMED": (
        "计划已确认，允许修改代码。实施时遵守下方注入的项目规范，"
        "并把修改范围限制在任务边界内。完成后推进到 IMPLEMENTING。"
    ),
    "IMPLEMENTING": (
        "当前处于开发阶段：遵守项目编码规范，仅做与任务目标相关的修改。"
        "实现完成后推进到 VERIFYING，并执行适用的验证命令。"
    ),
    "VERIFYING": (
        "当前处于验证阶段：执行项目适用的验证命令（见下方），"
        "如实报告验证结果；无法验证时明确说明原因。"
        "验证通过后推进到 COMPLETED；验证不通过可用 advance 打回 IMPLEMENTING。"
    ),
    "COMPLETED": (
        "任务已完成。允许结束会话或开始新工作；"
        "如需继续修改，请先重新打开任务（keystone task reopen）。"
    ),
}
