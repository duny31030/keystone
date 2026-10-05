# Trellis Pi 实现的源码实证

来源：本机 `@mindfoldhq/trellis@0.6.17`（`/home/duny/.nvm/versions/node/v22.22.3/lib/node_modules/@mindfoldhq/trellis/dist/`），2026-10-05 直接读 dist 产物，非文档推测。

本文修正了 `10-03-multi-platform-adapter` 设计文档中三处未被验证的 Pi 假设。

## 1. 注册方式：原生 TypeScript extension

`dist/templates/pi/settings.json`（模板原样）：

```json
{
  "enableSkillCommands": true,
  "extensions": ["./extensions/trellis/index.ts"],
  "prompts": ["./prompts"]
}
```

- Pi 原生从 `.pi/settings.json` 的 `extensions` 数组加载 TS 入口。
- 无需任何 stdin/stdout 协议，无需 JSON settings hook 注册。
- 没有 `jiti` 依赖出现在 Trellis 的 package.json 里（deps 仅 chalk/commander/figlet/giget/inquirer/undici/zod + `@mindfoldhq/trellis-core`）。**我们设计中"由 jiti runtime 加载"的表述属于推测，应降级为待确认。**

## 2. 元数据中写死的平台事实

`dist/types/ai-tools.js:274-289`：

```js
pi: {
  name: "Pi Agent",
  templateDirs: ["common", "pi"],
  configDir: ".pi",
  supportsAgentSkills: true,
  cliFlag: "pi",
  defaultChecked: false,
  hasPythonHooks: false,     // ← 明确不提供 Python hooks
  templateContext: {
    cmdRefPrefix: "/trellis-",
    executorAI: "Bash scripts or tool calls",
    userActionLabel: "Slash commands",
    agentCapable: true,
    hasHooks: true,          // ← 但提供 extension hooks
    cliFlag: "pi",
  },
},
```

`hasPythonHooks: false` + `hasHooks: true` 的二分法，是"不得复用 Python hook runner 假装支持 Pi"这条设计约束的原始出处。同文件注释还记录：`hasHooks/hasPythonHooks` 不得在宿主真正消费 hook stdout 前置 true（Grok 条目旁）。

## 3. extension 入口签名与实际注册的钩子点

`dist/templates/pi/extensions/trellis/index.ts.txt`，2124 行，`export default function trellisExtension(pi)`：

```ts
export default function trellisExtension(pi: {
  registerTool?: (tool: JsonObject) => void;
  registerShortcut?: (
    key: string,
    opts: { description?: string; handler: (ctx: PiExtensionContext) => unknown },
  ) => void;
  on?: (event: string, handler: (event: unknown, ctx?: PiExtensionContext) => unknown) => void;
  getThinkingLevel?: () => string;
}): void
```

实际注册的 6 个事件（`grep 'pi.on?.'`）：

| 事件 | 行号 | 实际用途 |
|---|---|---|
| `session_start` | 2028 | 仅 `ctx.ui.notify(...)` 提示用户用 `/trellis-start`；**不注入 context** |
| `session_shutdown` | 2035 | 仅清内存 `nativeCards.clear()`；**不落盘、不写事件** |
| `tool_call` | 2039 | 仅给 `bash` 命令前面拼 `export TRELLIS_CONTEXT_ID=...`；**不返回阻止结果** |
| `tool_result` | 2046 | 仅标记失败的 subagent 结果为 `isError: true` |
| `before_agent_start` | 2066 | **唯一真正注入 context 的地方** |
| `context` | 2121 | 空 handler，只调 `getKey` |

## 4. 三处修正：我们设计里的假设 vs 源码现实

### 4.1 `tool_call` deny —— 源码中不存在

设计文档写的 `tool_call → { block: true, reason }` 在 Trellis 实现中**没有任何支撑**。全文 grep `block:` 零命中。真实 handler：

```ts
pi.on?.("tool_call", (event, ctx) => {
  const k = getKey(event, ctx);
  const ev = event as { toolName?: string; input?: JsonObject };
  if (
    ev.toolName === "bash" &&
    isObj(ev.input) &&
    typeof ev.input.command === "string" &&
    !cmdHasTrellisCtx(ev.input.command)
  )
    ev.input.command = `export TRELLIS_CONTEXT_ID=${shellQuote(k)}; ${ev.input.command}`;
});
```

它改写 `input.command` 后**返回 undefined**，不做拦截。Pi agent 工具名（`dist/templates/pi/agents/trellis-implement.md` frontmatter）为：`read, write, edit, bash, find, grep` —— 这是目前唯一可用的工具名证据，但**未被 Keystone 验证**。

结论：`tool_call` 能否阻断写入、返回什么形状、覆盖哪些工具，全部是**未验证假设**。这是本任务的头号调研项。

### 4.2 `session_shutdown` → SessionEnd metadata —— 源码中是清内存

```ts
pi.on?.("session_shutdown", () => {
  nativeCards.clear();
  activeSubagentToolCallId = null;
});
```

无 fd 写入、无 session id 捕获。Trellis 改用另一条路径维持跨调用关联：`tool_call` 时把 `TRELLIS_CONTEXT_ID` 注入 bash 环境变量。**"session_shutdown 能拿到可用于落盘的 session id"未经证实。**

### 4.3 `session_start` 不注入 context

Trellis 的注释说明（`pi.js:resolvePiCommands`）：

> Pi's `session_start` event cannot mutate model context; the strong startup injection happens later at agent start.

即 `session_start` **不能修改模型上下文**，真正的启动注入只能在 `before_agent_start`。这与我们当前"SessionStart 注入"的 CodeBuddy 心智模型不同，Pi 上必须合并到 agent start。

