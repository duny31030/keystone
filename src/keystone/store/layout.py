""".keystone/ 目录布局与定位。"""

from __future__ import annotations

from pathlib import Path

KEYSTONE_DIR = ".keystone"


class KeystoneLayout:
    """一个目标项目的 .keystone 目录结构。"""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.dir = root / KEYSTONE_DIR

    @property
    def project_json(self) -> Path:
        return self.dir / "project.json"

    @property
    def specs_dir(self) -> Path:
        return self.dir / "specs"

    @property
    def tasks_dir(self) -> Path:
        return self.dir / "tasks"

    @property
    def state_dir(self) -> Path:
        return self.dir / ".state"

    @property
    def sessions_json(self) -> Path:
        return self.state_dir / "sessions.json"

    @property
    def events_jsonl(self) -> Path:
        return self.state_dir / "events.jsonl"

    @property
    def initialized(self) -> bool:
        return self.project_json.is_file()

    def task_dir(self, code: str) -> Path:
        return self.tasks_dir / code


def find_layout(start: Path | None = None) -> KeystoneLayout | None:
    """从 start（默认 cwd）逐级向上查找 .keystone/；找不到返回 None。"""
    current = (start or Path.cwd()).resolve()
    for candidate in (current, *current.parents):
        if (candidate / KEYSTONE_DIR).is_dir():
            return KeystoneLayout(candidate)
    return None
