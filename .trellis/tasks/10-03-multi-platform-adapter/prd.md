# Keystone 多平台适配设计

## Goal

规划 Keystone 对 Claude Code、Codex、Pi 和现有 CodeBuddy 的支持，将项目/任务/策略核心与平台协议分离，并按已验证能力逐步适配，而不许诺不同平台具有相同门禁能力。

## Research Evidence

| 平台 | 适配级别 | 已知安全能力 | 主要证据 |
|---|---|---|---|
| CodeBuddy | full（已实现） | Context、PreToolUse deny、Stop reminder、SessionEnd 已实测 | Keystone 现有真实测试 |
| Claude Code | full（下一实现） | 官方支持 JSON Hook、PreToolUse deny、Stop、SessionEnd；与 CodeBuddy 输出近似同构 | Claude Hooks 官方文档 + Trellis `.claude` 模板 |
| Codex | partial（第二批） | UserPromptSubmit/SubagentStart context；写入 deny 尚无可靠本地证据 | Trellis `.codex/hooks.json` 与 feature/approval 要求 |
| Pi | full potential（第三批） | TypeScript extension 的 tool_call `{ block: true, reason }` 与 before_agent_start context | Pi extension 官方文档 + Trellis `.pi` 模板 |

## Architecture Decision

共享 `.keystone/` 领域核心不分叉，平台只做薄协议适配：

```text
Keystone Core
  - project/spec/task/session storage
  - state machine and policy
  - task/context rendering
  - normalized hook semantics

Platform Adapter
  - config paths and ownership
  - install/remove/doctor plans
  - payload -> normalized event fields
  - semantic effect -> native platform output
  - explicit capability matrix
```

新增目标结构：

```text
src/keystone/
  platforms/
    base.py        # PlatformAdapter protocol and capabilities
    registry.py    # adapter lookup
    codebuddy.py   # existing JSON settings behavior, mechanically migrated
    claude.py      # Claude JSON Hook adapter
    codex.py       # context-only adapter
    pi.py          # extension bundle installer/adapter
  hook/
    model.py       # InjectContext / DenyTool / BlockStop / Noop
    dispatcher.py  # normalized fields -> shared event semantics
```

不设计通用平台配置 AST。JSON settings、Codex hooks + user approval、Pi TypeScript extension 是不同的操作模型；adapter 只共享生命周期计划结果和 semantic effects。

## Capability Rules

- CodeBuddy 和 Claude：可声明 Context + PreToolUse deny；Stop enforce 必须各自真实宿主验证后才宣称。
- Codex：MVP 只支持 `.agents/skills`、AGENTS guidance、UserPromptSubmit/SubagentStart context；不声明 PreToolUse deny 或 Stop gate。用户必须自行启用 `features.hooks = true`、完成 `/hooks` 审批和项目 trust。
- Pi：MVP 先复用 shared skills；extension Hook 是独立 TypeScript 实现，后续才做 `before_agent_start` context 与 `tool_call` block。不得复用 Python stdin/stdout runner 假装支持。
- `policy_mode=strict`、`stop_mode=enforce` 在不具备相应 capability 的 adapter 上必须 WARN 或拒绝配置，不得静默降级成已保护。

## Platform Installation Scope

```text
keystone init --platform codebuddy
keystone init --platform claude
keystone init --platform codex
keystone init --platform pi
keystone doctor --platform <name>
keystone uninstall --platform <name>
```

无 `--platform` 时不创建/修改 `.codebuddy/.claude/.codex/.pi` 配置。适配器只能修改自己可证明拥有的条目，保留所有第三方 Hook、MCP、模型、trust、agent 和命令配置。

## Implementation Sequence

1. 机械迁移 CodeBuddy 到 adapter，所有现有测试和生成 diff 不变。
2. 实现 Claude Code adapter，先真实验证 context 和 deny。
3. 实现 Skills 安装（独立任务）并让 Codex/Pi 通过 `.agents/skills` 获得 workflow 引导。
4. 实现 Codex context-only adapter，提供明确 onboarding/approval diagnostics。
5. 独立实现 Pi extension bundle 和真实宿主 smoke test。

## Acceptance Criteria

- [x] 现有 CodeBuddy init/doctor/uninstall 行为在 adapter 重构后无回归
- [x] `init --platform codebuddy` 与当前 settings diff 等价
- [x] Claude adapter 可无损写/卸载自身注册（真实宿主 smoke test 待用户在 `scripts/claude-smoke.sh` 生成的项目中执行）
- [x] Codex adapter 不会承诺未验证的 deny/Stop 能力，并显式诊断 hooks/trust/approval 前置条件
- [ ] Pi adapter 作为 extension 实现，而不是伪 JSON Hook；tool_call block 与 context 注入有真实 smoke test（**拆分为独立后续任务**，本批只做 shared `.agents/skills`）
- [x] 每个 adapter 的 README capability matrix 标记 verified/experimental/unverified
- [x] 平台安装不修改 MCP、用户级开关或第三方配置

## Batch Outcome (2026-10-03)

本批完成 adapter 边界收敛、Codex context-only adapter、Pi shared-skills 映射与文档/测试：

- `adapters/` 下沉了 settings 路径、事件集合、注册计数、deny 渲染、环境变量兜底和 capability warnings；
  `status` / `doctor` / `doctor --fix` / `uninstall` / hook runner 不再硬编码 CodeBuddy。
- `CodexAdapter` 只注册 `UserPromptSubmit`，只写 `.codex/hooks.json`，doctor 明确列出用户级前置条件和未支持能力。
- `--platform codex|pi` 与 `--platform auto` 统一映射到共享 `.agents/skills/`。
- 保留的待办（非本批）：Claude/Codex 真实宿主 smoke 由用户手工执行；Pi TypeScript extension 另开任务。

## Deferred: Pi Extension (next task)

Pi 的 `before_agent_start` context、`tool_call` deny 与 `session_shutdown` metadata 需要一个 Keystone 自有的 TypeScript extension bundle。它不复用 Python stdin/stdout runner，有自己的 package-data、类型检查和真实 Pi host smoke 门槛。本批刻意不做，避免做出无法兑现的平台门禁承诺。
