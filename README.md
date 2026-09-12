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
└── .state/                   # gitignored：会话绑定、元数据事件日志
```

共享层随 git 走（版本化、可评审、多人合并）；运行时状态不进仓库。

## 安装

```bash
# 仓库内开发安装（Python ≥ 3.9，运行时零依赖）
pip install -e .
```

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
- **结束前**：注入完成检查清单（`stop_mode: enforce` 时未完成任务会直接阻止结束）。

## 任务状态机

```
TODO → PLANNING → PLAN_CONFIRMED → IMPLEMENTING → VERIFYING → COMPLETED
       （VERIFYING → IMPLEMENTING 验证不通过打回；COMPLETED → IMPLEMENTING 重新打开）
```

状态只由用户手动推进，Keystone 不判断代码正确性：

```bash
keystone task list
keystone task show TASK-001
keystone task advance TASK-001          # 沿主链走下一步（--to 可指定合法目标）
keystone task complete TASK-001         # VERIFYING → COMPLETED
keystone task reopen TASK-001           # COMPLETED → IMPLEMENTING
```

## Hook 事件

| 事件 | 行为 |
|---|---|
| `SessionStart` | 注入项目资料 + 规范 + 禁止事项 |
| `UserPromptSubmit` | 解析会话绑定任务（支持 `TASK-123` / `#123` 编号切换），注入任务上下文与阶段要求 |
| `PreToolUse` | 流程控制：计划确认前禁止写文件、完成任务后禁止继续修改、保护 `.keystone` 状态文件不被 AI 直接改写 |
| `PostToolUse` | 记录元数据事件（工具名/成败/时间），不记录任何内容 |
| `Stop` | 注入完成检查清单；enforce 模式阻止未完成任务结束；`stop_hook_active` 防循环 |
| `SessionEnd` | 记录会话结束元数据 |
| `PreCompact` | 上下文压缩前恢复关键信息（项目、任务、阶段、验收标准、验证命令） |

异常原则：**控制类 Hook fail-open，记录类 Hook fail-silent** —— Keystone 出任何问题都不影响 CodeBuddy 正常使用。未初始化 `.keystone/` 的项目完全零打扰。

## 配置项（`.keystone/project.json`）

| 字段 | 说明 | 默认 |
|---|---|---|
| `stop_mode` | `reminder` 仅提醒 / `enforce` 未完成阻止结束 | `reminder` |
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
