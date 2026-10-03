# Keystone Workflow Skills Design

## 1. Product Boundary

Keystone skills supplement existing CLI and Hook behavior; they never become a second source of task truth.

```text
User explicitly invokes a skill
  -> Skill reads task/project/spec artifacts through Keystone CLI/files
  -> Skill writes only its declared Markdown artifact or reports evidence
  -> User confirms state change
  -> keystone task CLI performs audited transition

Automatic Hook path remains separate:
  Hook -> normalized event -> task state/context/policy -> platform output
```

## 2. Canonical Resource Layout

```text
src/keystone/
  assets/
    skills/
      keystone-plan/
        SKILL.md
      keystone-verify/
        SKILL.md
      keystone-handoff/
        SKILL.md
  skills/
    catalog.py      # metadata: name, description, targets, hashes
    targets.py      # platform target mapping only
    installer.py    # plan/install/manifest/collision handling
```

Skills use portable YAML frontmatter plus Markdown body. `SKILL.md` contains no platform-specific Hook JSON. Optional `references/` can be added only when a skill needs stable long-form material.

## 3. Safety Contract Shared by All Skills

Every skill must state:

1. Read task truth through `keystone task show <id>`; do not infer state from prompt text, session bindings or old summaries.
2. Do not create/edit/delete `.keystone/project.json`, `.keystone/.state/**`, or `tasks/*/task.json`.
3. Use `keystone task create/plan/advance/complete/reopen`; do not fabricate transitions or audit entries.
4. Only explicit user confirmation authorizes a state transition.
5. Do not modify platform settings, Hook registration, MCP configuration or user-level files.
6. Do not overwrite a user-authored artifact without explicit user permission.
7. Report missing/corrupt state and suggest `keystone doctor`; do not silently repair it.

## 4. Installer Model

Installer stores a managed manifest under `.keystone/managed/skills.json` with canonical skill name, target path, resource hash and platform target. This manifest tracks Keystone-owned installed copies only; Hook runtime does not depend on it.

Install plan actions: CREATE, UNCHANGED, CONFLICT, OVERWRITE (`--force` only).

- `auto`: detects existing `.agents/.claude/.codebuddy/.zcode` directories; no existing directory means no write.
- `all`: writes every supported target.
- `agents`: writes the shared target once; it serves Codex and Pi.
- A different file at a managed target is a CONFLICT unless `--force` is passed.
- Uninstall will be planned later, after install semantics are exercised in real platforms.

## 5. Verification

Tests cover resource discovery, target selection, plan purity, idempotency, conflict/force behavior, manifest integrity and bundle inclusion. Packaging tests inspect wheel and npm tarball resource paths.
