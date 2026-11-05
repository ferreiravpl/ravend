---
name: review
description: Independent review of a Ravend spec's changes by a fresh-context reviewer agent — correctness, acceptance criteria, scope, security and project conventions — producing evidence-backed P0/P1/P2 findings and a verdict. Use after /ravend:verify, or when asked to review the current branch.
argument-hint: <slug> [--headless]
---

# Ravend · review

> **`--headless`**: never ask the user anything, and make your **final message exactly the JSON object in *Output*** — also when blocked or failing (use the blocked/FAIL form). The headless runner parses it.

## 1. Prepare
- `python3 "$RAVEND_ROOT/scripts/ravend.py" project` → `data_dir`, `base_branch` (fallback path: this skill's base dir + `/../../scripts/ravend.py`).
- Iteration `N` = number of existing `<data_dir>/specs/<slug>/review-*.md` + 1.
- Base ref: `git merge-base HEAD <base_branch>`.
- Integrations for `review` (`context`, `git`): the reviewer agent has no MCP access, so gather what helps here and pass it as text — e.g. callers of changed public symbols (`context`), CI checks or existing PR comments for the branch (`git`). Skip if none are chosen.

## 2. Dispatch the reviewer
Call the `ravend:reviewer` agent (fresh context = no implementer bias). Prompt it with paths, not content:
- spec: `<data_dir>/specs/<slug>/spec.md`, verify report: `.../verify.md` (if present)
- base ref, iteration N, previous review file (if N > 1: check that its P0/P1 were addressed)
- project notes `<data_dir>/project.md` and knowledge index `<data_dir>/knowledge/index.md` (if present)
- integration findings gathered above (if any)
The agent returns a JSON object (verdict + findings).

## 3. Record
Write `<data_dir>/specs/<slug>/review-N.md`: verdict, then findings grouped P0 → P1 → P2 as `file:line — title — why it fails (scenario) — required action`, then the raw JSON in a fenced block. Append one line to the spec `## Log`.
- APPROVED (no P0/P1) → spec `status: review` stays; suggest `/ravend:ship <slug>`.
- CHANGES_REQUESTED → suggest `/ravend:build <slug> --fix review`.
- If a P0/P1 finding was already raised in the previous iteration and is still present, say so explicitly — the loop is not converging and a human should decide.
- Findings that reflect a reusable, project-specific rule → invoke `ravend:learn` (only if not already enforceable by a linter).

## Output
Interactive: verdict + findings table + next step.
`--headless`: end with exactly one JSON object `{"verdict": "APPROVED"|"CHANGES_REQUESTED", "iteration": N, "findings": [{"severity": "P0|P1|P2", "file": "...", "line": 12, "title": "..."}]}`.
