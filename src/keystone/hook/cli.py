"""keystone-hook 命令入口：事件分发 + 统一异常兜底。

用法：keystone-hook <event>
事件名接受 kebab-case（session-start）或 PascalCase（SessionStart）。
"""

from __future__ import annotations

import sys

from keystone.adapters.registry import get_adapter, supported_platforms
from keystone.hook import events, input as hook_input, output
from keystone.store import layout as layout_mod

# kebab-case → PascalCase 事件名
EVENT_ALIASES = {
    "session-start": "SessionStart",
    "user-prompt-submit": "UserPromptSubmit",
    "pre-tool-use": "PreToolUse",
    "stop": "Stop",
    "session-end": "SessionEnd",
}

EVENT_HANDLERS = {
    "SessionStart": events.session_start,
    "UserPromptSubmit": events.user_prompt_submit,
    "PreToolUse": events.pre_tool_use,
    "Stop": events.stop,
    "SessionEnd": events.session_end,
}

_PLATFORMS = "|".join(supported_platforms())
_EVENTS = "|".join(alias for alias in EVENT_ALIASES)
USAGE = f"usage: keystone-hook [--platform {_PLATFORMS}] <{_EVENTS}>"


def _parse_args(args: list[str]) -> tuple[str, str] | None:
    platform = "codebuddy"
    if len(args) >= 3 and args[0] == "--platform":
        platform = args[1]
        args = args[2:]
    if len(args) != 1:
        return None
    return platform, args[0]


def resolve_event(name: str) -> str | None:
    """事件名归一：接受 kebab-case（session-start）、PascalCase（SessionStart）、
    无连字符小写（sessionstart）等写法。"""
    normalized = (name or "").strip().lower().replace("_", "-").replace(" ", "-")
    if normalized in EVENT_ALIASES:
        return EVENT_ALIASES[normalized]
    flat = normalized.replace("-", "")
    for kebab, canonical in EVENT_ALIASES.items():
        if kebab.replace("-", "") == flat:
            return canonical
    return None


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    parsed = _parse_args(args)
    if parsed is None:
        print(USAGE, file=sys.stderr)
        return 1
    platform, event_arg = parsed
    try:
        adapter = get_adapter(platform)
    except ValueError:
        print(f"keystone-hook: 不支持的平台 {platform!r}\n{USAGE}", file=sys.stderr)
        return 1
    event = resolve_event(event_arg)
    handler = EVENT_HANDLERS.get(event) if event else None
    if handler is None:
        print(f"keystone-hook: 未知事件 {event_arg!r}\n{USAGE}", file=sys.stderr)
        return 1
    if event not in adapter.expected_events:
        print(f"keystone-hook: {adapter.display_name} adapter 不支持事件 {event}\n{USAGE}", file=sys.stderr)
        return 1

    fields = hook_input.parse_fields(
        hook_input.read_hook_input(),
        adapter.environment_defaults(),
    )
    found = layout_mod.find_layout(fields["cwd_path"])
    try:
        result = handler(fields, found) if found is not None else None
    except Exception as exc:  # noqa: BLE001 - 兜底策略：fail-open / fail-silent
        output.debug(f"{event} 处理失败（按放行/静默处理）: {exc!r}")
        return 0
    if result:
        output.emit(output.render_for_platform(result, platform))
    return 0


if __name__ == "__main__":
    sys.exit(main())
