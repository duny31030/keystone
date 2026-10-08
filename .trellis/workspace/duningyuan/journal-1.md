# Journal - duningyuan (Part 1)

> AI development session journal
> Started: 2026-09-12

---



## Session 1: Keystone v1 实现完成

**Date**: 2026-09-12
**Task**: Keystone v1 实现完成
**Branch**: `main`

### Summary

去服务端化架构实现 CodeBuddy hook 增强层：init 脚手架、七事件 hook runner、任务状态机与 CLI、流程控制与规范注入，66 个测试全过

### Git Commits

| Hash | Message |
|------|---------|
| `920bec0` | (see git log) |

### Status

[OK] **Completed**


## Session 2: 验证并收敛 CodeBuddy Hook 兼容性

**Date**: 2026-09-20
**Task**: 验证并收敛 CodeBuddy Hook 兼容性
**Branch**: `main`

### Summary

真实验证确认五个 CodeBuddy hooks；移除未验证的 PostToolUse/PreCompact 默认注册，迁移保留第三方混合 rules，修正 npm 退出码与打包字节码问题；68 个测试通过。

### Git Commits

| Hash | Message |
|------|---------|
| `0687b01` | (see git log) |

### Status

[OK] **Completed**


## Session 3: 实现本地诊断与安全生命周期命令

**Date**: 2026-09-20
**Task**: 实现本地诊断与安全生命周期命令
**Branch**: `main`

### Summary

实现 init --dry-run、status、doctor、uninstall/purge；审查修复第三方 hook 归属、status 错误退出码与 gitignore 格式保真；86 测试通过，Python/npm fresh-install 生命周期烟测通过；未发布。

### Git Commits

| Hash | Message |
|------|---------|
| `fea745f` | (see git log) |

### Status

[OK] **Completed**


## Session 4: 真实 CodeBuddy 控制 Hook 验证完成

**Date**: 2026-09-20
**Task**: 真实 CodeBuddy 控制 Hook 验证完成
**Branch**: `main`

### Summary

COMPLETED 写入拒绝、.keystone 状态保护、计划阶段拦截、Stop reminder、SessionEnd 均已实机验证；Stop enforce 未观察到阻断，stop_hook_active 无法通过重复结束会话触发，README 已按实机结果更新。

### Git Commits

| Hash | Message |
|------|---------|
| `f5cb3d9` | (see git log) |

### Status

[OK] **Completed**


## Session 5: 实现 keystone task plan 命令

**Date**: 2026-09-20
**Task**: 实现 keystone task plan 命令
**Branch**: `main`

### Summary

实现 plan.md 模板生成、PLANNING→PLAN_CONFIRMED 的 plan.md 存在性校验、task show/list 的 plan 状态显示；95 个测试全过。

### Git Commits

| Hash | Message |
|------|---------|
| `f447da2` | (see git log) |

### Status

[OK] **Completed**


## Session 6: 实现 keystone doctor --fix 自动修复

**Date**: 2026-09-20
**Task**: 实现 keystone doctor --fix 自动修复
**Branch**: `main`

### Summary

实现 doctor --fix：自动补齐缺失 Hook 注册、清理退役条目、补 gitignore、创建缺失目录和规范模板；不修复损坏 JSON；103 测试全过。

### Git Commits

| Hash | Message |
|------|---------|
| `71a670e` | (see git log) |

### Status

[OK] **Completed**


## Session 7: 实现 keystone events list 命令

**Date**: 2026-09-20
**Task**: 实现 keystone events list 命令
**Branch**: `main`

### Summary

实现 events list：只读列出 SessionEnd 元数据，支持按任务/会话/事件过滤，跳过损坏行；111 测试全过。

### Git Commits

| Hash | Message |
|------|---------|
| `b14d0bd` | (see git log) |

### Status

[OK] **Completed**


## Session 8: 实现发布工程化基础设施

**Date**: 2026-09-20
**Task**: 实现发布工程化基础设施
**Branch**: `main`

### Summary

实现 release.sh 发布脚本（版本校验、测试、构建、tag、推送）、CHANGELOG.md、GitHub Actions workflow（tag 触发，发布步骤默认注释）。

### Git Commits

| Hash | Message |
|------|---------|
| `c589717` | (see git log) |

### Status

[OK] **Completed**


