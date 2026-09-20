# keystone task plan 命令与结构化计划

## Goal

实现 `keystone task plan` 命令，为任务生成结构化 `plan.md` 模板，将 PLANNING 阶段的计划从对话中固化为文件，作为进入 `PLAN_CONFIRMED` 的前提条件。

## Requirements

- `keystone task plan <code>` 在任务目录生成 `plan.md`，包含目标、影响范围、实施步骤、验证方案、风险与未决事项
- `plan.md` 由用户或 AI 编辑，不是 Keystone 自动生成的
- `keystone task advance <code>` 在 `PLANNING → PLAN_CONFIRMED` 时校验 `plan.md` 存在且非空；无 plan 则拒绝并提示 `keystone task plan`
- 不强制内容结构（用户可删改模板），只要求文件存在且非空
- `keystone task show` 显示 plan.md 路径和状态（存在/缺失）
- `keystone task list` 可选显示 `plan` 状态标记

## Acceptance Criteria

- [ ] `keystone task plan TASK-001` 生成 `plan.md` 模板
- [ ] `keystone task plan TASK-001` 对已存在 plan.md 的任务提示已存在，不覆盖
- [ ] `keystone task advance TASK-001` 在 PLANNING 且无 plan.md 时拒绝，提示运行 plan
- [ ] `keystone task advance TASK-001` 在有 plan.md 时正常推进到 PLAN_CONFIRMED
- [ ] `keystone task show` 显示 plan.md 状态
- [ ] 测试覆盖以上场景，pytest 全绿
- [ ] README 更新 task plan 用法
- [ ] 版本 0.2.1，不发布