## 5. 已确认可用的 `before_agent_start` context 注入

```ts
pi.on?.("before_agent_start", (event, ctx) => {
  const k = getKey(event, ctx);
  const key = cacheKey(k, ctx);
  const cur = (event as { systemPrompt?: string }).systemPrompt ?? "";
  ...
  const freshTaskCtx = buildContext(root, "trellis-implement", k);
  let taskCtx = taskCtxSnapshot.get(key);
  if (taskCtx === undefined) {
    taskCtx = freshTaskCtx;
    taskCtxSnapshot.set(key, taskCtx);
    lastSentTaskCtx.set(key, freshTaskCtx);
  }
  const updates: string[] = [];
  ...
  return {
    message: content
      ? { customType: "trellis-runtime-context", content, display: false }
      : undefined,
    systemPrompt: [cur, startup, taskCtx].filter(Boolean).join("\n\n"),
  };
});
```

两个关键机制：

1. 返回对象同时带 `systemPrompt`（拼接后的完整 system prompt）与 `message`（`customType` 持久消息）。
2. **system prompt 快照 + 缓存**：任务上下文只在首次写入 `systemPrompt`，后续磁盘变化通过持久消息通道下发，注释解释原因是 provider 的 prefix cache 一旦 system prompt 变化就从字节 0 失效。这是真实性能约束，不是可选优化。

## 6. Python bridge 契约（可照抄）

`runContextScript`（`:1157`）：

```ts
function runContextScript(root: string, key: string | null, args: string[]): string {
  const script = join(root, ".trellis", "scripts", "get_context.py");
  if (!exists(script)) return "";
  try {
    const py = process.platform === "win32" ? "python" : "python3";
    const result = spawnSync(py, [script, ...args], {
      cwd: root,
      env: key ? { ...process.env, TRELLIS_CONTEXT_ID: key } : process.env,
      encoding: "utf-8",
      timeout: SESSION_OVERVIEW_TIMEOUT_MS,   // 1500ms
      windowsHide: true,
    });
    if (result.status !== 0) return "";
    return (result.stdout ?? "").trim();
  } catch {
    return "";
  }
}
```

要点：**显式脚本路径 + JSON stdout**，不是 hook stdin/stdout 协议；非零退出即返回空串（fail-open）；1500ms 超时；按 turn 缓存（`turnCache`，1500ms TTL）避免重复 spawn python。

## 7. 项目根定位

`findRoot`（`:972`）**只认 `.trellis/` 目录**作为根标记，且刻意注释说明：裸 `.pi` 可能是 Pi 的全局配置（`~/.pi`），接受它会导致 root 解析过早停在 `~`；`.trellis` 若为普通文件也拒绝。

`resolveRoot(ctx)` 优先 `ctx.cwd`，回退 `process.cwd()`，理由：host 启动目录可能与 session cwd 不同（pi-web / RPC / 多项目宿主）。

对 Keystone 的直接含义：我们的 `find_layout`（找 `.keystone/`）语义与之一致，但**必须用 `ctx.cwd` 而非 `process.cwd()`**。

## 8. Session id 来源与归一

`contextKey`（`:1062`）取值顺序：

1. `ctx.sessionManager.getSessionId()`
2. `process.env.PI_SESSION_ID`
3. `process.env.PI_SESSIONID`
4. input 里的 `session_id` / `sessionId` / `sessionID`
5. 回退 `ctx.sessionManager.getSessionFile()` / `transcript_path`

归一化：非 `[A-Za-z0-9._-]` 字符替换为 `_`，截断后附加 hash，最终形如 `pi_<normalized>_<hash>`。

**这是 Keystone 在 Pi 上拿 session id 的候选途径，但同样未经我们实测。**

## 9. 共享 skills 的 corroboration

`dist/configurators/pi.js` 注释原文：

> Shared skills go to `.agents/skills/` (Pi discovers this cross-platform workspace alias natively). Neutral resolver keeps content byte-identical to Codex's/Gemini's writes for the same skill names, avoiding the duplicate/conflicting-skill installs reported in #447.

Pi 原生识别 `.agents/skills/`；与 Codex/Gemini 写同一目录时必须字节一致，否则触发重复/冲突安装（上游 issue #447）。Keystone 已落地的 `SHARED_TARGET_LABEL` + codex/pi 共用目标方向正确，且应继续保持内容 byte-identical。

## 10. 规模参照

Trellis 的 Pi extension 2124 行，其中 Keystone 不需要的部分：`trellis_subagent` 工具注册（派生 Pi 子进程、JSON 模式解析、并发/链式调度）、TUI 卡片渲染（`@earendil-works/pi-tui` 懒加载）、权限转发三层机制（`PI_SUBAGENT_PARENT_SESSION` / `PI_SUBAGENT_CHILD=1` / serving heartbeat，上游 issue #610）、`registerShortcut("alt+o")`。

Keystone 的范围应显著更小：context 注入 + 状态机/策略桥接 + 事件落盘，无 subagent、无 TUI、无工具注册。

## 结论：必须先真人验证的三个问题

1. `tool_call` 的返回契约：能否阻断工具（字段名与形状），覆盖哪些 Pi 原生工具，有无绕过路径。
2. `session_shutdown` 是否暴露可用的 session id / transcript 路径用于落盘；若不暴露，SessionEnd 元数据只能换别的信号源。
3. `before_agent_start` 返回 `systemPrompt` + `message` 的确切类型与 Pi 版本兼容区间。

在这三点有真实 Pi 观测结果之前，不写 extension 代码。