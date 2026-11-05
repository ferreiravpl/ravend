---
name: ship
description: Open the pull request for a reviewed Ravend spec — verifies the gate is green for the current tree and the latest review is approved, pushes the branch and creates the PR with acceptance criteria, test evidence and review verdict. Use when the user asks to ship, open a PR, or finish a spec.
argument-hint: <slug> [--yes] [--headless]
---

# Ravend · ship

> **`--headless`**: never ask the user anything, and make your **final message exactly the JSON object in *Output*** — also when blocked or failing (use the blocked/FAIL form). The headless runner parses it.

Pushing and opening a PR is visible to the team: confirm with the user first unless `--yes` was given.

## 1. Preconditions (stop and report if any fails)
- `python3 "$RAVEND_ROOT/scripts/ravend.py" status --json` (fallback path: this skill's base dir + `/../../scripts/ravend.py`):
  - `last_gate.full.status == "PASS"` **and** its `fingerprint == tree` (gate ran on exactly this code). Otherwise run `gate full` first.
- Newest `<data_dir>/specs/<slug>/review-N.md` is APPROVED and was written after the last code change (compare with `git log -1 --format=%cI`).
- Working tree clean (commit leftovers that belong to the spec; ask about anything else).
- `gh auth status` works (otherwise tell the user to run `! gh auth login`).

## 2. PR
- `git push -u origin <branch>`.
- `gh pr create --base <base_branch> --title "<type>(<scope>): <spec title>" --body-file <tmp>` with body:
  - **Summary** — 2–4 sentences from the spec problem + what changed.
  - **Acceptance criteria** — checklist, each with the test that proves it (from verify.md).
  - **Verification** — gate full steps and result; links/notes for E2E evidence.
  - **Review** — verdict, iteration count, remaining P2s.
  - **Out of scope / follow-ups**.
  - Source link (Jira/GitHub issue) if any.
  The spec itself stays local; the PR body is what the team sees.
- If the source is a Jira issue and the Atlassian MCP is available, offer to comment the PR link on it.

## 3. Close
`python3 "$RAVEND_ROOT/scripts/ravend.py" disarm`; set spec `status: done`; append the PR URL to `## Log`.

## Output
Interactive: PR URL. `--headless`: exactly one JSON object `{"pr_url": "..."}`.
