# npm 与 PyPI 自动发布流水线

## Goal

把"打 tag → 自动发布"真正打通:推送 `v*` tag 后,CI 先跑测试与版本校验,再自动把 Python 包发布到正式 PyPI、把 npm 包发布到 npmjs。现状是 CI 里发布 job 被整段注释,`release.sh` 打完 tag 只打印手敲命令就结束,导致本地 0.2.1 已 push 但两个 registry 都停在旧版本(npm 0.1.0,PyPI 完全没有)。

## Requirements

- **R1 触发**:仅在推送 `v*` tag 时触发发布;普通 push 到 main 不发布。
- **R2 npm 发布**:`keystone-hook` 发布到 `registry.npmjs.org`,凭据走 `NPM_TOKEN` secret。
- **R3 PyPI 发布**:`keystone-hook` 发布到正式 `pypi.org`,凭据走 `PYPI_TOKEN` secret。
- **R4 测试门禁**:发布 job 必须依赖测试 job 通过,测试失败不得发布。
- **R5 版本一致性**:tag 版本(`v0.2.1` → `0.2.1`)必须等于 `pyproject.toml` 中的版本;不一致则 workflow 失败且不发布。
- **R6 源码同步**:发布前执行 `scripts/sync_npm.py`,保证 npm 内嵌 Python 源码与 `src/keystone` 一致、npm 版本号与 pyproject 一致。
- **R7 幂等**:若 registry 上已存在同一版本,发布 job 应以"跳过"而非硬失败收场,使同一 tag 可安全重跑。
- **R8 发布物一致**:npm 与 PyPI 实际发布的内容必须与被测试的构建产物相同,不在发布 job 里重新构建一份新的。
- **R9 脚本与文档对齐**:`scripts/release.sh` 的收尾提示改为"tag 已推送,CI 将自动发布";README 安装说明从 TestPyPI 改为正式 PyPI。
- **R10 前置条件落盘**:明确写出需要在 GitHub 仓库配置的 secrets,以及首次发布 PyPI 包名的不可逆性。

## Constraints

- 仓库为 private(`api.github.com/repos/duny31030/keystone` 返回 404),因此 **PyPI trusted publishing(OIDC)不可用**,必须使用 API token。此点已实测确认,不是猜测。
- `NPM_TOKEN` / `PYPI_TOKEN` 只能由仓库所有者在 GitHub Settings → Secrets 中手工配置,CI 内无法自举。
- npm 当前 `latest` 为 `0.1.0`,PyPI 上 `keystone-hook` 尚未注册;首次 PyPI 发布将永久占用该包名，之后只能 yank 不能删除。
- npm 发布会写入外部 registry,属不可逆外部动作,必须在 secret 就位后由人工打 tag 触发。

## Acceptance Criteria

- [ ] 推送 `v0.3.0` tag 后,Release workflow 全绿,且 `npm view keystone-hook version` 返回 `0.3.0`。
- [ ] `https://pypi.org/pypi/keystone-hook/json` 返回 200 且 `info.version` 为 `0.3.0`。
- [ ] tag 版本与 `pyproject.toml` 不一致时,workflow 在校验步骤即失败,`publish-*` job 不执行。
- [ ] 对已发布过的版本重复推同一 tag,发布 job 输出 skip 提示并成功结束,不产生报错。
- [ ] 只 push 到 main(无 tag)时,Release workflow 不触发。
- [ ] `scripts/release.sh` 尾部不再提示手敲 `npm publish` / `uv publish`。
- [ ] README 中 Python 安装命令指向正式 PyPI,不再出现 `test.pypi.org`。

## Out of Scope

- TestPyPI 双发(本任务只发正式 PyPI)。
- 自动 version bump、自动生成 release notes、自动创建 GitHub Release。
- 迁移到 OIDC / trusted publishing(受 private 仓库限制,不在此任务解决)。
- 改动 keystone 运行时 Python 代码或 CLI 行为。