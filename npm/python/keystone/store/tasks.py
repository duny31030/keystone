"""任务存储：一个任务一个目录 tasks/TASK-XXX/{task.json, prd.md}。

task.json 是 git 版本化的共享状态；prd.md 承载任务描述。
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from keystone.core import statemachine
from keystone.errors import KeystoneError
from keystone.store.layout import KeystoneLayout
from keystone.util import atomic_write_json, now_iso

_CODE_RE = re.compile(r"^TASK-(\d{3,})$")


def _write_prd(task_dir: Path, title: str, description: str, acceptance_criteria: list[str]) -> None:
    lines = [f"# {title}", "", "## 描述", "", description.strip() or "（待补充）", "", "## 验收标准"]
    if acceptance_criteria:
        lines += [f"- [ ] {c}" for c in acceptance_criteria]
    else:
        lines.append("- [ ] 待明确")
    (task_dir / "prd.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def next_task_code(layout: KeystoneLayout) -> str:
    """扫描现有任务目录，返回最大的编号 +1（TASK-001 起）。"""
    max_n = 0
    if layout.tasks_dir.is_dir():
        for entry in layout.tasks_dir.iterdir():
            m = _CODE_RE.match(entry.name)
            if m:
                max_n = max(max_n, int(m.group(1)))
    return f"TASK-{max_n + 1:03d}"


def create_task(
    layout: KeystoneLayout,
    title: str,
    description: str = "",
    acceptance_criteria: list[str] | None = None,
    status: str = "TODO",
    pending_confirmation: bool = False,
) -> dict:
    criteria = list(acceptance_criteria or [])
    code = next_task_code(layout)
    task_dir = layout.task_dir(code)
    task_dir.mkdir(parents=True, exist_ok=True)
    ts = now_iso()
    task = {
        "code": code,
        "title": title,
        "status": status,
        "pending_confirmation": pending_confirmation,
        "acceptance_criteria": criteria,
        "created_at": ts,
        "updated_at": ts,
        "transitions": [{"from": None, "to": status, "at": ts, "reason": "created"}],
    }
    atomic_write_json(task_dir / "task.json", task)
    _write_prd(task_dir, title, description, criteria)
    return load_task(layout, code)


def _task_json_path(layout: KeystoneLayout, code: str) -> Path:
    if not _CODE_RE.match(code):
        raise KeystoneError(f"非法任务编号：{code}（期望形如 TASK-001）")
    path = layout.task_dir(code) / "task.json"
    if not path.is_file():
        raise KeystoneError(f"任务 {code} 不存在")
    return path


def load_task(layout: KeystoneLayout, code: str) -> dict:
    """读取任务；附带的 description_md 取自 prd.md（缺失时为空）。"""
    path = _task_json_path(layout, code)
    try:
        task = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise KeystoneError(f"任务 {code} 的 task.json 无法读取：{exc}") from exc
    prd = layout.task_dir(code) / "prd.md"
    task["description_md"] = prd.read_text(encoding="utf-8") if prd.is_file() else ""
    return task


def save_task(layout: KeystoneLayout, task: dict) -> dict:
    """持久化任务（description_md 是派生内容，不写回 task.json）。"""
    payload = {k: v for k, v in task.items() if k != "description_md"}
    task["updated_at"] = now_iso()
    payload["updated_at"] = task["updated_at"]
    atomic_write_json(_task_json_path(layout, task["code"]), payload)
    return task


def list_tasks(layout: KeystoneLayout) -> list[dict]:
    """全部任务的摘要（不含 description_md），按编号排序。"""
    tasks = []
    if layout.tasks_dir.is_dir():
        for entry in sorted(layout.tasks_dir.iterdir()):
            if _CODE_RE.match(entry.name) and (entry / "task.json").is_file():
                try:
                    tasks.append(json.loads((entry / "task.json").read_text(encoding="utf-8")))
                except (OSError, json.JSONDecodeError):
                    continue
    return tasks


def find_task(layout: KeystoneLayout, code: str) -> dict | None:
    try:
        return load_task(layout, code)
    except KeystoneError:
        return None


def transition_task(layout: KeystoneLayout, code: str, target: str, reason: str = "") -> dict:
    """校验并执行一次状态流转，记录流转审计。"""
    task = load_task(layout, code)
    current = task["status"]
    statemachine.validate_transition(current, target)
    task["transitions"] = task.get("transitions", []) + [
        {"from": current, "to": target, "at": now_iso(), "reason": reason}
    ]
    task["status"] = target
    return save_task(layout, task)
