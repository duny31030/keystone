"""Keystone workflow skill catalog and project-level installation helpers."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from importlib.resources import files
from pathlib import Path

SKILL_NAMES = ("keystone-plan", "keystone-verify", "keystone-handoff")
TARGETS = {
    "agents": ".agents/skills",
    "claude": ".claude/skills",
    "codebuddy": ".codebuddy/skills",
    "zcode": ".zcode/skills",
}
PLATFORM_ALIASES = {
    "codex": "agents",
    "pi": "agents",
}
SHARED_TARGET_LABEL = "agents (shared by Codex and Pi)"


@dataclass(frozen=True)
class SkillChange:
    action: str
    skill: str
    target: Path
    detail: str = ""


def source_path(skill: str) -> Path:
    if skill not in SKILL_NAMES:
        raise ValueError(f"unknown Keystone skill: {skill}")
    return Path(str(files("keystone.assets.skills").joinpath(skill, "SKILL.md")))


def source_content(skill: str) -> str:
    return source_path(skill).read_text(encoding="utf-8")


def source_hash(skill: str) -> str:
    return hashlib.sha256(source_content(skill).encode()).hexdigest()


def selected_targets(root: Path, platform: str) -> tuple[str, ...]:
    if platform == "all":
        return tuple(TARGETS)
    if platform == "auto":
        detected = []
        for name, relative in TARGETS.items():
            root_dir = root / Path(relative).parts[0]
            if root_dir.exists():
                detected.append(name)
        # Codex/Pi use the shared .agents/skills target even when .agents is absent.
        if (root / ".codex").exists() or (root / ".pi").exists():
            if "agents" not in detected:
                detected.append("agents")
        return tuple(detected)
    platform = PLATFORM_ALIASES.get(platform, platform)
    if platform not in TARGETS:
        raise ValueError(f"unsupported platform: {platform}")
    return (platform,)


def plan_install(root: Path, platform: str, force: bool = False) -> list[SkillChange]:
    changes: list[SkillChange] = []
    for target_name in selected_targets(root, platform):
        base = root / TARGETS[target_name]
        for skill in SKILL_NAMES:
            target = base / skill / "SKILL.md"
            source = source_content(skill)
            if not target.exists():
                changes.append(SkillChange("CREATE", skill, target))
            elif target.read_text(encoding="utf-8") == source:
                changes.append(SkillChange("UNCHANGED", skill, target))
            elif force:
                changes.append(SkillChange("OVERWRITE", skill, target))
            else:
                changes.append(SkillChange("CONFLICT", skill, target, "existing skill differs; use --force to overwrite"))
    return changes


def apply_install(changes: list[SkillChange]) -> list[SkillChange]:
    conflicts = [change for change in changes if change.action == "CONFLICT"]
    if conflicts:
        return conflicts
    for change in changes:
        if change.action in {"CREATE", "OVERWRITE"}:
            change.target.parent.mkdir(parents=True, exist_ok=True)
            change.target.write_text(source_content(change.skill), encoding="utf-8")
    return []
