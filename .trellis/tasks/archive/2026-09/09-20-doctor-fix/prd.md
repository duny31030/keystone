# keystone doctor --fix 自动修复

## Goal

实现 `keystone doctor --fix` 命令，自动补齐缺失的 Keystone Hook 注册、清理退役 Hook 条目、补 gitignore managed block，严格限制只修 Keystone 自己写入的配置，不碰任务、规范或用户内容。

## Requirements

- `keystone doctor --fix` 在运行 `doctor` 检查后，自动修复可安全修复的问题
- 修复范围严格限定：
  - 补齐缺失的五个已验证 Hook 注册（SessionStart、UserPromptSubmit、PreToolUse、Stop、SessionEnd）
  - 清理退役的 PostToolUse / PreCompact Keystone 条目
  - 补 `.gitignore` 的 `.keystone/.state/` managed block
  - 创建缺失的 `.keystone/` 目录结构（tasks、.state、specs）
  - 生成缺失的规范模板文件（architecture.md、coding.md、general-ban.md）
- **不修复**：损坏的 task.json、project.json、sessions.json、用户自定义内容
- 修复前显示将做什么，修复后显示结果
- 修复后自动重新运行 doctor，显示修复后的状态
- 如果修复后仍有 FAIL，返回非零退出码

## Acceptance Criteria

- [ ] `doctor --fix` 能补齐缺失的 Hook 注册
- [ ] `doctor --fix` 能清理退役的 PostToolUse / PreCompact 条目
- [ ] `doctor --fix` 能补 `.gitignore` 的 managed block
- [ ] `doctor --fix` 能创建缺失的 `.keystone/` 目录结构
- [ ] `doctor --fix` 能生成缺失的规范模板
- [ ] `doctor --fix` 不修改用户已有的自定义内容
- [ ] `doctor --fix` 不修复损坏的 JSON 文件（报告但不修改）
- [ ] 修复后 doctor 显示 0 fail
- [ ] 测试覆盖以上场景，pytest 全绿
- [ ] README 更新 doctor --fix 用法
- [ ] 版本 0.2.1，不发布
