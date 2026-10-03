---
name: keystone-handoff
description: Create a factual handoff for a Keystone task. Use when pausing work, switching agents, approaching a context limit, or when the user requests a handoff.
---

# Keystone Task Handoff

Use this skill to preserve task context across sessions or agents. A handoff records current facts; it does not change task state.

## Required Steps

1. Identify the task code and read current state:

   ```bash
   keystone task show TASK-XXX
   keystone events list --task TASK-XXX
   ```

2. Read the task's `prd.md`, `plan.md` when present, and relevant project specifications.
3. Create or update `tasks/TASK-XXX/handoff.md` only with user permission when it already exists.
4. Write a concise handoff with these sections:

   ```markdown
   # Task Handoff: TASK-XXX

   ## Current State
   - Current Keystone status:
   - Current branch / working tree facts:

   ## Completed Work
   -

   ## Verification Evidence
   - Command / observation:
   - Result:

   ## Open Risks And Blockers
   -

   ## Next Steps
   1.

   ## Useful Commands
   -
   ```

5. Report the generated handoff path and the exact next action.

## Safety Rules

- A handoff is not evidence of completion. Never transition the task automatically.
- SessionEnd events are hints, not task completion signals.
- Do not edit `.keystone/project.json`, `.keystone/.state/**`, or `tasks/*/task.json`.
- Do not overwrite a user-authored `handoff.md` without explicit permission.
- Keep secrets, tokens, credentials, private URLs, and sensitive tool output out of the handoff.
- If task data is missing or corrupt, stop and suggest `keystone doctor`; do not repair state yourself.
