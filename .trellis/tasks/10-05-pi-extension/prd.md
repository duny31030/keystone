# Pi TypeScript Extension 支持

## Goal

为 Pi Agent 实现 Keystone 自有的 TypeScript extension，使 Pi 用户获得与 CodeBuddy 等价的任务上下文注入、写入门禁和会话记录能力，同时**不**把 Python Hook stdin/stdout runner 伪装成 Pi runtime。

本任务的核心不是"写一个 extension"，而是"在真实 Pi 上确认哪些能力可以兑现，再只实现能兑现的那部分"。

## Background

`10-03-multi-platform-adapter` 已完成 Pi 能确定兑现的部分：`keystone skills install --platform pi` 安装到共享 `.agents/skills/`，`--platform auto` 识别 `.pi/` 根目录。Pi 的 hook 能力（context / deny / session metadata）被明确拆出到本任务。

源码调研（见 `research/trellis-pi-reference.md`，基于本机 `@mindfoldhq/trellis@0.6.17` dist 实证）确认：

- Pi 用**原生 TypeScript extension**（`.pi/settings.json` 的 `extensions` 数组），不是 JSON hook。
- Trellis 元数据明确 `hasPythonHooks: false` + `hasHooks: true`。
- Trellis 的 extension **不做 deny**：`tool_call` 只改写 bash command 字符串，返回 undefined。
- Trellis 的 `session_shutdown` **不落盘**，只清内存。
- Trellis 的 `session_start` **不能修改模型上下文**，真正的注入在 `before_agent_start`。

因此设计文档里"`tool_call → { block: true, reason }`"与"`session_shutdown → SessionEnd metadata`"是**未验证假设**，不能直接实现。

## Non-Goals

- 不派生 Pi subagent（不实现 `trellis_subagent` 等价物）。
- 不做 TUI 渲染、快捷键、卡片。
- 不做权限转发（上游 issue #610 那套三层机制）。
- 不写用户级 Pi 配置（`~/.pi`）。
- 不注册 Pi 工具（`registerTool`），除非 context 注入被证明做不到。
- 不承诺任何未在真实 Pi 上观测到的门禁行为。

## Requirements

### R1. 真实 Pi 观测（阻塞性前置）

在写任何 extension 代码前，必须在真实 Pi 会话中确认三件事，并把原始观测记录到 `research/pi-host-observations.md`：

1. **`tool_call` 返回契约**：能否阻断工具调用？字段名与形状是什么（`block`? `deny`? 抛异常?）？覆盖哪些 Pi 原生工具（候选：`write`/`edit`/`bash`，来自 Trellis agent frontmatter）？是否存在绕过路径？
2. **`session_shutdown` 上下文**：handler 能否拿到 session id / transcript 路径？拿到的值在进程生命周期内是否可用？
3. **`before_agent_start` 返回类型**：`systemPrompt` 与 `message.customType` 的确切类型、是否会被后续调用覆盖、是否存在长度上限。

若 R1 任一项无法确认，对应能力标记为 unsupported 并写入 capability matrix，**不以推测实现**。

> **R1 已完成（2026-10-05）**：三项契约全部实测确认可用，另有两项计划外发现（项目级 extension 需 project trust；`tool_call` handler 抛错为 fail-closed）。详见 `research/pi-host-observations.md`，其中"已定的实现决策"一节直接约束 R2/R3 设计。

### R2. Extension bundle

在 R1 结论确定后，产出：

```text
src/keystone/assets/pi/
  extensions/keystone.ts         # extension 入口
  settings.fragment.json         # 待合并进 .pi/settings.json 的片段（含 extensions 路径）
```

- 入口导出 `default function keystoneExtension(pi)`，仅使用 R1 证实的 `pi.on(...)` / `pi.registerTool?.(...)`。
- 项目根定位走 `ctx.cwd`，回退 `process.cwd()`；复用 Keystone 的 `.keystone/` 定位语义。
- 所有宿主交互（context 生成、策略判定、事件落盘）通过**显式子进程桥**调用 Python 共享核心，不使用 hook stdin/stdout 协议。
- extension 只做协议适配，不重新实现状态机或策略。

### R3. Bridge CLI

新增一个显式 bridge 子命令（形态待设计确定，候选 `keystone bridge <action> --json`），契约：

