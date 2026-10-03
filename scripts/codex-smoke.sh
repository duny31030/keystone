#!/usr/bin/env bash
# Prepare an isolated Codex smoke project. This script never edits user config, trust, or hook approval.
set -euo pipefail

ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
PROJECT=${1:-/tmp/keystone-codex-smoke}

rm -rf "$PROJECT"
mkdir -p "$PROJECT"
printf '[project]\nname = "keystone-codex-smoke"\nversion = "0.0.0"\n' > "$PROJECT/pyproject.toml"
"$ROOT/.venv/bin/keystone" init --dir "$PROJECT" --platform codex -y --name keystone-codex-smoke >/dev/null
"$ROOT/.venv/bin/keystone" skills install --dir "$PROJECT" --platform codex >/dev/null

cat > "$PROJECT/.codex/SMOKE.md" <<'SMOKE'
# Keystone Codex Context-Only Smoke Checklist

This adapter is experimental and context-only. It does not register PreToolUse, Stop, or SessionEnd policy gates.

## Manual prerequisites

Keystone does not write user-level Codex configuration. Complete these manually before testing:

1. In `~/.codex/config.toml`, enable hooks:

```toml
[features]
hooks = true
```

For older Codex versions, use the documented legacy feature name if needed.

2. Mark this project trusted in your user config:

```toml
[projects."/absolute/path/to/keystone-codex-smoke"]
trust_level = "trusted"
```

3. Open the project in interactive Codex and run `/hooks` once to inspect and approve the Keystone command.

## Verify context injection

In the project terminal:

```bash
keystone task create "Codex adapter smoke"
```

Then in Codex send:

```text
I am working on TASK-001. Explain the current task and its stage. Do not edit files.
```

Expected: Keystone task/phase context is visible to Codex. Send a second prompt without task code and confirm the same task remains bound instead of a duplicate task being created.

## Verify explicit limitations

While the task is TODO/PLANNING, ask Codex to write a normal file. This adapter does NOT promise to block it; record the actual behavior but do not interpret it as Keystone policy enforcement.

Check:

```bash
keystone doctor --platform codex
keystone events list
```

Expected: doctor shows the project hook registration plus warnings for user-side hooks/trust/approval and unsupported file deny/Stop/SessionEnd behavior. Events may remain empty because SessionEnd is not registered.

## Verify uninstall safety

```bash
keystone uninstall --platform codex
```

Confirm only `.codex/hooks.json` Keystone entry is removed; `.keystone/`, `.agents/skills/`, and any third-party Codex hooks remain.
SMOKE

echo "Codex smoke project ready: $PROJECT"
echo "Checklist: $PROJECT/.codex/SMOKE.md"
