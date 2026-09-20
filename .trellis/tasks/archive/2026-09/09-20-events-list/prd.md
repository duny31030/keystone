# keystone events list 事件查看命令

## Goal

实现 `keystone events list` 命令，读取 `.keystone/.state/events.jsonl` 中的 SessionEnd 元数据记录，支持按任务、会话、事件类型过滤，纯本地 JSONL 读取。

## Requirements

- `keystone events list` 列出所有事件记录
- `keystone events list --task TASK-001` 按任务过滤
- `keystone events list --session <id>` 按会话过滤
- `keystone events list --event SessionEnd` 按事件类型过滤
- 输出格式：时间 | 事件 | 会话 | 任务 | 原因
- 只读，不修改任何文件
- 事件文件不存在时输出空列表，不报错
- 事件行格式损坏时跳过该行，继续处理其他行

## Acceptance Criteria

- [ ] `keystone events list` 输出所有 SessionEnd 记录
- [ ] `--task` 过滤只显示指定任务的事件
- [ ] `--session` 过滤只显示指定会话的事件
- [ ] `--event` 过滤只显示指定事件类型
- [ ] 无事件时输出空列表提示
- [ ] 损坏行被跳过，不影响其他行
- [ ] 测试覆盖以上场景，pytest 全绿
- [ ] README 更新 events list 用法
- [ ] 版本 0.2.1，不发布
