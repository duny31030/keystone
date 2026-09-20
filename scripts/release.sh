#!/usr/bin/env bash
# Keystone 发布脚本：校验版本、跑测试、同步 npm、构建产物、打 tag、推送。
# 用法：./scripts/release.sh 0.2.1
# 发布到 registry 的部分默认注释，等用户决定后再启用。

set -euo pipefail

ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$ROOT"

VERSION="${1:-}"
if [ -z "$VERSION" ]; then
    echo "用法: $0 <version>"
    echo "示例: $0 0.2.1"
    exit 1
fi

# 1. 检查工作区干净
if [ -n "$(git status --porcelain)" ]; then
    echo "错误：工作区有未提交变更，请先提交或 stash"
    git status --short
    exit 1
fi

# 2. 检查版本号一致性
pyproject_version=$(grep '^version = ' pyproject.toml | sed 's/.*"\(.*\)"/\1/')
init_version=$(grep '__version__ = ' src/keystone/__init__.py | sed 's/.*"\(.*\)"/\1/')
npm_version=$(python3 -c "import json; print(json.load(open('npm/package.json'))['version'])")

echo "版本号检查："
echo "  pyproject.toml: $pyproject_version"
echo "  __init__.py:    $init_version"
echo "  package.json:   $npm_version"
echo "  目标版本:       $VERSION"

if [ "$pyproject_version" != "$VERSION" ] || [ "$init_version" != "$VERSION" ] || [ "$npm_version" != "$VERSION" ]; then
    echo ""
    echo "错误：版本号不一致。请先统一为 $VERSION："
    echo "  pyproject.toml: version = \"$VERSION\""
    echo "  src/keystone/__init__.py: __version__ = \"$VERSION\""
    echo "  npm/package.json: \"version\": \"$VERSION\""
    exit 1
fi

echo ""
echo "✓ 版本号一致"

# 3. 跑测试
echo ""
echo "运行测试..."
if ! .venv/bin/pytest; then
    echo "错误：测试失败，拒绝发布"
    exit 1
fi
echo "✓ 测试通过"

# 4. 同步 npm
echo ""
echo "同步 npm 包..."
python3 scripts/sync_npm.py
echo "✓ npm 同步完成"

# 5. 构建产物
echo ""
echo "构建 Python 产物..."
rm -rf dist
uv build
echo "✓ Python 构建完成"

echo ""
echo "构建 npm 产物..."
cd npm
rm -f *.tgz
npm pack --dry-run > /dev/null
npm pack
cd ..
echo "✓ npm 构建完成"

# 6. 检查 CHANGELOG
if ! grep -q "## \[$VERSION\]" CHANGELOG.md 2>/dev/null; then
    echo ""
    echo "警告：CHANGELOG.md 中没有找到 [$VERSION] 条目"
    echo "请先补充 CHANGELOG.md，然后重新运行发布脚本"
    exit 1
fi
echo "✓ CHANGELOG.md 包含 [$VERSION] 条目"

# 7. 提交、打 tag、推送
echo ""
echo "提交发布变更..."
git add pyproject.toml src/keystone/__init__.py npm/package.json CHANGELOG.md npm/python/
git commit -m "chore(release): $VERSION" || echo "（无变更可提交，继续）"

echo ""
echo "打 tag v$VERSION..."
git tag -a "v$VERSION" -m "Release $VERSION"

echo ""
echo "推送 main 和 tag..."
git push origin main --tags

echo ""
echo "✓ 发布准备完成"
echo ""
echo "下一步（手动执行，或启用 CI 后自动）："
echo "  npm publish --access public        # npm 发布"
echo "  uv publish --publish-url https://test.pypi.org/legacy/  # TestPyPI 发布"
echo ""
echo "如果要自动发布，取消 .github/workflows/release.yml 中发布步骤的注释。"
