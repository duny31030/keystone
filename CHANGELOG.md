# Changelog

所有 Keystone 的用户可见变更都会记录在此文件中。

格式参考 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.0.0/)，版本号遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

## [Unreleased]

## [0.3.0] - 2026-10-08

### Added
- Platform adapter 层：`src/keystone/adapters/`，把配置路径、事件注册、deny 渲染、注册计数和 capability 提示从共享核心下沉到平台薄适配器
- Codex 平台支持（context-only）：`keystone init|doctor|uninstall --platform codex` 只操作 `.codex/hooks.json`，只注册 `UserPromptSubmit` 注入任务上下文
- Claude/Codex/Pi 真实宿主观测记录落盘 `.trellis/tasks/*/research/`；Pi extension 拆为子任务 `10-05-pi-extension`（宿主契约已实测：tool_call block、session id、before_agent_start 注入均可用；项目级 extension 需 project trust；handler 抛错为 fail-closed，须显式 fail-open）
- Claude/Codex smoke 项目生成脚本：`scripts/claude-smoke.sh`、`scripts/codex-smoke.sh`
- `keystone skills install --platform codex|pi` 明确映射共享 `.agents/skills/`；`skills list` 显示 shared target；Pi 原生识别该目录已实测确认

### Changed
- Claude adapter 升级为 Verified（headless）：context、file-tool deny、三类门禁、Stop reminder/enforce、SessionEnd 均在真实 `claude -p` 会话验证；Stop enforce 实测被宿主尊重且循环保护生效
- Codex UserPromptSubmit context 升级为 Verified：真实 `codex exec` 会话验证（含暗号注入测试）；capability warnings 补充 hook 信任按项目记账与 headless bypass 说明
- `keystone status` / `keystone doctor` / hook runner 不再硬编码 CodeBuddy 事件计数、设置路径和平台白名单，一律按 `--platform` 走 adapter
- README 平台矩阵按实测结果更新，并新增 PATH 陷阱说明（旧版全局 `keystone-hook` 会让 hook 静默失效）

### Notes
- Codex 适配刻意不提供 file-tool deny、strict gate、Stop、SessionEnd；这些能力需要独立宿主验证后才可能引入
- Codex 用户级前置条件（`hooks = true`、project trust、`/hooks` 审批）由 Keystone 提示但不代改
- Pi TypeScript extension 拆分为后续独立任务，未在本版本引入

## [0.2.1] - 2026-10-03

### Added
- Keystone workflow skills: `keystone-plan`, `keystone-verify`, `keystone-handoff`
- `keystone skills list` and `keystone skills install` with auto/all/platform targeting, dry-run, idempotency and collision protection
- Canonical Skill resources included in Python wheel and npm tarball

## [0.2.0] - 2026-09-20

### Added
- `keystone doctor --fix` 自动修复：补齐缺失 Hook 注册、清理退役条目、补 gitignore、创建缺失目录和规范模板
- `keystone events list`：只读查看本地 SessionEnd 事件记录，支持按任务/会话/事件类型过滤
- `keystone task plan`：生成结构化 plan.md 模板，PLANNING → PLAN_CONFIRMED 需要 plan.md 存在且非空
- `keystone task show` 和 `keystone task list` 显示 plan.md 状态
- 真实 CodeBuddy 兼容性验证：SessionStart、UserPromptSubmit、PreToolUse、Stop（reminder）、SessionEnd 已实机验证
- `PreToolUse` 对 COMPLETED 任务后的写入拒绝已实机验证
- `.keystone` 状态文件保护已实机验证

### Changed
- `PLANNING → PLAN_CONFIRMED` 状态流转需要 `plan.md` 存在且非空
- README 兼容矩阵按真实 CodeBuddy 测试结果更新

### Fixed
- npm shim 退出码透传：Node 包装器现在正确返回 Python CLI 的失败退出码
- `merge_settings()` 在混合 rule 中保留第三方 command，不再误删

### Removed
- 默认注册 `PostToolUse` 和 `PreCompact`（当前 CodeBuddy 版本未验证支持）
- `keystone-hook post-tool-use` 和 `keystone-hook pre-compact` CLI 接口

## [0.1.0] - 2026-09-12

### Added
- 初始版本：Keystone MVP 实现
- `keystone init` 初始化 `.keystone/` 目录和 CodeBuddy Hook 注册
- `keystone-hook` 支持 SessionStart、UserPromptSubmit、PreToolUse、PostToolUse、Stop、SessionEnd、PreCompact
- 任务状态机：TODO → PLANNING → PLAN_CONFIRMED → IMPLEMENTING → VERIFYING → COMPLETED
- 流程控制：计划确认前禁止写入、任务完成后禁止修改、`.keystone` 状态文件保护
- 本地诊断：`keystone doctor`、`keystone status`、`keystone uninstall`
- npm 和 TestPyPI 发布
