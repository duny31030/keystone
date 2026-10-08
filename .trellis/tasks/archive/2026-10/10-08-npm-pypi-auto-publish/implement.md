# Implement — npm 与 PyPI 自动发布流水线

## 前置:校验依据(实现前已实测,勿重复推导)

| 事实 | 证据 |
|---|---|
| 仓库 private → 不能用 OIDC | `api.github.com/repos/duny31030/keystone` → 404 |
| npm 缺版本探针 exit 1 | `npm view keystone-hook@0.2.1 version` → stderr `E404 No match found for version`,exit 1 |
| npm 有版本探针 exit 0 | `npm view keystone-hook@0.1.0 version` → stdout `0.1.0`,exit 0 |
| npm 版本列表可解析 | `npm view keystone-hook versions --json` → `["0.1.0"]`,node `JSON.parse` 得数组 |
| npm tgz 名可推导 | `npm pack --dry-run` → `filename: keystone-hook-0.2.1.tgz`,即 `<name>-<version>.tgz` |
| PyPI 版本不存在 → 404 | `pypi.org/pypi/requests/99.99.99/json` → 404;存在 → `requests/2.31.0` → 200 |
| `keystone-hook` 未上 PyPI | `pypi.org/pypi/keystone-hook/json` → 404(仅 test.pypi.org 有 0.1.0) |
| 测试全绿 | `uv run --with pytest python -m pytest` → 133 passed |
| 测试基线命令不能用 `./scripts/release.sh` 原样 | `.venv/bin/python` 指向 `/usr/sbin/python3` 且缺 pytest;CI 用 setup-python + pip 不受影响 |

## 执行清单

### 1. 版本号 → 0.3.0(三处必须一致)

- [ ] `pyproject.toml`:`version = "0.3.0"`
- [ ] `src/keystone/__init__.py`:`__version__ = "0.3.0"`
- [ ] `npm/package.json`:`"version": "0.3.0"`
- [ ] `npm/python/keystone/__init__.py`:由 `scripts/sync_npm.py` 自动同步(不手改)
- **自检**:`python3 scripts/sync_npm.py` 必须输出「npm 版本号已是 0.3.0」且 `git status` 只剩版本号文件的改动。

### 2. CHANGELOG.md

- [ ] 把 `## [Unreleased]` 下全部条目收进 `## [0.3.0] - 2026-10-08`
- [ ] 重新留一个空的 `## [Unreleased]` 小节在顶部
- **原因**:否则首次发布的包内容与 CHANGELOG 对不上(见 design.md 版本策略)。

### 3. `.github/workflows/release.yml`(核心)

- [ ] `build` job:
  - [ ] 加 tag↔版本校验步骤(最前):`GITHUB_REF_NAME` 去 `v` 前缀 vs `tomllib` 读出的 `project.version`,不等则 `::error::` + `exit 1`
  - [ ] `pytest` 之后保留 `sync_npm.py`
  - [ ] sync 后复校 pyproject version == package.json version,不等则失败
  - [ ] upload artifact 拆为两个:`python-dist`(`dist/*.whl`, `dist/*.tar.gz`)与 `npm-tarball`(`npm/*.tgz`)
- [ ] 新增 `publish-pypi`(needs: build):
  - [ ] `actions/download-artifact@v4` 取 `python-dist` 到 `dist/`
  - [ ] `pypa/gh-action-pypi-publish@release/v1`,`with: password: ${{ secrets.PYPI_TOKEN }}` + `skip-existing: true`
- [ ] 新增 `publish-npm`(needs: build):
  - [ ] `actions/download-artifact@v4` 取 `npm-tarball` 到 `npm-dist/`
  - [ ] `setup-node@v4` + `registry-url: https://registry.npmjs.org`
  - [ ] 探针:读 package.json 版本 → 若 `npm view keystone-hook@$V version` 成功则 `exit 0` 跳过;否则 `npm publish ./npm-dist/*.tgz`
  - [ ] `env: NODE_AUTH_TOKEN: ${{ secrets.NPM_TOKEN }}`
