# Claude Code 真实宿主观测记录

日期：2026-10-05。环境：Claude Code 2.1.281，headless 模式（`claude -p`，非交互），项目 `/tmp/ks-claude-headless`（keystone init --platform claude）。**Claude headless 模式完整触发所有已注册 hook**，包括 PreToolUse 拒绝与 Stop。

## 逐项验证结果

| 能力 | 结果 | 证据 |
|---|---|---|
| SessionStart context 注入 | ✅ | 模型答出项目名与 test command `pytest` |
| UserPromptSubmit 任务绑定 | ✅ | sessions.json 写入 session→TASK-001 |
| PreToolUse：PLANNING 写入门禁 | ✅ | 任务 PLANNING 时要求创建 gated.txt，文件未创建 |
| PreToolUse：IMPLEMENTING 放行 | ✅ | 推进后同一写入成功 |
| PreToolUse：COMPLETED 后拒绝 | ✅ | 覆盖尝试被拒，文件内容不变 |
| `.keystone` 状态文件保护 | ✅ | 覆盖 project.json 被拒，文件仍为合法 JSON |
| SessionEnd 事件落盘 | ✅ | events.jsonl 追加带 session id/task 的记录 |
| Stop reminder | ✅ | 检查清单注入，模型逐项回答 |
| **Stop enforce 真实阻止** | ✅ | 见下 |

## Stop enforce 的关键证据

对照实验（同一项目、同一 prompt、`--max-turns` 限制）：

1. 恒返回 `{"decision":"block"}` 的 Stop hook：会话反复重试直到 max_turns → Claude **尊重 block**。
2. keystone enforce 模式完整跑一次：`num_turns=24, subtype=success`，Stop 被调用两次：
   - 第 1 次 `stop_hook_active=false` → keystone 返回 block；
   - 第 2 次 `stop_hook_active=true` → keystone 循环保护放行 → 会话正常结束。

**没有死循环，enforce 生效。** 这与 CodeBuddy 宿主行为相反（CodeBuddy 收到 block 输出但未表现出阻止结束）。

## 真实 payload 形状（捕获）

PreToolUse：

```json
{"session_id":"...","transcript_path":"/home/duny/.claude/projects/...jsonl","cwd":"/tmp/ks-claude-headless","prompt_id":"...","permission_mode":"acceptEdits","hook_event_name":"PreToolUse","tool_name":"Write","tool_input":{"file_path":"...","content":"..."},"tool_use_id":"..."}
```

Stop：额外含 `stop_hook_active`、`last_assistant_message`、`background_tasks`、`session_crons`。

`keystone-hook --platform claude` 的别名归一全部命中；deny 输出使用 `permissionDecisionReason` 字段被宿主接受。

## 注意事项

1. **PATH 陷阱**：注册的是裸命令 `keystone-hook`。本机全局 npm 装的旧版 `keystone-hook@0.1.0` 不认识 `--platform`，exit 1 被 fail-open 静默吞掉，表现为"hook 注册了但毫无效果"。测试时用 venv bin 前置 PATH 解决；用户环境需 `npm update -g keystone-hook` 或用 `--hook-command` 指定绝对路径。
2. headless（`-p`）模式跳过 workspace trust 对话框；交互模式的 trust 行为未覆盖。
3. 验证使用的模型通道报 `[claude-code:unrecognized_model]`（glm-5.3 经代理），不影响 hook 机制验证。

## 结论

Claude adapter 的全部注册能力（context、file-tool deny、三类门禁、Stop reminder/enforce、SessionEnd）在 headless 真实宿主验证通过。capability 可升级为 verified（标注 headless 范围；交互 TUI 未覆盖）。