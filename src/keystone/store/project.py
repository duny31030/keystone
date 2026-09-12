"""project.json 读写与语言预设。"""

from __future__ import annotations

from keystone.store.layout import KeystoneLayout
from keystone.util import atomic_write_json, read_json

# 语言预设：keystone init 按语言填入默认构建/测试配置（需求文档 P0）
LANG_PRESETS = {
    "java": {
        "framework": "spring-boot",
        "build_tool": "maven",
        "build_command": "mvn clean package",
        "test_command": "mvn test",
    },
    "python": {
        "framework": "",
        "build_tool": "pip",
        "build_command": "",
        "test_command": "pytest",
    },
}


def load_project(layout: KeystoneLayout) -> dict | None:
    """读 project.json；未初始化返回 None。"""
    if not layout.initialized:
        return None
    return read_json(layout.project_json)


def save_project(layout: KeystoneLayout, project: dict) -> None:
    atomic_write_json(layout.project_json, project)


def make_project(
    slug: str,
    name: str,
    language: str,
    framework: str | None = None,
    build_tool: str | None = None,
    build_command: str | None = None,
    test_command: str | None = None,
    stop_mode: str = "reminder",
    policy_mode: str = "permissive",
) -> dict:
    """组装 project.json；未显式给定的构建字段取语言预设默认值。"""
    preset = LANG_PRESETS.get(language, {})
    return {
        "slug": slug,
        "name": name,
        "language": language,
        "framework": framework if framework is not None else preset.get("framework", ""),
        "build_tool": build_tool if build_tool is not None else preset.get("build_tool", ""),
        "build_command": build_command if build_command is not None else preset.get("build_command", ""),
        "test_command": test_command if test_command is not None else preset.get("test_command", ""),
        "stop_mode": stop_mode,  # reminder | enforce
        "policy_mode": policy_mode,  # permissive | strict
    }
