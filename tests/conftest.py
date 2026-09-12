"""测试公共设施。"""

from __future__ import annotations

import sys
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import pytest

from keystone import scaffold
from keystone.core.context import render_session_start  # noqa: F401 - 冒烟导入
from keystone.store.layout import KeystoneLayout
from keystone.store.project import make_project


@pytest.fixture
def project_dir(tmp_path: Path) -> Path:
    """一个已完成 keystone init 的目标项目（python 预设）。"""
    project = make_project(slug="demo", name="demo", language="python")
    scaffold.scaffold_keystone(tmp_path, project)
    scaffold.write_codebuddy_settings(tmp_path, "keystone-hook")
    scaffold.ensure_gitignore(tmp_path)
    return tmp_path


@pytest.fixture
def layout(project_dir: Path) -> KeystoneLayout:
    return KeystoneLayout(project_dir)


def make_fields(**overrides) -> dict:
    """构造与 hook.input.parse_fields 输出同构的字段 dict。"""
    fields = {
        "session_id": "sess-1",
        "transcript_path": "",
        "hook_event_name": "",
        "cwd": "/tmp/demo",
        "cwd_path": Path("/tmp/demo"),
        "prompt": "",
        "tool_name": "",
        "tool_input": {},
        "tool_response": None,
        "reason": "",
        "stop_hook_active": False,
        "raw": {},
    }
    fields.update(overrides)
    return fields