- [ ] **不加** `permissions:` 块;**保留** workflow 里原有的注释掉的 OIDC/TestPyPI 段作为历史参考或直接删除——二选一,不能留下与启用逻辑矛盾的注释

### 4. `scripts/release.sh`

- [ ] 第 105-109 行的收尾提示改为:tag 已推送,CI 将自动发布;列出需要预先配置的 secrets
- [ ] 删除 `npm publish` / `uv publish` 手敲提示与「取消注释启用」说明

### 5. `README.md`

- [ ] 安装段:`pip install --index-url https://test.pypi.org/simple/ keystone-hook` → `pip install keystone-hook`
- [ ] 去掉「TestPyPI 测试站」字样
- [ ] PATH pitfall 段落中的示例版本号如有过时引用一并订正

## 验证命令

```bash
# YAML 可解析 + job 图 + 无注释残留
python3 -c "import yaml;d=yaml.safe_load(open('.github/workflows/release.yml'));print(list(d['jobs']))"
python3 -c "import yaml;d=yaml.safe_load(open('.github/workflows/release.yml'));\
print(d['jobs']['publish-pypi']['needs'],d['jobs']['publish-npm']['needs'])"

# 版本三处一致
grep '^version' pyproject.toml; grep __version__ src/keystone/__init__.py; \
python3 -c "import json;print(json.load(open('npm/package.json'))['version'])"

# sync 幂等(必须无 diff)
python3 scripts/sync_npm.py && git diff --stat

# 测试基线
uv run --with pytest python -m pytest

# 构建产物 + twine 元数据检查
uv build && uvx twine check dist/*

# 探针语义(离线可验)
npm view keystone-hook@0.1.0 version; echo "expect exit 0 -> $?"
npm view keystone-hook@0.3.0 version 2>/dev/null; echo "expect exit 1 -> $?"

# 无 tag 不触发(触发条件未被改宽)
python3 -c "import yaml;print(yaml.safe_load(open('.github/workflows/release.yml'))[True])"
```

## 评审门

1. **YAML 门**:两个 publish job 的 `needs` 指向 `build`;触发条件仍只含 `tags: v*`。
2. **一致性门**:`sync_npm.py` 跑完 `git diff` 为空,`sh test` 兜底版本比对。
3. **幂等门**:npm 探针在版本已存在时 `exit 0`,不存在时非 0;PyPI 侧 `skip-existing: true` 在位。
4. **无重建门**:publish job 中不出现 `python -m build` / `uv build` / `npm pack`。
5. **凭据门**:`PYPI_TOKEN` 走 `password:`,`NPM_TOKEN` 走 `NODE_AUTH_TOKEN`,均只引用 secret 名不出现明文。
6. **无破坏门**:`git diff --stat` 不含 `src/keystone/**`(除 `__init__.py` 版本号一行)。

## 回滚点

| 阶段 | 回滚 |
|---|---|
| 改版本号/CHANGELOG 后 | `git checkout -- pyproject.toml src/keystone/__init__.py npm/package.json CHANGELOG.md` |
| workflow 改错 | `git checkout -- .github/workflows/release.yml` |
| 误打 tag 未推 | `git tag -d v0.3.0` |
| tag 已推、workflow 全红、未发布成功 | secrets 修好后 GitHub「Re-run failed jobs」;幂等探针保证重跑安全 |
| 已发布成功但有致命缺陷 | 仅能 yank(PyPI)/ 72h 内 unpublish(npm);此后只能发下一个版本修正 |

## 不做

- 不加 `workflow_dispatch`(见 design.md 理由)。
- 不迁移 OIDC / trusted publishing。
- 不改 `src/keystone/**` 运行时逻辑。
- 不实际执行发布:打 tag 推送属于外部不可逆动作,由用户在有 secrets 后决定。