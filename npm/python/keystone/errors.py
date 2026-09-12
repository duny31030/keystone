"""Keystone 统一异常定义。"""

from __future__ import annotations


class KeystoneError(Exception):
    """Keystone 所有错误类型的基类。"""


class NotInitializedError(KeystoneError):
    """目标项目尚未执行 keystone init，缺少 .keystone/ 目录。"""


class InvalidTransitionError(KeystoneError):
    """任务状态机拒绝该次流转。"""

    def __init__(self, current: str, target: str) -> None:
        self.current = current
        self.target = target
        super().__init__(
            f"不允许从 {current} 流转到 {target}；"
            f"使用 keystone task advance 或查看合法流转：{ALLOWED_HINT}"
        )


ALLOWED_HINT = "TODO→PLANNING→PLAN_CONFIRMED→IMPLEMENTING→VERIFYING→COMPLETED，另有 VERIFYING→IMPLEMENTING 与 COMPLETED→IMPLEMENTING"
