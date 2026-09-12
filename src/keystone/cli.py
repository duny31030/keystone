"""keystone 命令行入口。

    keystone init          在目标项目初始化 .keystone/ 并注册 CodeBuddy hooks
    keystone task ...      任务管理（create/list/show/advance/complete/reopen）
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from keystone import scaffold
from keystone.core import statemachine
from keystone.errors import KeystoneError
from keystone.store import tasks as task_store
from keystone.store.layout import find_layout
from keystone.store.project import make_project


def _interactive_default(prompt: str, default: str, enabled: bool = True) -> str:
    """TTY 下向用户要一个值，非 TTY 或显式 -y 时直接用默认值。"""
    if enabled and sys.stdin.isatty():
        answer = input(f"{prompt} [{default}]: ").strip()
        return answer or default
    return default


def cmd_init(args: argparse.Namespace) -> int:
    target = Path(args.dir).expanduser().resolve()
    if not target.is_dir():
        print(f"keystone init: 目录不存在：{target}", file=sys.stderr)
        return 1

    interactive = not args.yes
    detected = scaffold.detect_language(target)
    language = args.lang
    if language is None:
        language = detected or _interactive_default("项目语言 (java/python)", "python", interactive)
    if language not in ("java", "python"):
        print(f"keystone init: 暂不支持语言 {language!r}（P0 支持 java / python）", file=sys.stderr)
        return 1

    default_name = target.name
    name = args.name or _interactive_default("项目名称", default_name, interactive)

    project = make_project(
        slug=name.lower().replace("_", "-"),
        name=name,
        language=language,
        framework=args.framework,
        build_tool=args.build_tool,
        build_command=args.build_command,
        test_command=args.test_command,
        stop_mode=args.stop_mode,
        policy_mode=args.policy_mode,
    )

    layout, created = scaffold.scaffold_keystone(target, project)
    if not created:
        print(f"keystone init: {layout.dir} 已存在，保留现有配置（project.json 未改动）")

    settings_path, existed = scaffold.write_codebuddy_settings(target, args.hook_command)
    gitignore_changed = scaffold.ensure_gitignore(target)

    print(f"✓ 项目：{project['name']}（{project['language']}"
          f"{(' / ' + project['framework']) if project['framework'] else ''}）")
    print(f"✓ 测试命令：{project['test_command'] or '（未配置）'}")
    print(f"✓ 已生成 {layout.dir}" + ("" if created else "（已存在，未覆盖）"))
    print(f"✓ 已{'更新' if existed else '创建'} {settings_path}（hook 命令：{args.hook_command} <event>）")
    print("✓ .gitignore 已追加 .keystone/.state/" if gitignore_changed else "· .gitignore 已包含忽略项，未改动")
    print()
    print("下一步：")
    print("  1. 编辑 .keystone/specs/ 下的规范文件（按项目实际填写）")
    print(f"  2. keystone task create \"<任务标题>\" 创建第一个任务")
    print("  3. 在 CodeBuddy 中打开项目，hook 会在会话开始/提交 prompt 时自动注入上下文")
    return 0


def _require_layout():
    layout = find_layout()
    if layout is None or not layout.initialized:
        print("keystone: 当前目录不是 keystone 项目（未找到 .keystone/project.json）。\n"
              "先在项目根目录执行 keystone init。", file=sys.stderr)
        raise SystemExit(1)
    return layout


def cmd_task(args: argparse.Namespace) -> int:
    layout = _require_layout()
    try:
        return _dispatch_task(args, layout)
    except KeystoneError as exc:
        print(f"keystone task: {exc}", file=sys.stderr)
        return 1


def _dispatch_task(args: argparse.Namespace, layout) -> int:
    action = args.task_command
    if action == "create":
        criteria = []
        for chunk in args.accept or []:
            criteria += [c.strip() for c in chunk.replace("；", ";").split(";") if c.strip()]
        task = task_store.create_task(
            layout,
            title=args.title,
            description=args.description or "",
            acceptance_criteria=criteria,
            pending_confirmation=args.pending,
        )
        print(f"✓ 已创建 {task['code']} [{task['status']}] {task['title']}")
        print(f"  目录：{layout.task_dir(task['code'])}")
        return 0

    if action == "list":
        all_tasks = task_store.list_tasks(layout)
        if args.status:
            all_tasks = [t for t in all_tasks if t.get("status") == args.status]
        if not all_tasks:
            print("（暂无任务，用 keystone task create 创建）")
            return 0
        for t in all_tasks:
            flag = " (待确认)" if t.get("pending_confirmation") else ""
            print(f"{t['code']}  [{t['status']:>14}]  {t.get('title', '')}{flag}")
        return 0

    if action == "show":
        t = task_store.load_task(layout, args.code)
        print(f"{t['code']} [{t['status']}] {t.get('title', '')}")
        if t.get("pending_confirmation"):
            print("性质：待确认任务")
        if t.get("description_md", "").strip():
            print()
            print(t["description_md"].strip())
        print()
        print("流转记录：")
        for tr in t.get("transitions", []):
            print(f"  {tr.get('at', '?')}  {tr.get('from') or '—'} → {tr.get('to')}"
                  + (f"  ({tr.get('reason')})" if tr.get("reason") else ""))
        return 0

    if action == "advance":
        current = task_store.load_task(layout, args.code)
        target_status = args.to or statemachine.next_status(current["status"])
        t = task_store.transition_task(layout, args.code, target_status, reason=args.reason)
        print(f"✓ {t['code']}: {current['status']} → {t['status']}")
        return 0

    if action == "complete":
        t = task_store.transition_task(layout, args.code, "COMPLETED", reason=args.reason)
        print(f"✓ {t['code']} 已完成（COMPLETED）")
        return 0

    if action == "reopen":
        t = task_store.transition_task(layout, args.code, "IMPLEMENTING", reason=args.reason or "reopen")
        print(f"✓ {t['code']} 已重新打开（{t['status']}）")
        return 0

    print(f"keystone task: 未知子命令 {action!r}", file=sys.stderr)
    return 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="keystone",
        description="Keystone：CodeBuddy 流程与上下文增强层（本地文件版）",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_init = sub.add_parser("init", help="初始化 .keystone/ 并注册 CodeBuddy hooks")
    p_init.add_argument("--dir", default=".", help="目标项目根目录（默认当前目录）")
    p_init.add_argument("--lang", choices=("java", "python"), default=None, help="项目语言（默认自动探测）")
    p_init.add_argument("--name", default=None, help="项目名称（默认目录名）")
    p_init.add_argument("--framework", default=None, help="框架覆盖（如 spring-boot / fastapi）")
    p_init.add_argument("--build-tool", default=None, help="构建工具覆盖（如 maven / pip）")
    p_init.add_argument("--build-command", default=None, help="构建命令覆盖")
    p_init.add_argument("--test-command", default=None, help="测试命令覆盖（如 mvn test / pytest）")
    p_init.add_argument("--stop-mode", choices=("reminder", "enforce"), default="reminder",
                        help="Stop hook 模式：reminder=仅提醒（默认），enforce=未完成则阻止结束")
    p_init.add_argument("--policy-mode", choices=("permissive", "strict"), default="permissive",
                        help="strict 下未绑定任务时也禁止写文件（默认 permissive）")
    p_init.add_argument("--hook-command", default="keystone-hook",
                        help="hook 注册的命令前缀（需包含 keystone 字样以便幂等合并），如 'python3 -m keystone.hook'")
    p_init.add_argument("-y", "--yes", action="store_true",
                        help="非交互模式：缺失信息一律用默认值")

    p_task = sub.add_parser("task", help="任务管理")
    task_sub = p_task.add_subparsers(dest="task_command", required=True)

    p_create = task_sub.add_parser("create", help="创建任务")
    p_create.add_argument("title")
    p_create.add_argument("-d", "--description", default="", help="任务描述（写入 prd.md）")
    p_create.add_argument("-a", "--accept", action="append", default=[],
                          help="验收标准，可多次传入或用分号分隔")
    p_create.add_argument("--pending", action="store_true", help="标记为待确认任务")

    p_list = task_sub.add_parser("list", help="任务列表")
    p_list.add_argument("--status", default=None, help="按状态过滤")

    p_show = task_sub.add_parser("show", help="任务详情")
    p_show.add_argument("code")

    p_advance = task_sub.add_parser("advance", help="沿状态机推进（或 --to 指定合法目标状态）")
    p_advance.add_argument("code")
    p_advance.add_argument("--to", default=None, help="目标状态（缺省沿主链走下一步）")
    p_advance.add_argument("--reason", default="", help="流转原因（记录审计）")

    p_complete = task_sub.add_parser("complete", help="完成任务（要求当前处于 VERIFYING）")
    p_complete.add_argument("code")
    p_complete.add_argument("--reason", default="", help="流转原因")

    p_reopen = task_sub.add_parser("reopen", help="重新打开已完成任务（→ IMPLEMENTING）")
    p_reopen.add_argument("code")
    p_reopen.add_argument("--reason", default="", help="流转原因")

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "init":
        return cmd_init(args)
    if args.command == "task":
        return cmd_task(args)
    return 1


if __name__ == "__main__":
    sys.exit(main())
