# Pi 真实宿主观测记录（R1 交付物）

日期：2026-10-05。环境：`@earendil-works/pi-coding-agent@1.0.2`，Node v22.22.3，provider `149-ali`（deepseek-v4.1-flash），全部通过 `pi -p`（print/非交互模式）实测。测试项目 `/tmp/ks-pi`（隔离，探针 extension 已清理，未修改用户 `~/.pi/` 配置）。

本文是 PRD R1 的三个阻塞问题的实测答案，外加两项计划外发现。**R1 状态：完成。**

## 问题 1：`tool_call` 能否阻断工具？

**能。`{ block: true, reason }` 是正确形状，实测生效。**

探针 handler：

```ts
pi.on("tool_call", (event, ctx) => {
  if (event.toolName === "write") {
    return { block: true, reason: "Keystone: task in PLANNING, writes denied until plan confirmed." };
  }
  return undefined;
});
```

观测结果：

- `write` 被拒，目标文件未创建；reason 原样送达模型（模型在回复中复述了 "Keystone probe gate" 字样）。
- 选择性阻断有效：仅当 `input.path` 匹配模式时 block，其它 write 正常放行。
- **`bash` 同样可以被 block**（`{ block: true }` 对 `toolName === "bash"` 生效，命令未执行）。
- 事件形状：`{ toolName: "write", input: { path, content } }`；bash 为 `{ toolName: "bash", input: { command } }`。
- `ctx` 携带 `cwd`（会话工作目录）与 `signal`（abort signal）。
- 内建工具名（实测 `systemPromptOptions.selectedTools`）：`read`, `bash`, `edit`, `write`（settings 文档另有 `powershell`, `grep`, `find`, `ls`）。

**绕过风险（重要）**：只拦 `write|edit` 时，模型被拒后改用 `bash` 重定向成功创建了文件（实测 `echo > file` 绕过）。结论与 CodeBuddy 一致：**bash 必须纳入写入门禁的工具集**，否则是假保护。CodeBuddy 的 TOOL_MATCHER 语义（门禁状态下 bash 整体视作写入工具、不解析命令内容）可直接照搬到 Pi。

**失败语义（重要，与 Keystone 原则相反）**：handler 抛异常时 Pi **阻止工具执行**（fail-closed，官方文档亦确认 "A `tool_call` handler failure blocks the tool as a fail-safe"）。实测：handler `throw` 后 write 未执行。因此 Keystone extension 的所有 bridge 调用必须 try/catch 并显式 `return undefined` 放行——绝不能让异常逃出去，否则违背"控制类 fail-open"原则且用户无法写文件。

## 问题 2：`session_shutdown` 能否拿到 session id？

**能。`ctx.sessionManager` 在 `session_start` 和 `session_shutdown` 中都可用。**

```json
session_start    {"sessionId":"01a10a3f-0e0c-...","sessionFile":"/home/duny/.pi/agent/sessions/--tmp-ks-pi--/....jsonl"}
session_shutdown {"reason":"quit","sessionId":"01a10a3f-2ff5-..."}
```

- `ctx.sessionManager.getSessionId()` / `getSessionFile()` 均为函数，返回稳定值。
- `session_shutdown` 事件带 `reason`（观测到 `"quit"`）。
- SessionEnd 元数据落盘（`.keystone/.state/events.jsonl`）**可行**。Trellis 没做这个，是它的选择，不是 Pi 的限制。

## 问题 3：`before_agent_start` 返回类型？

**两种注入通道都实测有效：**

1. `{ systemPrompt: string }` —— 整体替换系统提示（拼接原值 + 注入段）。暗号验证：注入 `BLUEHERON-42` 后模型准确复述。
2. `{ message: { customType: string, content: string } }` —— 注入持久自定义消息。暗号验证：prompt 中不含暗号，模型答出注入的 `FALCON-8890`。