## Session 9: 实现 Keystone workflow skills

**Date**: 2026-10-03
**Task**: 实现 Keystone workflow skills
**Branch**: `main`

### Summary

增加 keystone-plan、keystone-verify、keystone-handoff canonical skills 和 skills list/install CLI；支持 auto/all/dry-run/冲突保护；Python/npm 资源打包验证通过，按要求未运行 pytest。

### Git Commits

| Hash | Message |
|------|---------|
| `a82ce85` | (see git log) |

### Status

[OK] **Completed**

## Session 10: Codex context-only adapter 与多平台收敛

**Date**: 2026-10-03
**Task**: Keystone 多平台适配设计
**Branch**: `main`

### Summary

收敛多平台 adapter 边界并实现 Codex context-only adapter：settings 路径、事件集合、注册计数、deny 渲染与 capability warnings 全部下沉到 adapters/；Codex 只注册 UserPromptSubmit，只写 .codex/hooks.json；Pi/Codex 统一映射共享 .agents/skills。

### Main Changes

- 新增 `adapters/base.py`（PlatformAdapter protocol、JsonHookAdapter、keystone command 识别）、`adapters/registry.py`、`adapters/codebuddy.py`、`adapters/claude.py`、`adapters/codex.py`
- `inspection.py` / `cli.py` / `hook/cli.py` 去硬编码：按 `--platform` 走 adapter，未注册事件返回 exit 1
- `skills/catalog.py`：`SHARED_TARGET_LABEL`，auto 识别 `.codex`/`.pi` 根目录
- 新增 Codex 测试与 `scripts/codex-smoke.sh`；`keystone events list` 兼容别名
- README 平台矩阵与 CHANGELOG 更新；Pi TypeScript extension 明确拆分为独立后续任务

### Git Commits

| Hash | Message |
|------|---------|
| `4bc2936` | feat: add Codex context-only platform adapter |

### Testing

- [OK] 133 passed（`.venv/bin/pytest`）
- [OK] wheel 构建与 fresh venv 安装 smoke：codebuddy/claude/codex doctor 与 status 输出正确
- [OK] npm tarball 打包并通过 npm shim 安装 smoke：Codex init 与本机 hook runner 正常
- [P] Claude / Codex 真实宿主 smoke 待用户手工执行（`scripts/claude-smoke.sh`、`scripts/codex-smoke.sh`）

### Status

[OK] **Completed**（真实宿主 smoke 为待办用户动作）

### Next Steps

- 在真实 Claude Code / Codex 中执行 smoke checklist，通过后更新 README capability status
- 新建独立任务实现 Pi TypeScript extension（before_agent_start / tool_call / session_shutdown）

## Session 11: 三平台真实宿主验证

**Date**: 2026-10-05
**Task**: Keystone 多平台适配设计（含子任务 pi-extension）
**Branch**: `main`

### Summary

Claude/Codex/Pi 三个平台的真实宿主验证全部完成，证据落盘 research/；capability 声明按实测升级；Pi extension 任务的阻塞性 R1 观测完成，三项契约全部确认可用。

### Main Changes

- Claude（headless `claude -p`）：9/9 通过，Stop enforce 实测被宿主尊重且循环保护生效 → Verified (headless)
- Codex（`codex exec`）：UserPromptSubmit 三前置条件确认（用户级 feature + trust + hook 信任），暗号测试证明注入到达模型 → Verified (context only)
- Pi（`pi -p` + 探针 extension）：`tool_call {block:true}` 生效、session id 可得、`before_agent_start` 双通道注入生效；发现项目级 extension 需 trust、handler 抛错 fail-closed（须显式 fail-open）、bash 可绕过 write/edit 门禁
- 横向发现：全局旧版 keystone-hook@0.1.0 PATH 陷阱会让 hook 静默失效（README 已加说明）
- adapter capability_warnings、README 矩阵、CHANGELOG 按实测更新；新增 Pi extension 子任务 research 文档

### Git Commits

| Hash | Message |
|------|---------|
| (see git log) | docs: record real-host verification for claude/codex/pi |

### Testing

- [OK] 133 tests passed（含更新后的 claude doctor 文案断言）
- [OK] 三平台真实宿主验证（headless 自动化，非模拟）

### Status

[OK] **Completed**

### Next Steps

