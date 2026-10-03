# Keystone

**Keystone 是 CodeBuddy 的流程与上下文增强层。**

CodeBuddy 负责读写代码、执行 Maven / pytest 等工程动作；Keystone 通过 Hook 机制注入项目规范与任务上下文，并对开发流程做有限控制（如：计划确认前禁止写文件、任务完成后禁止继续修改）。

明确边界：Keystone **不读取代码、不修改代码、不执行构建测试**，不需要 MCP，不开发 CodeBuddy 插件。它只处理 Hook 元数据、项目配置、任务状态和上下文生成。

## 架构（v1：去服务端化）

```text
CodeBuddy
   │  Hook 事件（stdin JSON，PascalCase 事件名）
   ▼
keystone-hook <event>          ← 短生命周期 CLI，纯标准库实现
   │  从 cwd 向上定位 .keystone/
   │  直读直写本地文件（无网络依赖）
   ▼
HookOutput JSON → stdout，退出码 0
```

所有状态存在目标仓库的 `.keystone/` 目录：

```
.keystone/
├── project.json              # git：项目标识、语言/框架、构建/测试命令、stop_mode、policy_mode
├── specs/                    # git：architecture.md / coding.md / general-ban.md（规范即文件，PR 评审）
├── tasks/TASK-001/           # git：task.json（状态机）+ prd.md（任务描述）
└── .state/                   # gitignored：会话绑定、SessionEnd 元数据日志
```

共享层随 git 走（版本化、可评审、多人合并）；运行时状态不进仓库。

## 安装

```bash
# npm（Node 垫片 + 内嵌 Python 源码，无需 pip 依赖）
npm install -g keystone-hook

# PyPI（TestPyPI 测试站）
pip install --index-url https://test.pypi.org/simple/ keystone-hook

# 仓库内开发安装（Python ≥ 3.9，运行时零依赖）
pip install -e .
```

两种安装方式提供同一套 CLI 行为：npm 包内嵌同一份 Python 源码，由 Node 垫片定位 `python3` 执行（仍需要 Python >= 3.9，但无需再通过 pip 安装 Keystone；可用 `KEYSTONE_PYTHON` 指定解释器）。npm 装的包发布新版本后用 `npm update -g keystone-hook` 升级。

## 快速上手

```bash
cd <你的项目>                 # 目标项目（java/maven 或 python/pytest）
keystone init                 # 自动探测语言，生成 .keystone/ 并注册 CodeBuddy hooks
keystone task create "实现登录" -d "手机号+验证码登录" -a "接口通;测试覆盖"
```

在 CodeBuddy 中打开项目即可：

- **会话开始**：自动注入项目技术栈、构建/测试命令与规范；
- **每次提交 prompt**：自动注入当前任务的描述、验收标准和阶段要求；首次会登记"待确认任务"（不会根据自然语言自动创建正式任务）；
- **计划确认前**（TODO/PLANNING）：写文件类工具被拦截，直到 `keystone task advance` 推进到 PLAN_CONFIRMED；
- **结束前**：`Stop` reminder 路径会注入完成检查清单；在 CodeBuddy 中已实测。

## 项目诊断与生命周期

```bash
# 预览 init 将创建或更新什么；绝不写入
keystone init --dry-run

# 汇总项目、任务、已注册 events 与本地运行态
keystone status

# 检查本地文件、settings 注册与可修复配置问题
keystone doctor

# 自动修复可安全修复的问题（补齐缺失的 Hook 注册、清理退役条目、补 gitignore、创建缺失目录和规范模板）
keystone doctor --fix

# 只注销 Keystone hooks，保留 .keystone/ 任务、规范和其他工具配置
keystone uninstall

# 预览彻底移除
keystone uninstall --purge --dry-run

# 确认删除 .keystone/ 项目资料（非交互环境必须显式 --yes）
keystone uninstall --purge --yes

# 查看本地 SessionEnd 事件记录（可按任务/会话/事件类型过滤）
keystone events list
keystone events list --task TASK-001
keystone events list --session <id>
```

`doctor` 只检查磁盘上的项目配置和 `.codebuddy/settings.json` 的静态注册，不会声称 CodeBuddy 已加载或实际触发 Hook。`doctor --fix` 自动修复可安全修复的问题：补齐缺失的五个已验证 Hook 注册、清理退役的 PostToolUse/PreCompact 条目、补 `.gitignore` 的 managed block、创建缺失的 `.keystone/` 目录结构和规范模板。**不修复**损坏的 JSON 文件或用户自定义内容。`status` 是只读摘要；两者都不执行构建、测试或修改代码。

`uninstall` 从所有 CodeBuddy event 中移除 Keystone command，保留混合 rule 内的第三方 command、matcher 与 `.codebuddy/` 目录。默认保留 `.keystone/`；只有 `--purge --yes` 才会删除任务和规范，且只移除 Keystone 自己写入的 gitignore managed block。

## Platform Support

| Platform | Status | Capabilities |
|---|---|---|
| CodeBuddy | Verified | Project/task context, file-tool deny, plan/completion gates, Stop reminder, SessionEnd metadata |
| Claude Code | Experimental | Project settings, context hooks, native file-tool deny renderer and SessionEnd configuration are implemented; real host smoke is still required |
| Codex | Planned | Future context + shared Skills support; no deny/Stop guarantee |
| Pi | Planned | Future TypeScript extension; no Python Hook compatibility claim |

