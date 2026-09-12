#!/usr/bin/env python3
"""发布前同步脚本：让 npm 包与 Python 包保持一致。

- src/keystone → npm/python/keystone（内嵌源码，排除 __pycache__）
- pyproject.toml 的版本号 → npm/package.json
- LICENSE、README.md → npm/

用法：python3 scripts/sync_npm.py（在仓库根目录执行）
"""

from __future__ import annotations

import json
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC_PACKAGE = ROOT / "src" / "keystone"
NPM_DIR = ROOT / "npm"
NPM_PYTHON = NPM_DIR / "python" / "keystone"
PYPROJECT = ROOT / "pyproject.toml"
NPM_PACKAGE_JSON = NPM_DIR / "package.json"


def read_version() -> str:
    text = PYPROJECT.read_text(encoding="utf-8")
    match = re.search(r'^version\s*=\s*"([^"]+)"', text, re.MULTILINE)
    if not match:
        raise SystemExit("pyproject.toml 中未找到 version")
    return match.group(1)


def sync_source() -> None:
    if NPM_PYTHON.exists():
        shutil.rmtree(NPM_PYTHON)
    shutil.copytree(SRC_PACKAGE, NPM_PYTHON, ignore=shutil.ignore_patterns("__pycache__"))


def sync_version(version: str) -> None:
    package = json.loads(NPM_PACKAGE_JSON.read_text(encoding="utf-8"))
    if package.get("version") != version:
        package["version"] = version
        NPM_PACKAGE_JSON.write_text(
            json.dumps(package, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        print(f"npm 版本号 → {version}")
    else:
        print(f"npm 版本号已是 {version}")


def sync_docs() -> None:
    for name in ("LICENSE", "README.md"):
        shutil.copy2(ROOT / name, NPM_DIR / name)


def main() -> int:
    version = read_version()
    sync_source()
    sync_version(version)
    sync_docs()
    print(f"已同步 src/keystone → npm/python/keystone（版本 {version}）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