事件形状：`{ type, prompt, images, systemPrompt, systemPromptOptions }`。`systemPromptOptions` 含 `selectedTools`, `toolSnippets`, `toolGuidelines`, `promptGuidelines`, `appendSystemPrompt`, `sections`, `cwd`, `contextFiles`, `customPrompt`, `forceSystemPrompt`。官方文档建议优先改结构化 sections（保护 provider prompt cache），整体替换 `systemPrompt` 会使缓存从字节 0 失效——与 Trellis 源码中的快照+缓存策略动机一致。

**`session_start` 确认不能注入 context**（与 Trellis 注释一致）：事件只有 `{ type, reason }`，无返回值通道；context 注入必须走 `before_agent_start`。

## 计划外发现 A：项目级 extension 需要 project trust

- `.pi/extensions/*.ts`（或 `.pi/settings.json` 的 `extensions` 数组）**只在项目被信任后加载**。实测：无 `--approve` 时 extension 完全不加载（factory 都不执行）；`--no-approve` 同样不加载。
- 非交互模式用 `pi -p --approve` 即可信任当前项目（"Trust project-local files for this run"）。
- 用户级 `~/.pi/agent/extensions/` 无需信任即加载（实测确认）。
- 官方文档：项目配置 `.pi` 在 project trust 授予后加载；`project_trust` 事件只有个人级/显式命令行 extension 能参与。
- **对 Keystone 的含义**：`keystone init --platform pi` 后必须提示用户授予项目信任（交互 `/approve` 或 CLI `--approve`），与 Codex 的 trust 前置条件同类。

## 计划外发现 B：共享 skills 已被 Pi 原生识别

`keystone skills install --platform pi` 写入 `.agents/skills/` 后，Pi 自动注册命令（探针读 `pi.getCommands()`）：

```json
{"total":5,"keystone":["skill:keystone-handoff","skill:keystone-plan","skill:keystone-verify"]}
```

`enableSkillCommands` 默认 true。**父任务已交付的 shared-skills 链路在真实 Pi 上确认可用**，Pi 矩阵中这一格可标 verified。

## ExtensionAPI 表面（factory 实测枚举）

`on, registerTool, registerCommand, registerShortcut, registerFlag, registerMessageRenderer, registerMarkdownTransformer, registerEntryRenderer, registerToolRenderer, getFlag, sendMessage, sendUserMessage, appendEntry, setSessionName, getSessionName, setLabel, exec, getActiveTools, getAllTools, getSettings, setActiveTools, getCommands, setModel, getThinkingLevel, setThinkingLevel, registerProvider, unregisterProvider, registerMcpServer, unregisterMcpServer, getMcpServers, registerVirtualModel, unregisterVirtualModel, events`

Keystone extension 只需要：`on`（事件）、可能的 `getSettings`。不需要 registerTool/UI/provider。

## 对设计文档假设的最终裁定

| 设计假设 | Trellis 源码 | Pi 实测 | 裁定 |
|---|---|---|---|
| `tool_call → {block:true,reason}` | 无此代码 | 生效 | **假设成立** |
| `session_shutdown → session id` | 只清内存 | 拿得到 | **假设成立** |
| `session_start` 注入 context | 不能 | 不能，注入在 `before_agent_start` | **假设成立** |
| extension 由 jiti 加载 | 无依赖证据 | 官方文档确认 jiti | **成立** |

## 已定的实现决策（由观测直接推出）

1. 写入门禁工具集 = `write | edit | bash`（照搬 CodeBuddy TOOL_MATCHER 语义：门禁状态整体拦，不解析 bash 命令内容）。
2. fail-open 实现方式：bridge 调用全部 try/catch，异常路径显式 `return undefined`；利用"handler 抛错=fail-closed"这一 Pi 语义反推，**任何代码路径都不允许向 Pi 抛异常**。
3. context 注入首选 `message`（customType）通道，`systemPrompt` 拼接仅在需要静态项目上下文时使用；对齐 prompt-cache 友好策略。
4. SessionEnd 落盘走 `session_shutdown` + `ctx.sessionManager.getSessionId()`。
5. init/doctor 必须提示 project trust 前置条件（`--approve` 或交互式批准）。