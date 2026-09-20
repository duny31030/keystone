# Changelog

所有 Keystone 的用户可见变更都会记录在此文件中。

格式参考 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.0.0/)，版本号遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

## [Unreleased]

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
