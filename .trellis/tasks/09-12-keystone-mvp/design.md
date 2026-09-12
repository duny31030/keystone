# Keystone v1 技术设计（去服务端化架构）

## 1. 总体架构

```text
CodeBuddy
   │ Hook 事件（stdin JSON，PascalCase 事件名）
   ▼
keystone-hook <event>          ← 短生命周期 CLI，纯标准库
   │ 读 cwd 向上找 .keystone/project.json
   │ 直读直写 .keystone/ 目录
   ▼
HookOutput JSON → stdout，退出码 0
```

无网络依赖。核心业务逻辑（core/）与存储（store/）分层解耦：Phase 2 需要服务端时，为 core 套 HTTP 壳、store 换 API 客户端即可。

## 2. 目录结构（本仓库，工具源码）

```
pyproject.toml                # 入口: keystone / keystone-hook
src/keystone/
├── cli.py                    # keystone init / task 子命令
├── hook/
│   ├── cli.py                # keystone-hook <event> 分发
│   ├── input.py              # stdin JSON（2s 超时守护线程）+ 字段兼容解析
│   ├── output.py             # HookOutput 构造（CodeBuddy 宽容解析，额外冗余键无害）
│   └── events.py             # 七个事件处理
├── core/                     # 存储无关业务核心
│   ├── statemachine.py       # 状态机
│   ├── context.py            # 上下文渲染
│   ├── taskmatch.py          # prompt 任务编号识别
│   └── policy.py             # 阶段要求文案、写类工具集合、policy_mode
└── store/                    # .keystone/ 目录存储
    ├── layout.py             # 路径布局与查找
    ├── project.py specs.py tasks.py sessions.py
tests/
```

## 3. 目标项目 `.keystone/` 布局

```
.keystone/
├── project.json              # git：slug/name/language/framework/build_tool/build_command/test_command/stop_mode/policy_mode
├── specs/                    # git：architecture.md / coding.md / general-ban.md（init 生成模板）
├── tasks/TASK-001/           # git：task.json + prd.md
└── .state/                   # gitignored：sessions.json、events.jsonl
```

## 4. 关键数据格式

task.json:

```json
{
  "code": "TASK-001",
  "title": "...",
  "status": "PLANNING",
  "acceptance_criteria": ["...", "..."],
  "pending_confirmation": false,
  "created_at": "...", "updated_at": "...",
  "transitions": [{"from": null, "to": "TODO", "at": "...", "reason": "created"}]
}
```

sessions.json: `{"<session_id>": {"task_code": "TASK-001", "updated_at": "..."}}`

events.jsonl: 每行一个元数据事件 `{"event": "PostToolUse", "tool_name": "Edit", "success": true, "session_id": "...", "task": "TASK-001", "at": "..."}`，绝不含文件内容/diff/命令输出。

## 5. 任务状态机

```
TODO → PLANNING → PLAN_CONFIRMED → IMPLEMENTING → VERIFYING → COMPLETED
                     VERIFYING → IMPLEMENTING（打回）
                     COMPLETED → IMPLEMENTING（重新打开）
```

- advance：沿主链走下一步（可 --to 指定合法目标）
- complete：等价 advance 到 COMPLETED（要求当前处于 VERIFYING）
- reopen：COMPLETED → IMPLEMENTING
- 非法流转抛 InvalidTransition，CLI 报错退出码 1，Hook 侧不主动变更状态

## 6. Hook 协议映射（依据 trellis 本地证据确认的 CodeBuddy 契约）

stdin 字段（兼容 camelCase 变体）：`session_id`、`transcript_path`、`conversation_id`、`cwd`、`hook_event_name`、`prompt`、`tool_name`、`tool_input`、`stop_hook_active`。环境变量：`CODEBUDDY_PROJECT_DIR` 等作 fallback。

输出：

- 注入类（SessionStart/UserPromptSubmit/Stop 提醒/PreCompact）：`{"hookSpecificOutput": {"hookEventName": "<Event>", "additionalContext": "<markdown>"}}`；上下文为空时不输出任何内容、exit 0（合法 no-op）
- 控制类（PreToolUse）：deny → `{"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny", "reason": "..."}}`；allow → 无输出 exit 0
- Stop 强制模式 → `{"decision": "block", "reason": "<检查清单>"}`，exit 0
- 防循环：Stop 事件且 `stop_hook_active` 为真 → 立即 exit 0 无输出

退出码：0 = 成功/放行；2 = 阻断（备用路径，主用 JSON deny）；其他非零 = 错误。

## 7. 事件与 matcher 注册（keystone init 写入 .codebuddy/settings.json）

| 事件 | matcher |
|---|---|
| SessionStart | `startup`、`clear`、`compact` 三条独立规则 |
| UserPromptSubmit | 无 matcher |
| PreToolUse / PostToolUse | 写类+执行类工具的 alternation：`Write\|Edit\|MultiEdit\|write_to_file\|replace_in_file\|apply_patch\|str_replace_editor\|Bash\|execute_command` |
| Stop / SessionEnd / PreCompact | 无 matcher（CodeBuddy 未支持的事件不会触发，注册无害） |

合并语义：settings.json 中仅增删 command 含 `keystone` 标识的 hook 条目，其余条目原样保留（与 trellis 共存）。

## 8. 写类工具名兼容集合（policy.py）

`Write, Edit, MultiEdit, write_to_file, replace_in_file, apply_patch, str_replace_editor, NotebookEdit, create_file, edit_file`。
执行类（仅记录/预留给 strict 模式）：`Bash, execute_command, run_command, terminal`。

## 9. 阶段注入文案（context.py 按状态渲染）

| 状态 | 注入要求 |
|---|---|
| TODO | 任务目标和开始要求（先进入 PLANNING 分析） |
| PLANNING | 先分析需求、影响范围、实施步骤和验证方案，不修改代码 |
| PLAN_CONFIRMED | 允许修改代码 |
| IMPLEMENTING | 开发规范和任务边界 |
| VERIFYING | 执行适用验证命令或说明无法验证原因 |
| COMPLETED | 允许结束，记录总结 |

## 10. 异常策略（无网络后收敛为文件层）

- 事件处理抛异常 → 控制类 fail-open（放行）、记录类 fail-silent（静默）
- `.keystone/` 不存在 → 全部事件 no-op（未初始化项目零打扰）
- stdin 读取失败/超时 → exit 0 无输出
- `policy_mode`：permissive（默认）/ strict（预留，strict 下 PreToolUse 对执行类也可拒绝、Stop 强制）

## 11. 测试策略

- 单测：状态机、taskmatch 正则、写类工具匹配、上下文渲染快照
- Runner 协议测试：临时 .keystone fixture + monkeypatch stdin，逐事件断言 stdout JSON 与退出码
- E2E：tmp 目录 `keystone init` → 管道逐事件 → 断言输出与文件状态；settings.json 合并/共存验证
