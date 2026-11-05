---
name: build
description: "Implementa a spec task por task — teste falhando primeiro, depois o código, o quality gate e um commit por task. Também corrige o que a verificação ou o review apontaram (o Ravend sabe o que falhou). Para uma mudança trivial, aceita a descrição direto, sem spec."
argument-hint: "<slug | descrição de uma mudança trivial>"
---

# Ravend · build

> **`--headless`**: never ask the user anything, and make your **final message exactly the JSON object in *Output*** — also when blocked or failing (use the blocked/FAIL form). The headless runner parses it.

## 0. Setup
- `RV="python3 $RAVEND_ROOT/scripts/ravend.py"` (empty `RAVEND_ROOT` → this skill's base dir + `/../../scripts/ravend.py`). `$RV project` → `data_dir`, `base_branch`, `has_profile`. No profile → stop and ask for `/ravend:init` (the gate is what makes this pipeline trustworthy).
- Argument is a slug → read `<data_dir>/specs/<slug>/spec.md`. No slug and it is a trivial change → work without a spec (skip to step 2, single "task").
- **Mode**: `$RV next <slug> --json`. `build` → section 2 for `task`. `fix` → section 3 (`fix` = `verify` or `review`; details in `problem`, `review`, `blocking`). `approve` → interactive: ask for approval, then `$RV spec approve <slug>`; headless with `--approved`: run it; without: report blocked. Anything else → tell the user to run `/ravend:continue`.
- Branch: if on `base_branch`, `git switch -c <spec.branch>` (or reuse it). If the tree has unrelated uncommitted changes, stop and ask — never mix them in.
- Arm the Stop-hook gate: `$RV arm`.
- Integrations (`$RV project` → `integrations`, roles for `build`): `docs` for the APIs of the library versions in use, `context` to find similar features and usages, `design` for UI tasks, `database` to check the real schema (read-only). Pass the relevant server names to `ravend:implementer` agents.
- Load the stack skill(s) of the modules you will touch (`ravend:stack-spring`, `ravend:stack-quarkus`, `ravend:stack-angular`, `ravend:stack-react`). Read `<data_dir>/project.md` conventions if not already in context.

## 1. Pick work
Unchecked tasks in order, respecting `deps`. If ≥2 remaining tasks are marked `[P]` with disjoint files, you may dispatch one `ravend:implementer` agent per task with worktree isolation (Agent tool, `isolation: "worktree"`), give each the spec path + task id, then merge their branches one by one and run `$RV gate fast` after each merge. Otherwise work sequentially in this session — it is cheaper and keeps context coherent.

## 2. Per task: red → green → gate → commit
1. **Read** only the files listed for the task plus what they directly depend on.
2. **Red**: write the tests for the ACs this task proves, at the level tagged in the AC (`[unit]` → unit test; `[api]` → see `ravend:api-tests`; `[e2e]`/`[visual]` → see `ravend:e2e-playwright`). Run the narrowest command for those tests and confirm they fail **for the expected reason** (not a compile error in the test itself). Bugs: the failing test must reproduce the report.
3. **Green**: the minimal production change that makes them pass, following the codebase's existing patterns (find a similar feature and mirror it). No speculative abstractions, no drive-by refactors outside the task's files.
4. **Gate**: `$RV gate fast`. On failure read the excerpt (full log path is printed), fix the root cause, re-run. Never weaken, skip, or delete a test to get green; never add `@Disabled`/`.skip`. After 3 failed attempts on the same problem: stop, record it in the spec `## Log`, report blocked.
5. **Close**: `$RV task done <slug> T<n>` — the runtime ticks the box and logs it; never edit the checkbox by hand (`next` reads it). Add a `## Log` line only for a notable decision. If `profile.git.commit_per_task` is not false: review `git status`, stage only this task's files, commit `<type>(<scope>): <task title> [<slug> T<n>]`.

## 3. Fix mode (`next` says `fix`)
- `fix: verify`: `problem` says what failed. Gate red → read the last gate excerpt (`$RV status --json` → `last_gate.full`, log path inside). Uncovered criteria → write the missing tests. Fix only that.
- `fix: review`: read the file in `review` (`review-N.md`). Fix every P0/P1, nothing else; a P0/P1 that is a bug gets a regression test first. If you disagree with a finding, do not silently skip it — write the rebuttal under it in review-N.md.
- Then gate fast → commit `fix(<scope>): address <gate|review-N> [<slug>]`.

## 4. Finish
All tasks ticked + gate fast green → suggest `/ravend:continue` (the next step is verify).
If the change revealed a reusable, project-specific lesson, invoke `ravend:remember`.

## Output
Interactive: tasks done, commits, gate result, anything deferred.
`--headless`: no questions; end with exactly one JSON object `{"status": "done"|"blocked", "summary": "...", "blockers": [...]}`.
