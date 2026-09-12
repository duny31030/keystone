# Keystone MVP: CodeBuddy 流程与上下文增强层

## Goal

Keystone 是 CodeBuddy 的流程与上下文增强层：通过 CodeBuddy Hook 机制，在会话和工具调用过程中注入项目规范与任务上下文，并对开发流程做有限控制。

明确边界（Keystone 不做）：

- 不读取代码、不修改代码；
- 不执行 Maven / pytest 等构建测试命令；
- 不需要 MCP；不开发 CodeBuddy 插件；
- 只处理 Hook 元数据、项目配置、任务状态和上下文生成。

## Architecture Decision（本任务已确认）

**v1 去服务端化**：状态全部存目标仓库 `.keystone/` 目录（git 版本化共享层 + gitignored 运行时层），`keystone-hook` 直读直写本地文件。原需求文档中的中心服务端（HTTPS + SQLite）推迟为 Phase 2，触发条件：团队集中管控、硬防篡改、跨项目聚合。

技术栈：Python ≥ 3.9，纯标准库实现。

## Requirements

### R1 Hook 事件（CodeBuddy Hook 协议，PascalCase 事件名）

- `SessionStart`（matcher: startup/clear/compact）：注入项目信息、技术栈、构建/测试命令、架构规范、编码规范、通用禁止事项。同会话不重复注入动态任务内容。
- `UserPromptSubmit`（核心）：识别项目 → 解析会话绑定任务 → 用户明确输入任务编号则切换 → 注入任务描述、验收标准、当前阶段要求。任务策略：已有活动任务则继续；无活动任务则创建"待确认任务"或提示选择；不根据自然语言自动创建正式任务。
- `PreToolUse`：计划确认前（TODO/PLANNING）禁止写文件类工具；任务 COMPLETED 后禁止继续修改，除非重新打开；另拦截对 `.keystone` 状态文件的直接写（防 AI 篡改裁判状态）。兼容多套工具名（Write/Edit/write_to_file/replace_in_file/apply_patch 等）。
- `PostToolUse`：记录元数据事件（工具名、项目、session、任务、成败、时间），不记录内容类信息。
- `Stop`：提醒模式（默认）注入完成前检查清单；可选强制模式阻止未完成任务结束；`stop_hook_active=true` 直接放行防循环。
- `SessionEnd`：记录会话结束元数据，不作为任务完成的依据。
- `PreCompact`：压缩前重新注入精简上下文（项目、任务、阶段、验收标准、验证命令、未完成事项）。

### R2 任务状态机（用户手动推进为主）

`TODO → PLANNING → PLAN_CONFIRMED → IMPLEMENTING → VERIFYING → COMPLETED`；允许 VERIFYING→IMPLEMENTING（打回）、COMPLETED→IMPLEMENTING（重开）。状态只经 `keystone task` CLI 变更；Keystone 不判断代码正确性、不自动推断完成。

### R3 本地配置与初始化

- `keystone init` 生成 `.keystone/`（project.json + specs 模板 + tasks/）与 `.codebuddy/settings.json`（合并式，不破坏已有 hooks）；
- java+maven、python+pytest 预设；
- Token/密钥不入仓库（本版无服务端，密钥需求随 Phase 2 消失）。

### R4 异常原则

控制类 Hook fail-open、记录类 Hook fail-silent；文件损坏/缺失时不影响 CodeBuddy 正常使用。预留 `policy_mode: permissive | strict`。

## Out of Scope

- 代码读取/索引、Diff 分析、自动执行构建测试、自动提交 Git；
- MCP、CodeBuddy 插件、多 Agent 适配、复杂策略编排、管理 UI；
- 中心服务端（Phase 2）。

## Acceptance Criteria

- [x] `keystone init` 在干净目录生成 `.keystone/` + 合并式 `.codebuddy/settings.json` + gitignore 追加，且不破坏已存在的 hooks 配置
- [x] 七个 hook 事件 `keystone-hook <event>` 均能按协议处理：注入事件输出 `hookSpecificOutput.additionalContext`；PreToolUse deny 输出 `permissionDecision`；Stop 提醒/强制/防循环行为正确
- [x] 任务状态机：合法流转成功、非法流转报错；`keystone task create/list/show/advance/complete/reopen` 可用
- [x] UserPromptSubmit 能识别 `TASK-123` / `#123` 编号并切换会话绑定；无绑定时按任务策略处理
- [x] PostToolUse / SessionEnd 只记录元数据（不含文件内容、diff、命令输出）
- [x] 服务异常情形（此架构下即文件缺失/损坏）遵循 fail-open/fail-silent，不影响 CodeBuddy 运行
- [x] pytest 全部通过；E2E 冒烟（临时项目 init → 逐事件管道验证）通过
