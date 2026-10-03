"""keystone 命令行入口。

    keystone init          在目标项目初始化 .keystone/ 并注册 CodeBuddy hooks
    keystone task ...      任务管理（create/list/show/advance/complete/reopen）
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from keystone.adapters.registry import get_adapter, supported_platforms
from keystone import scaffold
from keystone.core import statemachine
from keystone.errors import KeystoneError
from keystone.inspection import doctor_findings, hook_commands, inspect_project
from keystone.skills import catalog as skill_catalog
from keystone.store import tasks as task_store
from keystone.store.layout import find_layout
from keystone.store.project import make_project


def _interactive_default(prompt: str, default: str, enabled: bool = True) -> str:
    """TTY 下向用户要一个值，非 TTY 或显式 -y 时直接用默认值。"""
    if enabled and sys.stdin.isatty():
        answer = input(f"{prompt} [{default}]: ").strip()
        return answer or default
    return default


def _render_plan(title: str, changes) -> None:
    print(f"{title}:")
    for change in changes:
        try:
            path = change.path.relative_to(change.path.parents[len(change.path.parents) - 1])
        except ValueError:
            path = change.path
        print(f"{change.action:9} {change.path}")
        if change.diff:
            print(change.diff.rstrip())


def cmd_init(args: argparse.Namespace) -> int:
    target = Path(args.dir).expanduser().resolve()
    if not target.is_dir():
        print(f"keystone init: 目录不存在：{target}", file=sys.stderr)
        return 1
    interactive = not args.yes and not args.dry_run
    language = args.lang or scaffold.detect_language(target) or _interactive_default("项目语言 (java/python)", "python", interactive)
    if language not in ("java", "python"):
        print(f"keystone init: 暂不支持语言 {language!r}（P0 支持 java / python）", file=sys.stderr)
        return 1
    name = args.name or _interactive_default("项目名称", target.name, interactive)
    project = make_project(
        slug=name.lower().replace("_", "-"), name=name, language=language,
        framework=args.framework, build_tool=args.build_tool,
        build_command=args.build_command, test_command=args.test_command,
        stop_mode=args.stop_mode, policy_mode=args.policy_mode,
    )
    try:
        adapter = get_adapter(args.platform)
        plan = scaffold.plan_init(target, project, args.hook_command, args.platform)
    except (OSError, UnicodeDecodeError, ValueError, json.JSONDecodeError) as exc:
        print(f"keystone init: 无法读取现有配置：{exc}", file=sys.stderr)
        return 1
    if args.dry_run:
        _render_plan(f"keystone init --dry-run: {target}", plan.changes)
        print("不会写入文件。")
        return 0
    settings_path, settings_changed, gitignore_changed = scaffold.apply_init_plan(plan, project)
    if not plan.creates_project:
        print(f"keystone init: {plan.layout.dir} 已存在，保留现有配置（project.json 未改动）")
    print(f"✓ 项目：{project['name']}（{project['language']}" + (f" / {project['framework']}" if project['framework'] else "") + "）")
    print(f"✓ 测试命令：{project['test_command'] or '（未配置）'}")
    print(f"✓ 已生成 {plan.layout.dir}" + ("" if plan.creates_project else "（已存在，未覆盖）"))
    print(f"✓ 已{'更新' if settings_changed else '检查'} {settings_path}（{adapter.display_name} hook 命令：{args.hook_command} <event>）")
    print("✓ .gitignore 已追加 .keystone/.state/" if gitignore_changed else "· .gitignore 已包含忽略项，未改动")
    print("\n下一步：")
    print("  1. 编辑 .keystone/specs/ 下的规范文件（按项目实际填写）")
    print("  2. keystone task create \"<任务标题>\" 创建第一个任务")
    print("  3. 在 CodeBuddy 中打开项目，hook 会在会话开始/提交 prompt 时自动注入上下文")
    return 0


def _target_layout(target: Path, platform: str = "codebuddy"):
    info = inspect_project(target, platform)
    layout = info["layout"]
    if layout is None or info["project"].state != "ok":
        print("keystone: 当前目录不是有效的 keystone 项目（未找到或无法读取 .keystone/project.json）。\n"
              "先在项目根目录执行 keystone init。", file=sys.stderr)
        return None, info
    return layout, info


def cmd_status(args: argparse.Namespace) -> int:
    target = Path(args.dir).expanduser().resolve()
    layout, info = _target_layout(target, args.platform)
    if layout is None:
        return 1
    project = info["project"].value
    assert isinstance(project, dict)
    if info["settings"].state not in ("missing", "ok"):
        print("keystone status: .codebuddy/settings.json 无法读取；运行 keystone doctor 查看详情。", file=sys.stderr)
        return 1
    if info["sessions"].state not in ("missing", "ok"):
        print("keystone status: .keystone/.state/sessions.json 无法读取；运行 keystone doctor 查看详情。", file=sys.stderr)
        return 1
    valid_tasks = [view.value for _, view in info["tasks"] if view.state == "ok" and isinstance(view.value, dict)]
    counts = {status: sum(task.get("status") == status for task in valid_tasks) for status in statemachine.STATUSES}
    pending = sum(bool(task.get("pending_confirmation")) for task in valid_tasks)
    active = sum(task.get("status") != "COMPLETED" for task in valid_tasks)
    registered = hook_commands(info["settings"].value, args.platform) if info.get("settings") and info["settings"].state == "ok" else {}
    session_count = len(info["sessions"].value) if info["sessions"].state == "ok" and isinstance(info["sessions"].value, dict) else 0
    event_count = 0
    if layout.events_jsonl.is_file():
        try:
            event_count = len([line for line in layout.events_jsonl.read_text(encoding="utf-8").splitlines() if line.strip()])
        except OSError:
            pass
    print(f"Project: {project.get('name', '<unnamed>')}")
    print(f"Root: {layout.root}")
    print(f"Stack: {project.get('language', '?')} / {project.get('framework') or '-'} / {project.get('build_tool') or '-'}")
    print(f"Policy: {project.get('policy_mode', '?')}    Stop: {project.get('stop_mode', '?')}")
    print(f"Test command: {project.get('test_command') or '（未配置）'}")
    print(f"\nTasks: {len(valid_tasks)} total, {active} active, {counts['COMPLETED']} completed, {pending} pending confirmation")
    print("  " + "  ".join(f"{status}: {counts[status]}" for status in statemachine.STATUSES))
    registered_events = sum(bool(registered.get(event)) for event in scaffold.EXPECTED_EVENTS)
    print(f"Hooks: {registered_events}/{len(scaffold.EXPECTED_EVENTS)} verified event registrations in .codebuddy/settings.json")
    print(f"Runtime: {session_count} session bindings, {event_count} SessionEnd records")
    return 0


def cmd_doctor(args: argparse.Namespace) -> int:
    target = Path(args.dir).expanduser().resolve()
    findings = doctor_findings(target, args.platform)
    totals = {level: 0 for level in ("PASS", "WARN", "FAIL")}
    for level, name, detail in findings:
        totals[level] += 1
        print(f"{level:4} {name:12} {detail}")
    print(f"\n{totals['PASS']} pass, {totals['WARN']} warn, {totals['FAIL']} fail")

    if not args.fix:
        return 1 if totals["FAIL"] else 0

    # --fix 模式：尝试修复可安全修复的问题
    from keystone.inspection import doctor_fix
    fixed = doctor_fix(target, args.hook_command, args.platform)
    if not fixed:
        print("\n· 无可修复的问题")
        return 1 if totals["FAIL"] else 0

    print("\n已修复：")
    for item in fixed:
        print(f"  ✓ {item}")

    # 修复后重新运行 doctor
    print("\n修复后重新检查：")
    findings = doctor_findings(target, args.platform)
    totals = {level: 0 for level in ("PASS", "WARN", "FAIL")}
    for level, name, detail in findings:
        totals[level] += 1
        print(f"{level:4} {name:12} {detail}")
    print(f"\n{totals['PASS']} pass, {totals['WARN']} warn, {totals['FAIL']} fail")
    return 1 if totals["FAIL"] else 0


def cmd_uninstall(args: argparse.Namespace) -> int:
    target = Path(args.dir).expanduser().resolve()
    if not target.is_dir():
        print(f"keystone uninstall: 目录不存在：{target}", file=sys.stderr)
        return 1
    if args.purge and not args.dry_run and not args.yes:
        if not sys.stdin.isatty():
            print("keystone uninstall: 非交互环境执行 --purge 必须同时传 --yes。", file=sys.stderr)
            return 1
        if input("将删除 .keystone/ 内的项目配置、规范、任务和运行态。继续？[y/N] ").strip().lower() not in {"y", "yes"}:
            print("已取消。")
            return 1
    try:
        plan = scaffold.plan_uninstall(target, args.purge, args.platform)
    except (OSError, UnicodeDecodeError, ValueError, json.JSONDecodeError) as exc:
        print(f"keystone uninstall: 无法读取现有配置：{exc}", file=sys.stderr)
        return 1
    if args.dry_run:
        _render_plan(f"keystone uninstall --dry-run: {target}", plan.changes)
        print("不会写入文件。")
        return 0
    scaffold.apply_uninstall_plan(plan)
    changed = [change for change in plan.changes if change.action in {"UPDATE", "REMOVE"}]
    if not changed:
        print("· 未发现 Keystone 配置，未改动。")
    else:
        print("✓ 已移除 Keystone Hook 注册；.keystone/ 项目资料已保留。" if not args.purge else "✓ 已移除 Keystone 注册并删除 .keystone/ 项目资料。")
    return 0


def _require_layout():
    layout = find_layout()
    if layout is None or not layout.initialized:
        print("keystone: 当前目录不是 keystone 项目（未找到 .keystone/project.json）。\n"
              "先在项目根目录执行 keystone init。", file=sys.stderr)
        raise SystemExit(1)
    return layout


def cmd_events(args: argparse.Namespace) -> int:
    target = Path(args.dir).expanduser().resolve()
    layout = find_layout(target)
    if layout is None:
        print("keystone: 当前目录不是 keystone 项目（未找到 .keystone/）", file=sys.stderr)
        return 1

    events_path = layout.events_jsonl
    if not events_path.is_file():
        print("（暂无事件记录）")
        return 0

    lines = events_path.read_text(encoding="utf-8").strip().splitlines()
    events = []
    for line in lines:
        try:
            event = json.loads(line)
            events.append(event)
        except json.JSONDecodeError:
            continue  # 跳过损坏行

    # 过滤
    if args.task:
        events = [e for e in events if e.get("task") == args.task]
    if args.session:
        events = [e for e in events if e.get("session_id") == args.session]
    if args.event:
        events = [e for e in events if e.get("event") == args.event]

    if not events:
        print("（暂无匹配的事件记录）")
        return 0

    # 表头
    print(f"{'时间':<20} {'事件':<15} {'会话':<40} {'任务':<10} {'原因':<15}")
    print("-" * 100)
    for e in events:
        at = e.get("at", "?")
        event = e.get("event", "?")
        session = e.get("session_id", "?")[:38]
        task = e.get("task") or "-"
        reason = e.get("reason", "-")
        print(f"{at:<20} {event:<15} {session:<40} {task:<10} {reason:<15}")
    return 0


def cmd_skills(args: argparse.Namespace) -> int:
    root = Path(args.dir).expanduser().resolve()
    if not root.is_dir():
        print(f"keystone skills: 目录不存在：{root}", file=sys.stderr)
        return 1

    if args.skills_command == "list":
        print("Keystone workflow skills:")
        for skill in skill_catalog.SKILL_NAMES:
            installed = []
            for target, relative in skill_catalog.TARGETS.items():
                if (root / relative / skill / "SKILL.md").is_file():
                    installed.append(target)
            marker = ", ".join(installed) if installed else "未安装"
            print(f"  {skill:<20} {marker}")
        return 0

    if args.skills_command == "install":
        try:
            changes = skill_catalog.plan_install(root, args.platform, args.force)
        except ValueError as exc:
            print(f"keystone skills: {exc}", file=sys.stderr)
            return 1
        if not changes:
            print("· auto 未检测到已存在的平台目录；未写入任何 Skill。使用 --platform all 或指定平台。")
            return 0
        for change in changes:
            print(f"{change.action:<10} {change.target}" + (f" ({change.detail})" if change.detail else ""))
        if args.dry_run:
            print("不会写入文件。")
            return 0
        conflicts = skill_catalog.apply_install(changes)
        if conflicts:
            print("keystone skills: 存在冲突，未写入任何文件。使用 --force 覆盖。", file=sys.stderr)
            return 1
        print("✓ Keystone workflow skills 已安装")
        return 0

    print(f"keystone skills: 未知子命令 {args.skills_command!r}", file=sys.stderr)
    return 1


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
            plan_flag = " [plan]" if (layout.task_dir(t["code"]) / "plan.md").is_file() else ""
            print(f"{t['code']}  [{t['status']:>14}]  {t.get('title', '')}{flag}{plan_flag}")
        return 0

    if action == "show":
        t = task_store.load_task(layout, args.code)
        print(f"{t['code']} [{t['status']}] {t.get('title', '')}")
        if t.get("pending_confirmation"):
            print("性质：待确认任务")
        if t.get("description_md", "").strip():
            print()
            print(t["description_md"].strip())
        plan_status = "已存在" if t.get("has_plan") else "缺失"
        print(f"\n计划文件：{plan_status}（{t['plan_path']}）")
        print()
        print("流转记录：")
        for tr in t.get("transitions", []):
            print(f"  {tr.get('at', '?')}  {tr.get('from') or '—'} → {tr.get('to')}"
                  + (f"  ({tr.get('reason')})" if tr.get("reason") else ""))
        return 0

    if action == "plan":
        path = task_store.write_plan(layout, args.code)
        print(f"✓ 已生成计划模板：{path}")
        print("  填写后运行 keystone task advance 推进到 PLAN_CONFIRMED")
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
    p_init.add_argument("--platform", choices=supported_platforms(), default="codebuddy", help="Hook 平台（默认 codebuddy）")
    p_init.add_argument("-y", "--yes", action="store_true",
                        help="非交互模式：缺失信息一律用默认值")
    p_init.add_argument("--dry-run", action="store_true", help="预览将要创建或更新的文件，不写入")

    p_status = sub.add_parser("status", help="显示项目、任务和本地注册摘要")
    p_status.add_argument("--dir", default=".", help="项目目录（默认当前目录，可从子目录向上定位）")
    p_status.add_argument("--platform", choices=supported_platforms(), default="codebuddy", help="检查的 Hook 平台（默认 codebuddy）")

    p_doctor = sub.add_parser("doctor", help="检查本地 Keystone 配置健康状态")
    p_doctor.add_argument("--dir", default=".", help="项目目录（默认当前目录，可从子目录向上定位）")
    p_doctor.add_argument("--platform", choices=supported_platforms(), default="codebuddy", help="检查的 Hook 平台（默认 codebuddy）")
    p_doctor.add_argument("--fix", action="store_true", help="自动修复可安全修复的问题")
    p_doctor.add_argument("--hook-command", default="keystone-hook", help="hook 注册的命令前缀")

    p_uninstall = sub.add_parser("uninstall", help="移除 Keystone Hook 注册")
    p_uninstall.add_argument("--dir", default=".", help="目标项目目录（默认当前目录）")
    p_uninstall.add_argument("--platform", choices=supported_platforms(), default="codebuddy", help="移除的 Hook 平台（默认 codebuddy）")
    p_uninstall.add_argument("--dry-run", action="store_true", help="预览卸载变更，不写入")
    p_uninstall.add_argument("--purge", action="store_true", help="同时删除 .keystone/ 项目资料")
    p_uninstall.add_argument("-y", "--yes", action="store_true", help="确认 --purge（非交互环境必需）")

    p_events = sub.add_parser("events", help="查看本地事件记录")
    p_events.add_argument("--dir", default=".", help="项目目录（默认当前目录）")
    p_events.add_argument("--task", default=None, help="按任务过滤（如 TASK-001）")
    p_events.add_argument("--session", default=None, help="按会话 ID 过滤")
    p_events.add_argument("--event", default=None, help="按事件类型过滤（如 SessionEnd）")

    p_skills = sub.add_parser("skills", help="管理 Keystone workflow skills")
    skills_sub = p_skills.add_subparsers(dest="skills_command", required=True)
    p_skills_list = skills_sub.add_parser("list", help="显示可用 Skills 和当前安装状态")
    p_skills_list.add_argument("--dir", default=".", help="目标项目目录（默认当前目录）")
    p_skills_install = skills_sub.add_parser("install", help="安装 workflow skills")
    p_skills_install.add_argument("--dir", default=".", help="目标项目目录（默认当前目录）")
    p_skills_install.add_argument("--platform", choices=("auto", "all", "agents", "claude", "codebuddy", "zcode", "codex", "pi"), default="auto")
    p_skills_install.add_argument("--dry-run", action="store_true", help="预览安装变更，不写入")
    p_skills_install.add_argument("--force", action="store_true", help="覆盖同名但内容不同的 Skill")

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

    p_plan = task_sub.add_parser("plan", help="生成结构化计划模板 plan.md")
    p_plan.add_argument("code")

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
    if args.command == "status":
        return cmd_status(args)
    if args.command == "doctor":
        return cmd_doctor(args)
    if args.command == "uninstall":
        return cmd_uninstall(args)
    if args.command == "events":
        return cmd_events(args)
    if args.command == "skills":
        return cmd_skills(args)
    return 1


if __name__ == "__main__":
    sys.exit(main())