- 输入：JSON（action、cwd、session id、可选 tool 信息）。
- 输出：JSON 到 stdout，非零退出表示失败。
- fail-open：非零退出或超时（≤1500ms，对齐 Trellis）时 extension 放行，不阻塞 Pi。
- 只读 + 追加事件；**不**修改 `task.json` / `project.json` / `.state/` 以外的任何文件。

### R4. 能力矩阵与诊断

- `adapters/pi.py`（或等价）声明 `PlatformCapabilities`，值必须来自 R1 实测结论。
- `keystone init --platform pi` 注册 extension 片段并提示需重启/重载 Pi；`doctor --platform pi` 对未支持能力 WARN。
- 不支持的策略（如 strict 门禁）必须显式 WARN，不得静默降级。

### R5. 卸载与安全

- `keystone uninstall --platform pi` 只移除 Keystone 写入的 extension 条目与文件，保留 `.pi/` 内第三方 extension、prompts、agents。
- 不读写 `~/.pi`、MCP、模型、权限设置。

## Acceptance Criteria

- [x] R1 三项观测已在真实 Pi 上完成，原始证据落盘 `research/pi-host-observations.md`（2026-10-05，pi 1.0.2）
- [ ] extension 由 `.pi/settings.json` 原生加载，未使用 Python hook runner
- [ ] `before_agent_start` context 在真实 Pi 中可见（含项目名、test/build 命令、任务状态）
- [ ] 写入门禁（若 R1 证实可行）在真实 Pi 中真实阻断 PLANNING 阶段写入；若不可行，capability matrix 标 unsupported 且 doctor WARN
- [ ] SessionEnd 元数据（若 R1 证实可行）写入 `.keystone/.state/events.jsonl`；若不可行，capability matrix 标 unsupported
- [ ] bridge CLI 非零退出/超时时 extension fail-open，Pi 不卡死
- [ ] `init` / `doctor` / `uninstall --platform pi` 只触碰 `.pi/` 内 Keystone 自有条目，不影响第三方
- [ ] extension 类型检查（`tsc --noEmit`）通过，且纳入发布门槛
- [ ] wheel 与 npm tarball 均包含 extension 资源并断言存在
- [ ] README 平台矩阵 Pi 状态按真实验证结果更新；未验证能力保持 unverified
- [ ] `.agents/skills/` 共享目标内容与 Codex 写入保持 byte-identical

## Risks

| 风险 | 影响 | 缓解 |
|---|---|---|
| `tool_call` 无法阻断 | Pi 无法提供写入门禁，只能做 context | R1 先行；若不可行则缩小范围并在文档明确 |
| `session_shutdown` 无 session id | 无法落盘 SessionEnd | 换信号源（如 `tool_call` 注入 env、`context` 事件）或标 unsupported |
| Pi extension API 版本漂移 | extension 在旧/新 Pi 上失效 | 只依赖 R1 实测版本；记录兼容区间；类型检查入发布门槛 |
| TypeScript 构建/资源打包引入新发布复杂度 | 发布门槛与 Python 包不一致 | extension 走独立资源断言步骤，不混入现有 release.sh 主流程 |
| extension 意外阻断用户正常操作 | 破坏 Pi 可用性 | 强 fail-open；任何异常放行 |

## Open Questions

1. Keystone 的 extension 是否也提供 Pi slash command（对齐 Trellis 的 `.pi/prompts/trellis-*.md`）？还是只做自动注入？
2. bridge CLI 是复用 `keystone` 主命令的子命令，还是独立可执行文件（避免 Pi 侧参数解析耦合）？
3. Pi 的 `enableSkillCommands` 是否影响 Keystone 在 `.agents/skills/` 的既有安装？
4. 是否需要在 extension 内缓存 context（对齐 Trellis 的 turnCache / systemPrompt 快照），还是每次 bridge 调用？

## Notes

- 本任务依赖 `10-03-multi-platform-adapter`；父任务已完成的 shared-skills 部分不重复。
- R1 是**阻塞性**的：没有真实 Pi 观测就不进入 R2。
- 参考实现：`@mindfoldhq/trellis@0.6.17` 的 `dist/templates/pi/extensions/trellis/index.ts.txt`（2124 行），但只作对照，不照抄其 subagent/TUI/权限转发部分。