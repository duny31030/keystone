# Keystone Multi-Platform Adapter Design

## 1. Current Boundary

The current core can be reused: `.keystone` storage, state machine, policy tool-name matching, task matching and context rendering. CodeBuddy-specific behavior must move out of generic modules:

- `.codebuddy/settings.json` path
- JSON settings merge/remove
- CodeBuddy Hook event names and matcher strings
- `hookSpecificOutput` / `permissionDecision` rendering
- `CODEBUDDY_*` environment fallbacks
- CodeBuddy-only doctor/status/uninstall findings

## 2. Semantic Hook Model

Shared event handlers return semantic effects rather than platform JSON:

```text
InjectContext(text)
DenyTool(reason)
BlockStop(reason)
Noop
```

Each adapter maps a supported semantic effect to native protocol:

| Effect | CodeBuddy / Claude | Codex MVP | Pi |
|---|---|---|---|
| InjectContext | hookSpecificOutput.additionalContext | UserPromptSubmit / SubagentStart additionalContext | before_agent_start systemPrompt/message |
| DenyTool | PreToolUse permissionDecision=deny | unsupported | tool_call block=true |
| BlockStop | Stop decision=block (host behavior must be tested) | unsupported | adapter-specific settle callback, later |

## 3. Adapter Contract

```python
class PlatformAdapter(Protocol):
    name: str
    capabilities: PlatformCapabilities
    def plan_install(root, runner_command) -> PlatformPlan: ...
    def plan_uninstall(root) -> PlatformPlan: ...
    def inspect(root) -> list[Finding]: ...
    def normalize_input(raw, env) -> NormalizedHookInput: ...
    def render(effect) -> NativeHookOutput: ...
```

`PlatformPlan` reuses existing CREATE/UPDATE/REMOVE/UNCHANGED dry-run semantics, but each adapter owns its JSON/TOML/TypeScript mutation implementation. This prevents a fake common configuration model from corrupting third-party settings.

## 4. Platform Details

### CodeBuddy

First adapter extracted with no behavior change. It retains the five real-world verified defaults: SessionStart, UserPromptSubmit, PreToolUse, Stop reminder and SessionEnd.

### Claude Code

Uses `.claude/settings.json` and the same command-hook list shape. It can reuse most JSON payload aliases and CodeBuddy JSON output renderer. PreToolUse deny is officially documented; exact matcher/tool names and Stop behavior must be smoke tested before marked verified.

### Codex

Uses `.codex/hooks.json`. Initial scope is context injection and shared skills only. The adapter must report missing user-side feature enablement, trust and `/hooks` approval. No strict policy or Stop gate claim.

Implemented as `CodexAdapter` (context-only MVP): a single `UserPromptSubmit` registration, reusing the shared `events.user_prompt_submit()` handler. It never reads or writes `~/.codex/config.toml`, project trust, `/hooks` approval, MCP, model or sandbox settings. `capability_warnings()` surfaces the manual prerequisites and the deliberately unsupported file-tool deny / strict gate / Stop / SessionEnd.

### Pi

Pi support in this batch is limited to the shared `.agents/skills` target: `keystone skills install --platform pi` installs there, `--platform auto` detects an existing `.pi/` root, and `skills list` labels the target as shared by Codex and Pi. Keystone does **not** create `.pi/settings.json`, install an extension, or claim context/deny behavior.

The Pi TypeScript extension is deferred to a separate task. It will install a Keystone-owned extension mapped as `before_agent_start` → context, `tool_call` → `{ block: true, reason }` for verified native Pi write/edit tools, and `session_shutdown` → SessionEnd metadata. It is a separate runtime bundle with its own type-check and host smoke gate, built independently from the Python Hook Runner.

## 5. Compatibility and Safety

- Project state remains `.keystone`; platforms never get their own task state.
- Adapter manifests record only Keystone-owned entries/files; uninstall does not delete third-party configuration.
- Each platform’s capability matrix is a public contract. Missing capability yields doctor WARN, not silent pretend protection.
- MCP stays out of scope. No adapter writes MCP server declarations, tokens, model settings or user home directory configuration.

## 6. Testing Strategy

- Unit tests: config plans, mixed third-party rule preservation, payload normalization, renderer output, capability downgrade diagnostics.
- Fixture tests: each platform’s generated config has expected event set and no unsupported gate.
- Real smoke tests: Claude first, then Codex and Pi. README only moves a capability to verified after a real host test.
