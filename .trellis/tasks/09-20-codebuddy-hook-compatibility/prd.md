# 验证 Keystone 剩余 CodeBuddy Hooks

## Goal

在真实 CodeBuddy 中验证 Stop、PostToolUse、SessionEnd、PreCompact 的触发、输出和元数据记录；根据事实收敛 Keystone 0.1.1 的默认 Hook 注册与公开承诺。

## Real CodeBuddy Results

测试项目：`/home/duny/tmp/keystone-codebuddy-smoke`。

| Hook | 结果 | 真实证据 |
|---|---|---|
| SessionStart | 支持 | 项目规范和技术栈上下文已注入 |
| UserPromptSubmit | 支持 | 成功创建、绑定和切换 TASK-003 |
| PreToolUse | 支持 | PLANNING 阶段的强制写入请求被真实拒绝 |
| Stop（reminder） | 支持 | VERIFYING 阶段结束时注入收尾检查清单 |
| SessionEnd | 支持 | `.state/events.jsonl` 写入了三条真实会话结束记录 |
| PostToolUse | 未支持/协议不同 | 多轮工具调用后无记录；移除 matcher 后仍无记录 |
| PreCompact | 未验证 | CodeBuddy 没有可靠的手动触发入口 |

SessionEnd 实际记录示例：

```json
{"at":"2026-09-20T12:29:28","event":"SessionEnd","reason":"other","session_id":"a42b44b942234600932b3741d6be3772","task":"TASK-003"}
```

## Requirements

- Keystone 0.1.1 默认只注册已在真实 CodeBuddy 中验证的事件：SessionStart、UserPromptSubmit、PreToolUse、Stop、SessionEnd；
- 重跑 `keystone init` 必须清理旧版 Keystone 写入的 PostToolUse / PreCompact 注册，且不得删除同事件下的第三方 hook；
- 不再公开 `keystone-hook post-tool-use` / `pre-compact` CLI 接口或宣传逐工具事件记录；
- README 必须区分真实 CodeBuddy 验证结果与仅本地协议测试的路径；
- npm 与 TestPyPI 发布版本同步到 0.1.1。

## Acceptance Criteria

- [x] 新项目初始化只写五个已验证的 CodeBuddy hooks
- [x] 老项目重跑 init 会清理 Keystone 的两条已退役 hook，第三方规则保持不变
- [x] CLI、实现和测试不再公开未验证事件
- [x] README/npm README 准确描述兼容矩阵与验证边界
- [x] pytest、Python 构建、npm tarball 全新安装冒烟通过
- [x] npm/TestPyPI 发布 0.1.1，GitHub main 已推送