```bash
# CodeBuddy remains the default
keystone init

# Configure only Claude Code hooks in the same project
keystone init --platform claude
keystone doctor --platform claude
keystone uninstall --platform claude
```

Claude registers only native file tools (`Write|Edit|MultiEdit|NotebookEdit`) for PreToolUse. It does not claim Bash or MCP write protection. Claude `Stop` enforce remains experimental until verified in a real Claude Code session.

## Workflow Skills

Keystone 提供项目级 workflow skills，帮助 AI 正确使用任务计划、验证和交接流程。Skills 是显式辅助入口；Hook 仍然是任务状态、上下文注入和写入门禁的权威控制面。

```bash
# 查看可用 Skills 和当前项目安装状态
keystone skills list

# 仅安装到已经存在的平台目录（默认，不创建新的 AI 配置目录）
keystone skills install --platform auto

# 预览向全部目标安装（不写入）
keystone skills install --platform all --dry-run

# 安装到所有项目级目标
keystone skills install --platform all
```

第一批 Skills：

| Skill | 作用 | 产物 |
|---|---|---|
| `keystone-plan` | 从任务、规范和需求形成可评审计划 | `plan.md` |
| `keystone-verify` | 组织实际验证证据、失败与风险 | 结构化会话报告 |
| `keystone-handoff` | 保存跨会话/跨 Agent 交接事实 | `handoff.md` |

安装目标：`.agents/skills/`（Codex/Pi 通用）、`.claude/skills/`、`.codebuddy/skills/`、`.zcode/skills/`。同名但非 Keystone 管理的 Skill 默认产生冲突并保持零修改；只有显式 `--force` 才覆盖。Skills 不修改 Hook、MCP、任务状态或用户级配置。

## 任务状态机

```
TODO → PLANNING → PLAN_CONFIRMED → IMPLEMENTING → VERIFYING → COMPLETED
       （VERIFYING → IMPLEMENTING 验证不通过打回；COMPLETED → IMPLEMENTING 重新打开）
```

状态只由用户手动推进，Keystone 不判断代码正确性：

```bash
keystone task list
keystone task show TASK-001
keystone task plan TASK-001            # 生成 plan.md 模板（PLANNING 阶段）
keystone task advance TASK-001         # 沿主链走下一步（--to 可指定合法目标）
keystone task complete TASK-001        # VERIFYING → COMPLETED
keystone task reopen TASK-001          # COMPLETED → IMPLEMENTING
```

**计划确认前置条件**：`PLANNING → PLAN_CONFIRMED` 要求任务目录存在 `plan.md`。执行 `keystone task plan TASK-001` 会生成包含目标、影响范围、实施步骤、验证方案、风险与未决事项的模板；不强制内容结构，只要求文件存在且非空。`keystone task show` 和 `keystone task list` 会显示计划文件状态。

## CodeBuddy 已验证 Hook

下列默认 hooks 已在真实 CodeBuddy 会话中验证；`keystone init` 只注册这些事件。

| 事件 | 已验证行为 |
|---|---|
| `SessionStart` | 注入项目资料、规范与禁止事项 |
| `UserPromptSubmit` | 解析会话绑定任务（支持 `TASK-123` / `#123` 切换），注入任务上下文与阶段要求 |
| `PreToolUse` | 计划确认前真实拒绝写入；任务完成后真实拒绝继续修改；保护 `.keystone` 状态文件不被直接改写 |
| `Stop` | `reminder` 模式注入完成检查清单（已实测）；`enforce` 的 block 输出已发送但当前 CodeBuddy 未表现出真正阻止结束 |
| `SessionEnd` | 记录会话级元数据（结束时间、原因、session ID、当前任务）到 `.keystone/.state/events.jsonl` |

`stop_hook_active` 循环保护仅在本地协议测试中验证；真实 CodeBuddy 中会话结束由宿主控制，无法通过重复发送"结束会话"来触发二次 Stop，因此该字段的实际效果尚不能确认。`PostToolUse` 与 `PreCompact` 未在当前 CodeBuddy 版本确认，因此 0.1.1 起不再默认注册或公开为可用能力。

异常原则：**控制类 Hook fail-open，记录类 fail-silent** —— Keystone 出任何问题都不影响 CodeBuddy 正常使用。未初始化 `.keystone/` 的项目完全零打扰。

## 配置项（`.keystone/project.json`）

| 字段 | 说明 | 默认 |
|---|---|---|
| `stop_mode` | `reminder` 注入检查清单（已实测）/ `enforce` 返回 block 输出，但当前 CodeBuddy 未表现出阻止结束的行为 | `reminder` |
| `policy_mode` | `permissive` / `strict`（strict 下未绑定任务也禁止写文件） | `permissive` |
| `test_command` / `build_command` | 注入给 AI 的验证/构建命令 | 按语言预设 |

## 开发

```bash
uv venv .venv && uv pip install -e '.[dev]'
.venv/bin/pytest
```

代码分层：`hook/`（stdin/stdout 协议与事件分发）、`core/`（状态机、上下文渲染等业务核心）、`store/`（`.keystone/` 目录存储实现）、`cli.py`（init / task 命令）、`scaffold.py`（settings.json 合并式注册）。

## Phase 2 展望（中心服务端）

当出现以下需求时再引入服务端：团队集中管控规范与任务、跨项目任务看板与事件分析、状态防篡改的硬约束、用户与权限。`core/` 与存储已解耦，届时为 core 套一层 HTTP 壳、store 换 API 客户端即可，Hook 协议不变。
