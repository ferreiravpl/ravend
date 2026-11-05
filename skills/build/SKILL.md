---
name: build
description: Implement a Ravend spec task by task, test-first, with the quality gate enforced before each task is closed. Also fixes gate failures or review findings (--fix). Use after /ravend:spec, or directly for trivial changes.
argument-hint: <slug | trivial change description> [--fix gate|verify|review] [--headless] [--approved]
---

# Ravend · build

> **`--headless`**: never ask the user anything, and make your **final message exactly the JSON object in *Output*** — also when blocked or failing (use the blocked/FAIL form). The headless runner parses it.

## 0. Setup
- `RV="python3 $RAVEND_ROOT/scripts/ravend.py"` (empty `RAVEND_ROOT` → this skill's base dir + `/../../scripts/ravend.py`). `$RV project` → `data_dir`, `base_branch`, `has_profile`. No profile → stop and ask for `/ravend:init` (the gate is what makes this pipeline trustworthy).
- Argument is a slug → read `<data_dir>/specs/<slug>/spec.md`. No slug and it is a trivial change → work without a spec (skip to step 2, single "task").
- Spec `status: draft` → interactive: ask for approval; headless without `--approved`: report blocked.
- Branch: if on `base_branch`, `git switch -c <spec.branch>` (or reuse it). If the tree has unrelated uncommitted changes, stop and ask — never mix them in.
- Arm the Stop-hook gate: `$RV arm`. Set spec `status: in-progress`.
- Load the stack skill(s) of the modules you will touch (`ravend:stack-spring`, `ravend:stack-quarkus`, `ravend:stack-angular`, `ravend:stack-react`). Read `<data_dir>/project.md` conventions if not already in context.

## 1. Pick work
Unchecked tasks in order, respecting `deps`. If ≥2 remaining tasks are marked `[P]` with disjoint files, you may dispatch one `ravend:implementer` agent per task with worktree isolation (Agent tool, `isolation: "worktree"`), give each the spec path + task id, then merge their branches one by one and run `$RV gate fast` after each merge. Otherwise work sequentially in this session — it is cheaper and keeps context coherent.

## 2. Per task: red → green → gate → commit
1. **Read** only the files listed for the task plus what they directly depend on.
2. **Red**: write the tests for the ACs this task proves, at the level tagged in the AC (`[unit]` → unit test; `[api]` → see `ravend:api-tests`; `[e2e]`/`[visual]` → see `ravend:e2e-playwright`). Run the narrowest command for those tests and confirm they fail **for the expected reason** (not a compile error in the test itself). Bugs: the failing test must reproduce the report.
3. **Green**: the minimal production change that makes them pass, following the codebase's existing patterns (find a similar feature and mirror it). No speculative abstractions, no drive-by refactors outside the task's files.
4. **Gate**: `$RV gate fast`. On failure read the excerpt (full log path is printed), fix the root cause, re-run. Never weaken, skip, or delete a test to get green; never add `@Disabled`/`.skip`. After 3 failed attempts on the same problem: stop, record it in the spec `## Log`, report blocked.
5. **Close**: tick the task (`- [x]`), append one line to `## Log` (date, task, notable decision). If `profile.git.commit_per_task` is not false: review `git status`, stage only this task's files, commit `<type>(<scope>): <task title> [<slug> T<n>]`.

## 3. Fix mode (`--fix gate|verify|review`)
- `gate`/`verify`: read the latest report (`$RV status --json` → `last_gate`, and `<data_dir>/specs/<slug>/verify.md`). Fix only what fails or the uncovered acceptance criteria.
- `review`: read the newest `<data_dir>/specs/<slug>/review-N.md`. Fix every P0/P1, nothing else; a P0/P1 that is a bug gets a regression test first. If you disagree with a finding, do not silently skip it — write the rebuttal under it in review-N.md.
- Then gate fast → commit `fix(<scope>): address <gate|review-N> [<slug>]`.

## 4. Finish
All tasks ticked + gate fast green → set spec `status: review`. Suggest `/ravend:verify <slug>`.
If the change revealed a reusable, project-specific lesson, invoke `ravend:learn`.

## Output
Interactive: tasks done, commits, gate result, anything deferred.
`--headless`: no questions; end with exactly one JSON object `{"status": "done"|"blocked", "summary": "...", "blockers": [...]}`.
