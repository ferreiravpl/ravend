---
name: sdd-context-compaction
description: Compact long-running task state into minimal persistent artifacts and scoped manifests.
compatibility: opencode
---
## What I do
- reduce context pressure
- preserve decisions and progress in files
- keep future steps low-token and recoverable

## When to use me
Use when the task history is growing or after a major phase transition.

## Procedure
1. Move stable conclusions into `decisions.md` and `progress.md`.
2. Remove stale assumptions from active reasoning.
3. Refresh the active task scope manifest.
4. Keep only the current step and necessary references in working context.
