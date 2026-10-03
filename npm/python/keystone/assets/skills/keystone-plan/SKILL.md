---
name: keystone-plan
description: Create or improve a Keystone task plan. Use when a task is in TODO or PLANNING, when the user asks for an implementation plan, or before requesting PLAN_CONFIRMED.
---

# Keystone Task Plan

Use this skill to make the task plan explicit and reviewable. The plan is stored in the task's `plan.md`; it is not a chat-only summary.

## Required Steps

1. Identify the task code from the user request or ask the user to choose one.
2. Read task truth through:

   ```bash
   keystone task show TASK-XXX
   ```

3. Confirm the task is in `TODO` or `PLANNING`. If it is `TODO`, explain that the user must first move it to `PLANNING` with `keystone task advance TASK-XXX`.
4. Read the project's `.keystone/project.json`, relevant `.keystone/specs/*.md`, `prd.md`, and an existing `plan.md` when present.
5. If `plan.md` does not exist, create the canonical template:

   ```bash
   keystone task plan TASK-XXX
   ```

6. Fill `plan.md` with concrete content for:
   - Goal
   - Impact scope and explicit non-goals
   - Ordered implementation steps
   - Verification commands and expected observations
   - Risks, assumptions, and decisions requiring user confirmation
7. Present the plan and wait for explicit user confirmation.
8. Only after explicit confirmation, tell the user or execute:

   ```bash
   keystone task advance TASK-XXX
   ```

## Safety Rules

- Do not edit `.keystone/project.json`, `.keystone/.state/**`, or any `tasks/*/task.json` directly.
- Do not hand-write task transitions or audit records. Use `keystone task` commands.
- Do not advance a task based on your own confidence, a test result, or an implied user response. Explicit user confirmation is required.
- Do not modify source code while the task is in `TODO` or `PLANNING`.
- If Keystone state is missing or corrupt, stop and suggest `keystone doctor`; do not silently repair state.
- Do not overwrite an existing user-authored `plan.md` without explicit permission.
