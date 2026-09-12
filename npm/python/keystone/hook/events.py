"""七个 hook 事件的处理逻辑。

handler 约定：接收 (fields, layout)，返回输出 dict 或 None（None = 不输出、
合法 no-op）。异常由分发器统一兜底：控制类 fail-open、记录类 fail-silent，
最终都表现为"无输出、退出码 0"，绝不影响 CodeBuddy 正常使用。
"""

from __future__ import annotations

from pathlib import Path

from keystone.core import context, policy, taskmatch
from keystone.core.statemachine import PRE_CONFIRM_STATUSES
from keystone.hook import output
from keystone.store import sessions, specs, tasks
from keystone.store.project import load_project
from keystone.store.layout import KeystoneLayout


def session_start(fields: dict, layout: KeystoneLayout) -> dict | None:
    """注入项目基础上下文：资料 + 规范 + 禁止事项（相对静态，不含动态任务）。"""
    project = load_project(layout)
    text = context.render_session_start(project, specs.load_specs(layout))
    return output.additional_context("SessionStart", text)


def user_prompt_submit(fields: dict, layout: KeystoneLayout) -> dict | None:
    """核心事件：解析会话任务绑定，注入任务描述、验收标准与阶段要求。

    任务策略（需求文档 §3.2）：
    - prompt 明确给出任务编号 → 切换/绑定到该任务（编号不存在则提示）；
    - 会话已有绑定 → 继续使用；
    - 无绑定但存在未完成任务 → 要求用户选择，不自动创建正式任务；
    - 项目无任何任务 → 登记一条"待确认任务"（pending_confirmation）。
    """
    project = load_project(layout)
    session_id = fields["session_id"]
    prompt = fields["prompt"]
    all_tasks = tasks.list_tasks(layout)

    codes = taskmatch.extract_task_codes(prompt)
    if codes:
        code = codes[0]
        task = tasks.find_task(layout, code)
        if task is None:
            return output.additional_context(
                "UserPromptSubmit", context.render_task_missing(code, all_tasks)
            )
        if session_id:
            sessions.bind_session(layout, session_id, code)
        return output.additional_context(
            "UserPromptSubmit",
            context.render_task(project, task, note=f"已按 prompt 中的编号绑定任务 {code}"),
        )

    bound_code = sessions.get_binding(layout, session_id) if session_id else None
    if bound_code:
        task = tasks.find_task(layout, bound_code)
        if task is not None:
            return output.additional_context("UserPromptSubmit", context.render_task(project, task))

    active = [t for t in all_tasks if t.get("status") != "COMPLETED"]
    if active:
        return output.additional_context("UserPromptSubmit", context.render_task_selection(active))

    task = tasks.create_task(
        layout,
        title=_derive_title(prompt),
        description=prompt,
        status="TODO",
        pending_confirmation=True,
    )
    if session_id:
        sessions.bind_session(layout, session_id, task["code"])
    return output.additional_context(
        "UserPromptSubmit",
        context.render_task(
            project,
            task,
            note="已根据 prompt 登记待确认任务；确认是正式任务后请沿状态机推进，非任务请求可忽略",
        ),
    )


def _derive_title(prompt: str) -> str:
    first_line = prompt.strip().splitlines()[0].strip() if prompt.strip() else ""
    title = first_line[:40] or "未命名待确认任务"
    return title


