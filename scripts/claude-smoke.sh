#!/usr/bin/env bash
# Prepare an isolated Claude Code smoke project. This script does not invoke Claude.
set -euo pipefail

ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
PROJECT=${1:-/tmp/keystone-claude-smoke}

rm -rf "$PROJECT"
mkdir -p "$PROJECT"
printf '[project]\nname = "keystone-claude-smoke"\nversion = "0.0.0"\n' > "$PROJECT/pyproject.toml"
"$ROOT/.venv/bin/keystone" init --dir "$PROJECT" --platform claude -y --name keystone-claude-smoke >/dev/null

cat > "$PROJECT/.claude/PROMPTS.md" <<'PROMPTS'
# Keystone Claude Code Smoke Checklist

Open this directory in a new Claude Code session. Record the raw Claude behavior and terminal result for every step.

## 1. Session context

Start a new session. Confirm the injected context contains the Keystone project name, build/test command and spec headings.

## 2. Task binding and plan gate

In the terminal:

```bash
keystone task create "Claude adapter smoke"
keystone task advance TASK-001
keystone task plan TASK-001
```

Fill plan.md with one non-empty line under each section. In Claude, send:

```text
I am working on TASK-001. Create blocked.txt with the text blocked.
```

Expected: PLANNING write must be denied by Claude's native UI. Verify:

```bash
test ! -e blocked.txt && echo PASS || echo FAIL
```

## 3. Confirmed write and completed deny

In the terminal:

```bash
keystone task advance TASK-001
keystone task advance TASK-001
```

In Claude, create `allowed.txt` with `allowed`. Expected: Write is allowed in IMPLEMENTING.

Then in terminal:

```bash
keystone task advance TASK-001
keystone task complete TASK-001
```

In Claude, try to change `allowed.txt` to `blocked-after-complete`. Expected: denied. Verify the original content stays unchanged.

## 4. Keystone state protection

In Claude, attempt to modify each path:

- `.keystone/project.json`
- `.keystone/tasks/TASK-001/task.json`
- `.keystone/.state/tampered.json`

Expected: each native file-tool operation is denied. Do not claim Bash or MCP protection from this smoke.

## 5. Stop and SessionEnd

First use the default reminder stop mode and request session end. Record whether the checklist appears.

Then inspect:

```bash
keystone events list --event SessionEnd
```

Stop enforce is experimental. If testing it, explicitly set `stop_mode` in project.json only after recording the default reminder result, and report the actual host behavior rather than assuming a block output stops Claude.
PROMPTS

echo "Claude smoke project ready: $PROJECT"
echo "Open: $PROJECT"
echo "Checklist: $PROJECT/.claude/PROMPTS.md"
