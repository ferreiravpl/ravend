---
name: spec
description: Turn a demand (free text, Jira key like PROJ-123, GitHub issue #45/URL) into a right-sized spec with testable acceptance criteria and a task checklist. Use when starting a feature or bug that is not trivial, or when the user asks to plan/specify work before coding.
argument-hint: <demand | PROJ-123 | #45> [--headless] [--approved]
---

# Ravend · spec

> **`--headless`**: never ask the user anything, and make your **final message exactly the JSON object in *Output*** — also when blocked or failing (use the blocked/FAIL form). The headless runner parses it.

Goal: the smallest spec that lets the work be built and verified without guessing. One file, not five.

## 0. Locate project data
Run `python3 "$RAVEND_ROOT/scripts/ravend.py" project` (if `RAVEND_ROOT` is empty, use this skill's base directory + `/../../scripts/ravend.py`). It prints `data_dir`. If `has_profile` is false, tell the user to run `/ravend:init` first (headless: proceed anyway, gate will be unavailable).
Specs live in `<data_dir>/specs/<slug>/spec.md` — on the developer's machine, never in the repo.
The same output has `integrations`: MCP servers the developer chose per role. Here use `issues`/`git` for intake, `context` to explore code, `knowledge` for internal docs/decisions, `design` for UI frames, `database` for the real schema, `observability` for bug evidence (stack trace, frequency, first seen). A chosen server that is not connected → continue without it and say so in one line.

## 1. Intake
- Jira key → read it with the `issues` integration (or any Atlassian MCP tools available); otherwise ask the user to paste it (headless: fail with a blocking question).
- GitHub issue → the `git`/`issues` integration if chosen, else `gh issue view <n> --json title,body,labels,comments`.
- Free text → use as is.
Then read only what is needed to understand the affected area: entry points, the module(s) touched, one or two similar existing features. Prefer the `context` integration for semantic search; otherwise use the `Explore` agent for broad searches so file dumps stay out of this context.

## 2. Classify the tier (decide, state it in one line, move on)
| Tier | Signals | Output |
|---|---|---|
| trivial | ≤2 files, no new behavior/contract, obvious | **no spec** — say "trivial: implement directly with /ravend:build" and stop |
| small | one module/layer, behavior clear | spec with Problem, Acceptance criteria, Tasks |
| large | several modules or full stack, new API/DB contract, migration, security, or real ambiguity | full template incl. Design |
| bug | defect report | Problem (observed vs expected + repro), AC = the regression test, Tasks |

The user can force a tier (`--tier`). When unsure between two tiers, pick the larger only if a wrong guess would cost rework across modules.

## 3. Ambiguity
List assumptions explicitly. If an open question changes the design or the acceptance criteria, it is **blocking**: interactive → ask (AskUserQuestion, ≤4 questions, with a recommended option); headless → put it under `## Open questions` and report it as blocking. Never invent business rules silently.

## 4. Write the spec
Use [references/spec-template.md](references/spec-template.md). Rules:
- Acceptance criteria are **Given/When/Then**, each tagged with the test level that will prove it: `[unit]`, `[api]`, `[e2e]`, `[visual]`. They become tests in /ravend:build — write them so a test can assert them.
- Tasks are vertical and small (one commit each), each lists the files it touches and the ACs it proves. Mark `[P]` only when tasks touch disjoint files and have no dependency.
- Design section only for `large`: what changes and why, contracts (endpoints/DTOs/schema), trade-offs. Do not restate the codebase.
- Slug: kebab-case, ≤40 chars. Branch: `<profile.git.branch_prefix or feat/><slug>`.
- If an existing project lesson in `<data_dir>/knowledge/` applies, reference it in the task.

## 5. Approval
- `large`: interactive → present a 5-line summary + path and ask for approval; on approval set `status: approved`. Headless without `--approved` → leave `status: draft`.
- `small`/`bug`: set `status: approved` unless there are blocking questions.
- With `--approved`: set `status: approved`.

## Output
Interactive: summary (tier, #ACs, #tasks, path) and the next command (`/ravend:build <slug>`).
`--headless`: never ask questions; end with exactly one JSON object: `{"slug": "...", "tier": "...", "spec_path": "...", "blocking_questions": [...]}`.
