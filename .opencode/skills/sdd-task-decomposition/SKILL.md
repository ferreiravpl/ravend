---
name: sdd-task-decomposition
description: Break a spec or plan into bounded implementation tasks with machine-readable handoff metadata.
compatibility: opencode
---
## What I do
- decompose work into small tasks
- define files in scope and validation steps
- support low-context implementation through manifests

## When to use me
Use after spec approval or when a direct implementation path still needs bounded tasks.

## Procedure
1. Break the work into the smallest meaningful tasks.
2. For each task, define acceptance criteria and validations.
3. Update `.lla/sdd/current/tasks.md`.
4. Update `.lla/manifests/task-scope.json` for the active task.
