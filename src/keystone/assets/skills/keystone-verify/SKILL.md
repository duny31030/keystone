---
name: keystone-verify
description: Organize factual verification for a Keystone task. Use when implementation is ready for verification, the task is in VERIFYING, or the user asks to test or assess acceptance criteria.
---

# Keystone Task Verify

Use this skill to gather trustworthy verification evidence. It does not decide that a task is complete.

## Required Steps

1. Identify the task code and read its current truth:

   ```bash
   keystone task show TASK-XXX
   ```

2. Read `.keystone/project.json` for `build_command` and `test_command`, plus the task's `prd.md` and `plan.md`.
3. Map each acceptance criterion to a concrete observation:
   - automated test or build command;
   - contract, compile, lint, or manual validation where appropriate;
   - an explicit "not run" reason when validation cannot be performed.
4. Execute only commands the user has authorized or commands that are clearly listed as the task's agreed verification plan.
5. Report evidence in this structure:

   ```text
   Task: TASK-XXX
   Verification:
   - <command or observation>: PASS / FAIL / NOT RUN
   - Evidence: <actual result>
   Risks and gaps:
   - <remaining risk or none>
   Suggested next state:
   - VERIFYING -> COMPLETED, or VERIFYING -> IMPLEMENTING
   ```

6. Ask the user to confirm any state transition. After confirmation, use `keystone task complete TASK-XXX` or `keystone task advance TASK-XXX`; use the normal state machine, never direct JSON edits.

## Safety Rules

- A passing test does not authorize task completion. The user decides whether evidence is sufficient.
- Never report a command as passed unless it actually ran and its result was observed.
- Record failures, skipped checks, environment limits, and residual risks plainly.
- Do not edit `.keystone/project.json`, `.keystone/.state/**`, or `tasks/*/task.json`.
- Do not infer task state from a conversation summary or SessionEnd event; use `keystone task show`.
- If a verification command could be destructive or outward-facing, ask before running it.
