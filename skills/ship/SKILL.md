---
name: ship
description: "Abre o pull request — só quando o gate completo está verde neste código e o review foi aprovado. Faz o push e cria o PR com os critérios de aceite, o teste que prova cada um, o resultado do gate e o veredito do review. Sempre pede sua confirmação antes."
argument-hint: "<slug>"
---

# Ravend · ship

> **`--headless`**: never ask the user anything, and make your **final message exactly the JSON object in *Output*** — also when blocked or failing (use the blocked/FAIL form). The headless runner parses it.

Pushing and opening a PR is visible to the team: confirm with the user first unless `--yes` was given.

## 1. Preconditions (stop and report if any fails)
`RV="python3 $RAVEND_ROOT/scripts/ravend.py"` (fallback: this skill's base dir + `/../../scripts/ravend.py`).
- With a slug: `$RV next <slug> --json` must answer `ship` (gate full green, criteria covered and review approved, all on exactly this code). Anything else → report its `message` and suggest `/ravend:continue`. Do not ship around it.
- Trivial change (no slug): `$RV status --json` → `last_gate.full.status == "PASS"` and its `fingerprint == tree`; otherwise run `gate full` first.
- Working tree clean (commit leftovers that belong to the spec; ask about anything else).
- `gh auth status` works, unless a `git` integration will open the PR (otherwise tell the user to run `! gh auth login`).

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
- `git` integration chosen (`$RV project` → `integrations`) → create the PR with that MCP instead of `gh`, same title/body/base; `gh` stays the fallback.
- Source is a ticket and an `issues` integration is chosen → offer to comment the PR link on it.

## 3. Close
`$RV disarm`; with a slug, `$RV spec done <slug> --pr <url>` (closes the spec and logs the PR).

## Output
Interactive: PR URL, or why it was not opened. `--headless`: exactly one JSON object — `{"pr_url": "..."}`, or `{"pr_url": "", "blocked": "<reason>"}` when a precondition fails (nothing pushed).
