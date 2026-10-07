# Codex 真实宿主观测记录

日期：2026-10-05。环境：codex-cli 0.160.0，`codex exec` 非交互模式，provider `api2.love-long.com`（gpt-6-sol）。测试项目 `/tmp/ks-codex-clean`（keystone init --platform codex）。用户级配置用隔离的 `CODEX_HOME=/tmp/ks-codex-home` 副本，未改动真实 `~/.codex/`。

## 触发 UserPromptSubmit hook 的三个必要条件（实测缺一不可）

1. 用户级 `[features] hooks = true`（项目级 config 设不了 feature flags——Codex 硬限制）。
2. 项目 `trust_level = "trusted"`。
3. Hook 信任：交互式走 `/hooks` 审批；**非交互式用 `--dangerously-bypass-hook-trust`**。

只满足 1+2、不做 hook 信任时：hook 完全不触发且**无任何报错**（RUST_LOG=debug 下只见 `feature.hooks=true`，无 hook 分发日志）。加上第 3 项后立即触发。

Hook 信任按 hooks.json **绝对路径逐项目记账**：用户真实 config 中已存在
`[hooks.state."D:\\GitLab\\.codex\\hooks.json:user_prompt_submit:0:0"] trusted_hash = "sha256:..."`
——即每个项目的 hooks.json 各需一次审批记录。

## 验证结果

| 能力 | 结果 | 证据 |
|---|---|---|
| UserPromptSubmit 触发 | ✅ | 哨兵 hook 捕获 payload |
| context 注入进模型 | ✅ | **暗号测试**：任务描述埋 `PLATYPUS-7731`（仅存在于 prd.md），Codex 准确答出 |
| 会话绑定落盘 | ✅ | prompt 含 TASK 编号后 sessions.json 写入绑定 |
| 无写入门禁 | ✅（符合声明） | PLAN_CONFIRMED 阶段 `--sandbox workspace-write` 下写文件成功 |

Codex 发给 hook 的真实 payload：

```json
{"session_id":"...","turn_id":"...","transcript_path":"<CODEX_HOME>/sessions/....jsonl","cwd":"...","hook_event_name":"UserPromptSubmit","model":"gpt-6-sol","permission_mode":"bypassPermissions","prompt":"hello"}
```

`keystone-hook --platform codex` 的字段归一全部命中；返回的 `hookSpecificOutput.additionalContext` 被宿主注入。

## 易误判点

- Codex 默认 sandbox 是 `read-only`：写失败是**宿主沙箱**拦的，不是 Keystone。必须 `--sandbox workspace-write` 重测才能证明"Keystone 无 deny"。
- 首轮测试曾被旧 provider 的 `403 INSUFFICIENT_BALANCE` 阻塞（模型调用失败发生在 hook 分发之前，UserPromptSubmit 不触发）；换 provider 后解除。
- 同 Claude：注册的是裸命令 `keystone-hook`，全局旧版 0.1.0 会静默吞掉一切（PATH 陷阱）。

## 结论

Codex MVP 声明的唯一能力（UserPromptSubmit context）在真实宿主验证通过，capability 可升级为 verified（context-only）。deny/Stop/SessionEnd 维持 unsupported——本次也顺带确认了 SessionEnd 无从注册（hooks.json 无对应可信事件路径被验证）。

## 需要修正的产品文案

`CodexAdapter.capability_warnings()` 应补充：
- hook 信任按项目 hooks.json 路径逐个记账，每个项目需一次 `/hooks` 审批；
- 自动化/headless 场景可用 `codex exec --dangerously-bypass-hook-trust`（用户自行评估风险）。