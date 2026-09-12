"""任务状态机。

主链：TODO → PLANNING → PLAN_CONFIRMED → IMPLEMENTING → VERIFYING → COMPLETED
附加：VERIFYING → IMPLEMENTING（验证不通过打回）、COMPLETED → IMPLEMENTING（重新打开）

第一版状态由用户手动推进（keystone task CLI），Keystone 不推断代码正确性。
"""

from __future__ import annotations

from keystone.errors import InvalidTransitionError

STATUSES = (
    "TODO",
    "PLANNING",
    "PLAN_CONFIRMED",
    "IMPLEMENTING",
    "VERIFYING",
    "COMPLETED",
)

ALLOWED_TRANSITIONS: dict[str, frozenset[str]] = {
    "TODO": frozenset({"PLANNING"}),
    "PLANNING": frozenset({"PLAN_CONFIRMED"}),
    "PLAN_CONFIRMED": frozenset({"IMPLEMENTING"}),
    "IMPLEMENTING": frozenset({"VERIFYING"}),
    "VERIFYING": frozenset({"COMPLETED", "IMPLEMENTING"}),
    "COMPLETED": frozenset({"IMPLEMENTING"}),
}

# 尚未到达"允许修改代码"节点的状态（PreToolUse 写入拦截的判定依据）
PRE_CONFIRM_STATUSES = frozenset({"TODO", "PLANNING"})


def is_valid_status(status: str) -> bool:
    return status in STATUSES


def validate_transition(current: str, target: str) -> None:
    """校验一次流转，非法则抛 InvalidTransitionError。"""
    if not is_valid_status(current):
        raise InvalidTransitionError(current or "<empty>", target)
    if not is_valid_status(target):
        raise InvalidTransitionError(current, target or "<empty>")
    if target not in ALLOWED_TRANSITIONS.get(current, frozenset()):
        raise InvalidTransitionError(current, target)


def next_status(current: str) -> str:
    """沿主链推进的下一个状态；COMPLETED 无下一步。"""
    if current == "COMPLETED":
        raise InvalidTransitionError(current, "<next>")
    validate_transition(current, _main_next[current])
    return _main_next[current]


_main_next = {
    "TODO": "PLANNING",
    "PLANNING": "PLAN_CONFIRMED",
    "PLAN_CONFIRMED": "IMPLEMENTING",
    "IMPLEMENTING": "VERIFYING",
    "VERIFYING": "COMPLETED",
}
