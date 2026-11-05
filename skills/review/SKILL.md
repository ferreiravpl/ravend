---
name: review
description: "Review independente das mudanças da spec, feito por um agente que não viu a implementação — correção, critérios de aceite, escopo, segurança e convenções do projeto — com findings P0/P1/P2 e evidência (arquivo:linha e cenário de falha)."
argument-hint: "<slug>"
---

# Ravend · review

> **`--headless`**: never ask the user anything, and make your **final message exactly the JSON object in *Output*** — also when blocked or failing (use the blocked/FAIL form). The headless runner parses it.

## 1. Prepare
- `python3 "$RAVEND_ROOT/scripts/ravend.py" project` → `data_dir`, `base_branch` (fallback path: this skill's base dir + `/../../scripts/ravend.py`).
- Base ref: `git merge-base HEAD <base_branch>`.
- Integrations for `review` (`context`, `git`): the reviewer agent has no MCP access, so gather what helps here and pass it as text — e.g. callers of changed public symbols (`context`), CI checks or existing PR comments for the branch (`git`). Skip if none are chosen.

## 2. Dispatch the reviewer
Call the `ravend:reviewer` agent (fresh context = no implementer bias). Prompt it with paths, not content:
- spec: `<data_dir>/specs/<slug>/spec.md`, verify report: `.../verify.md` (if present)
- base ref, iteration N (`$RV next <slug> --json` before review: previous reviews are listed in the spec's `state.json`), previous review file if any (check that its P0/P1 were addressed)
- project notes `<data_dir>/project.md` and knowledge index `<data_dir>/knowledge/index.md` (if present)
- integration findings gathered above (if any)
The agent returns a JSON object (verdict + findings).

## 3. Record
- Pass the agent's JSON to the runtime: `$RV review record <slug>` with the JSON on stdin (heredoc), run from the repository root. Never write the JSON to a file inside the repository: it changes the code being recorded. It numbers the review, writes `review-N.md` (findings grouped P0 → P1 → P2 with scenario and action) and derives the verdict: any P0/P1 means CHANGES_REQUESTED, whatever the agent wrote.
- If the data dir is read-only (sandbox) and the command fails, write `<data_dir>/specs/<slug>/review-N.md` yourself in that same format (N = existing review files + 1).
- Next step: `/ravend:continue` (fix round or PR). If a P0/P1 from the previous review is still present, say so explicitly — `next` will stop and hand over.
- Findings that reflect a reusable, project-specific rule → invoke `ravend:remember` (only if not already enforceable by a linter).

## Output
Interactive: verdict + findings table + next step.
`--headless`: end with exactly one JSON object `{"verdict": "APPROVED"|"CHANGES_REQUESTED", "iteration": N, "findings": [{"severity": "P0|P1|P2", "file": "...", "line": 12, "title": "..."}]}`.