def pre_tool_use(fields: dict, layout: KeystoneLayout) -> dict | None:
    """流程控制（第一版范围）：
    1. 保护 .keystone 裁判状态不被 AI 直接改写（task.json / .state / project.json）；
    2. 计划确认前（TODO/PLANNING）禁止写文件；
    3. 任务 COMPLETED 后禁止继续修改，需先重新打开。
    """
    project = load_project(layout)
    if not policy.is_write_tool(fields["tool_name"]):
        return None

    target = policy.extract_target_path(fields["tool_input"])
    if target and _is_keystone_internal(Path(target), layout):
        return output.deny_pre_tool_use(
            "禁止直接修改 .keystone 内部状态文件（任务状态、会话绑定、项目配置）。"
            "推进任务状态请使用 keystone task 命令（如 `keystone task advance TASK-001`）。"
        )

    session_id = fields["session_id"]
    bound = sessions.get_binding(layout, session_id) if session_id else None
    if not bound:
        # 无任务时不拦截：用户可能只是提问。strict 模式（预留）收紧。
        if project.get("policy_mode") == "strict":
            return output.deny_pre_tool_use(
                "strict 模式：当前会话没有绑定任务，禁止写入文件。"
                "请先绑定或创建任务（在 prompt 中给出任务编号，或 keystone task create）。"
            )
        return None

    task = tasks.find_task(layout, bound)
    if task is None:
        return None  # 绑定悬空时放行，避免卡死流程（fail-open）

    status = task["status"]
    if status in PRE_CONFIRM_STATUSES:
        return output.deny_pre_tool_use(
            f"任务 {bound} 处于 {status}（计划确认前），禁止写入文件。"
            "请先完成需求分析与方案，经用户确认后用 "
            f"`keystone task advance {bound}` 推进到 PLAN_CONFIRMED 再动手。"
        )
    if status == "COMPLETED":
        return output.deny_pre_tool_use(
            f"任务 {bound} 已完成，禁止继续修改。如确需返工，请先用 "
            f"`keystone task reopen {bound}` 重新打开任务。"
        )
    return None


def _is_keystone_internal(target: Path, layout: KeystoneLayout) -> bool:
    """判断目标路径是否落在受保护的 keystone 状态文件上。"""
    try:
        rel = target.expanduser().resolve().relative_to(layout.dir.resolve())
    except (ValueError, OSError):
        return False
    parts = rel.parts
    if not parts:
        return False
    if parts[0] == ".state" or parts[0] == "project.json":
        return True
    return parts[0] == "tasks" and parts[-1] == "task.json"


def post_tool_use(fields: dict, layout: KeystoneLayout) -> dict | None:
    """记录元数据事件：工具名/成败/会话/任务/时间。绝不记录内容类信息。"""
    session_id = fields["session_id"]
    sessions.append_event(
        layout,
        {
            "event": "PostToolUse",
            "tool_name": fields["tool_name"],
            "success": _derive_success(fields),
            "session_id": session_id,
            "task": sessions.get_binding(layout, session_id) if session_id else None,
        },
    )
    return None


def _derive_success(fields: dict):
    explicit = fields["raw"].get("success")
    if isinstance(explicit, bool):
        return explicit
    response = fields["tool_response"]
    if isinstance(response, dict):
        if isinstance(response.get("is_error"), bool):
            return not response["is_error"]
        if isinstance(response.get("success"), bool):
            return response["success"]
    return None


def stop(fields: dict, layout: KeystoneLayout) -> dict | None:
    """结束前检查。stop_hook_active 为真时立即放行，避免无限循环。"""
    if fields["stop_hook_active"]:
        return None
    project = load_project(layout)
    session_id = fields["session_id"]
    bound = sessions.get_binding(layout, session_id) if session_id else None
    task = tasks.find_task(layout, bound) if bound else None
    if task is None:
        return None  # 无活动任务，无需检查清单
    text = context.render_stop_checklist(project, task)
    if project.get("stop_mode") == "enforce" and task.get("status") != "COMPLETED":
        return output.block_stop(text)
    return output.additional_context("Stop", text)


def session_end(fields: dict, layout: KeystoneLayout) -> dict | None:
    """会话结束记录。不作为任务完成的依据。"""
    session_id = fields["session_id"]
    sessions.append_event(
        layout,
        {
            "event": "SessionEnd",
            "reason": fields["reason"] or "unknown",
            "session_id": session_id,
            "task": sessions.get_binding(layout, session_id) if session_id else None,
        },
    )
    return None


def pre_compact(fields: dict, layout: KeystoneLayout) -> dict | None:
    """上下文压缩前恢复关键信息。"""
    project = load_project(layout)
    session_id = fields["session_id"]
    bound = sessions.get_binding(layout, session_id) if session_id else None
    task = tasks.find_task(layout, bound) if bound else None
    text = context.render_pre_compact(project, task, specs.load_specs(layout))
    return output.additional_context("PreCompact", text)
