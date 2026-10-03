"""Platform adapter registry."""

from __future__ import annotations

from keystone.adapters.claude import ClaudeAdapter
from keystone.adapters.codebuddy import CodeBuddyAdapter
from keystone.adapters.codex import CodexAdapter

_ADAPTERS = {
    "codebuddy": CodeBuddyAdapter(),
    "claude": ClaudeAdapter(),
    "codex": CodexAdapter(),
}


def get_adapter(name: str = "codebuddy"):
    try:
        return _ADAPTERS[name]
    except KeyError as exc:
        supported = ", ".join(sorted(_ADAPTERS))
        raise ValueError(f"unsupported platform {name!r}; supported: {supported}") from exc


def supported_platforms() -> tuple[str, ...]:
    return tuple(sorted(_ADAPTERS))