- Pi extension R2-R5：bridge CLI、extension bundle、tsc 类型检查、打包断言（子任务 10-05-pi-extension）
- 考虑发布 0.3.0（CHANGELOG [Unreleased] 已齐）

---

## Session 12: npm 与 PyPI 自动发布流水线

**Date**: 2026-10-08
**Task**: npm 与 PyPI 自动发布流水线 (`10-08-npm-pypi-auto-publish`)
**Branch**: `main`

### Summary

启用被注释掉的 CI 发布 job：推送 `v*` tag 后自动发布到正式 PyPI 与 npmjs。首次发布定为 0.3.0（HEAD 已积累大量 [Unreleased] 功能，发 0.2.1 会让包内容与 CHANGELOG 矛盾）。

### Main Changes

- `.github/workflows/release.yml` 重写：`build`（门禁 + 产物）→ `publish-pypi` / `publish-npm`（各自 `needs: build`，只下载产物不重建）
- `build` 门禁顺序：tag↔pyproject 版本比对（`tomllib`，最前，快速失败）→ pytest → `sync_npm.py` → 同步零漂移校验（版本一致 + `git diff --exit-code` 覆盖 npm 生成物）
- 产物拆为 `python-dist` / `npm-tarball`，消除多 path 通配符下的目录结构不确定性
- 幂等：PyPI 用 action 的 `skip-existing`；npm 无等价开关，改用 `npm view` 探针（实测 exit 0 = 已存在 → 跳过，exit 1 = 不存在 → 发布），探测失败方向 fail-closed
- `scripts/release.sh` 收尾改为「tag 已推送，CI 将自动发布」，移除手敲 `npm publish` / `uv publish` 提示，补充 secrets 前置条件与不可逆警告
- 版本 0.2.1 → 0.3.0（pyproject / `__init__` / npm 生成物），CHANGELOG 的 [Unreleased] 收为 `[0.3.0] - 2026-10-08`
- README 安装命令从 TestPyPI 改为正式 PyPI
- 新增 `.trellis/spec/backend/release-and-publishing.md`：版本单一来源、CI 门禁顺序、探针契约、private repo 无法用 OIDC、发布不可逆

### Key Findings

- 仓库是 private → PyPI trusted publishing (OIDC) 不可用，api.github.com 返回 404，只能 token auth
- `gh-action-pypi-publish` 没有 `token:` 输入，凭据走 `password:`；token 流程不需要 `permissions:` 块
- `keystone-hook` 在 pypi.org 尚未注册 → 首次发布只能用 account-scoped token，之后可换 project-scoped
- npm 重复版本发布是硬失败，探针是必需的（不能靠 registry 侧幂等）

### Git Commits

| Hash | Message |
|------|---------|
| `e9e9353` | `chore(release): cut 0.3.0` |
| `7f4b40c` | `ci: auto-publish to npm and PyPI on v* tag` |
| `792893b` | `docs(trellis): record release flow and publishing constraints` |

### Testing

- [OK] 133 tests passed（`.venv/bin/pytest` 在本机可用；此前误判为损坏，实为 shell 中 `python` 被 AppImage 遮蔽导致的控制台输出误导）
- [OK] `uv build` + `uvx twine check dist/*` → PASSED
- [OK] YAML 解析、job 图、触发条件、无重建、无 permissions、凭据仅引用 secret
- [OK] 探针语义实测：`npm view keystone-hook@0.1.0 version` exit 0；`@0.3.0` exit 1
- [OK] tag 校验对抗矩阵 8 组输入（含 `vv0.3.0`、`v0.3.0-rc1`、`refs/tags/...`）无误通过
- [NOT VERIFIED] 真实发布到 registry —— 需 secrets + 真实 tag 推送，属外部不可逆动作，留给用户

### Status

[OK] **Completed**（已提交并推送到 origin/main；未打 tag，未触发任何发布）

### Next Steps

- 在 GitHub Settings → Secrets 配置 `PYPI_TOKEN`（首次用 Entire account 范围）与 `NPM_TOKEN`
- 执行 `./scripts/release.sh 0.3.0` 或手动 `git tag v0.3.0 && git push origin v0.3.0` 触发首次发布
- 若 branch protection 有名为 `test` 的 required check，需改名为 `build`（job 已重命名）
