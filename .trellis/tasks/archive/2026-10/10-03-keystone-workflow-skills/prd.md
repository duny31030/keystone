# Keystone 前期工作流 Skills

## Goal

为 Keystone 增加第一批高价值的项目级 workflow skills，帮助 AI 在计划、验证和交接阶段正确使用现有 `.keystone/` 任务状态机与文件产物，而不复制或绕过 Hook 的权威控制。

## Architecture Decision

Skills 是**显式的辅助流程入口**，Hooks 是**自动上下文和强制门禁**：

- Hook 仍然负责任务绑定、状态注入、计划前/完成后写入拒绝和 `.keystone` 裁判状态保护；
- Skill 只指导 AI 读取任务、填写明确的 Markdown artifact、执行或记录验证、生成交接摘要；
- Skill 不能直接改 `task.json`、`project.json`、`.state/`，不能自行推进、完成或重开任务；所有状态变更必须调用 `keystone task` CLI，并由用户明确确认；
- 首批不做 status/doctor/events skills，因为 CLI 已经是更精确的入口。

## MVP Skills

### `keystone-plan`（P0）

触发：用户开始非平凡任务，任务在 TODO/PLANNING，或需要更新计划。

读取：`project.json`、`task.json`、`prd.md`、现有 `plan.md`、`specs/*.md`。

输出：已有的 `tasks/TASK-XXX/plan.md`。

规则：先执行 `keystone task show <id>`；缺计划时执行 `keystone task plan <id>`；填写目标、影响范围、步骤、验证方案和风险；等待用户确认后才建议执行 `keystone task advance <id>`。

### `keystone-verify`（P0）

触发：用户请求验证，或任务处于 VERIFYING。

读取：项目 build/test 命令、task/prd/plan、实际改动和实际命令输出。

输出：第一版输出结构化会话报告；不强制创建 `verification.md`，等跨会话证据确有价值时再引入版本化 artifact。

规则：如实记录实际命令、结果、失败、跳过和风险；不把测试通过视作完成授权；用户确认后才调用 advance/complete，失败时可建议退回 IMPLEMENTING。

### `keystone-handoff`（P1）

触发：会话暂停、换 agent、上下文将丢失，或用户明确要求交接。

读取：当前任务 artifact 与 `keystone events list --task <id>` 的会话线索。

输出：建议 `tasks/TASK-XXX/handoff.md`，记录当前阶段、已完成内容、验证证据、阻塞项、未决事项和下一步命令。

规则：handoff 不改变任务状态；SessionEnd 不是完成依据；不覆盖已有 handoff.md，除非用户明确授权。

## Installation and Distribution

Canonical source 放入 Python package：

```text
src/keystone/assets/skills/
  keystone-plan/SKILL.md
  keystone-verify/SKILL.md
  keystone-handoff/SKILL.md
```

npm 同步时随 `src/keystone` 进入 `npm/python/keystone/assets/`，确保 PyPI wheel 与 npm tarball 都包含同一份技能源。

新增显式命令（不由 `keystone init` 默认执行）：

```text
keystone skills list
keystone skills install --platform auto|all|agents|claude|codebuddy|zcode
keystone skills install --platform <name> --dry-run
keystone skills install --platform <name> --force
keystone skills doctor
```

目标路径：

| 平台/别名 | 目标 |
|---|---|
| 通用 / Codex / Pi | `.agents/skills/keystone-*/SKILL.md` |
| Claude Code | `.claude/skills/keystone-*/SKILL.md` |
| CodeBuddy | `.codebuddy/skills/keystone-*/SKILL.md` |
| ZCode | `.zcode/skills/keystone-*/SKILL.md` |

`auto` 仅向项目中已经存在的平台目录写入；`all` 才创建全部平台目录。已有非 Keystone 管理的同名 skill 默认报冲突、零修改；只有 `--force` 才覆盖。第一版仅支持项目级安装，绝不写用户主目录或 MCP 配置。

## Acceptance Criteria

- [x] 三个 canonical SKILL.md 均包含触发条件、前置读取、产物、边界和安全规则
- [x] `skills list` 显示可用 skills 与平台安装状态
- [x] `skills install --dry-run` 零写入且显示逐文件计划
- [x] `skills install --platform auto` 只向已有平台目录写入
- [x] `skills install --platform all` 正确安装 Claude/CodeBuddy/ZCode 和 shared agents 目标
- [x] 同名非托管 skill 发生冲突时零修改；`--force` 行为明确
- [x] 任何 skill 安装不会修改 Hook、MCP、任务状态或用户级配置
- [x] wheel 和 npm tarball 都包含 canonical skill 资源
- [x] README 记录安装与职责边界
