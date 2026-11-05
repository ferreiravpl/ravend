---
name: run
description: Run the whole Ravend pipeline interactively for one demand — spec, build, verify, review, ship — picking the smallest safe path for its size and stopping only at the human checkpoints.
argument-hint: <demand | PROJ-123 | #45>
disable-model-invocation: true
---

# Ravend · run

You are the orchestrator; there is no separate orchestrator agent. Keep this session's context for decisions and delegate only noisy or independent work (exploration → `Explore`, E2E authoring → `ravend:verifier`, review → `ravend:reviewer`).

Flow for `$ARGUMENTS`:

1. **Spec** — invoke `ravend:spec`. It decides the tier.
   - trivial → skip to 2 without a spec.
   - large → **checkpoint 1**: wait for the user's approval of the spec.
2. **Build** — invoke `ravend:build <slug>` (or with the change description if trivial).
3. **Verify** — invoke `ravend:verify <slug>`. Trivial changes: `gate full` only.
4. **Review** — invoke `ravend:review <slug>`. Skipped for trivial unless the user asks.
5. **Loop** — gate failures or CHANGES_REQUESTED → `ravend:build <slug> --fix verify|review` → back to 3. At most **2 fix rounds**; stop earlier if the same P0/P1 reappears. On stop: summarize state, findings and what you tried, and hand over to the user.
6. **Ship** — **checkpoint 2**: ask before invoking `ravend:ship <slug>` (push + PR).

Between stages print one status line (stage, result, next). Prefer `/clear`-friendly progress: everything needed to resume is in the spec file (`## Tasks` + `## Log`), so a new session can continue with `/ravend:build <slug>` or `/ravend:verify <slug>`.

For unattended runs (CI, background), use the headless runner instead: `python3 "$RAVEND_ROOT/scripts/ravend_run.py" "<demand>" --until review`.
