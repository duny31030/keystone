# 增强验证 Keystone CodeBuddy 控制 Hooks

## Goal

在真实 CodeBuddy 中完成当前仅由本地协议测试覆盖的控制路径验证；以实测结果修正 Keystone 的实现、README 兼容矩阵和测试，而不是继续宣传未验证能力。

## Scope

验证对象：

- `Stop` 的 `enforce` 模式是否真正阻止结束；
- `stop_hook_active` 是否由 CodeBuddy 传入并能防止 Stop 循环；
- `COMPLETED` 任务之后的写入是否真实被 PreToolUse 拒绝；
- 直接修改 `.keystone/project.json`、`.keystone/.state/`、`.keystone/tasks/**/task.json` 是否真实被拒绝；
- 修改 `.keystone/tasks/**/prd.md` 和普通项目文件是否被允许。

不纳入：

- 恢复 `PostToolUse` / `PreCompact`；
- 自动 CodeBuddy 测试；
- 新 Hook 事件；
- 任务自动推进。

## Verification Method

建立一个新的临时 CodeBuddy 冒烟项目，使用当前源码构建出的 Keystone CLI，逐场景执行真实操作并记录 CodeBuddy 实际行为。每一场景只验证一个断言，避免把上下文遵守误认为 Hook 硬拦截。

## Acceptance Criteria

- [ ] Stop enforce 的真实行为明确：能阻断、仅提示，或 CodeBuddy 忽略 block 输出
- [ ] stop_hook_active 的真实行为明确：有实机证据，或记录为宿主不支持该字段
- [ ] COMPLETED 后普通写入的真实拦截结果明确
- [ ] `.keystone` 裁判状态文件保护的真实拦截结果明确
- [ ] `prd.md` 和普通项目文件的允许写入结果明确
- [ ] README 兼容矩阵按上述实测结果更新
- [ ] 若实现与 CodeBuddy 行为不符，代码和测试已修正；若行为正确，则补充回归测试
- [ ] 测试全绿，改动提交并推送 GitHub；不发布 npm/TestPyPI
