---
name: init
description: Set up Ravend for the current repository on this developer's machine — detect stacks, build the local gate profile (build/test/lint/format/app/E2E commands), write project notes, and optionally configure Playwright/Context7 MCP servers at local scope. Nothing is written into the repository.
argument-hint: [--refresh]
disable-model-invocation: true
---

# Ravend · init

Everything this skill writes goes to `<data_dir>` (`~/.ravend/projects/<project-id>/` unless `RAVEND_HOME` is set). Do **not** create or modify files in the repository (no CLAUDE.md, no scripts, no config) — other developers use the repo too.

## 1. Facts first
`RV="python3 $RAVEND_ROOT/scripts/ravend.py"` (empty `RAVEND_ROOT` → this skill's base dir + `/../../scripts/ravend.py`).
- `$RV project` → `data_dir`, `has_profile`, `base_branch`.
- `$RV detect` → modules, stacks, build tools, test runners, lint/format signals, compose files.
- Existing profile and no `--refresh` → show it and ask what to change.

## 2. Confirm commands (read, don't guess)
For each module read only: the build file sections that matter (plugins: surefire/failsafe, spotless, checkstyle, jacoco, pitest; or package.json `scripts`), CI config if present (`.github/workflows/*.yml` — the commands CI runs are the best source of truth), README "how to run/test". Check wrappers (`./mvnw`, `./gradlew`) and the package manager lockfile.

## 3. Build `profile.json`
Schema and per-stack examples: [references/profile.md](references/profile.md). Principles:
- **gate.fast** = what runs after every task, scoped to the change, aims for < 2 min: compile/typecheck + tests related to changed files (`{java_tests}`, `vitest related {files}`, `jest --findRelatedTests {files}`) + lint on changed files.
- **gate.full** = what CI would run for this change: full build + all tests of affected modules + lint + integration + E2E (`needs_app` when it requires the running app) + optional coverage/mutation.
- **format** = only fast per-file formatters (prettier, eslint --fix, biome). Heavy JVM formatters (spotless) go as the first gate step instead.
- Prefer the repo's own scripts/plugins; never add tools to the repo. If something important is missing (no linter, no E2E setup), note it as a recommendation, don't install it.
- `protected_paths`: secrets and generated files the agent must never edit.
- `headless.allowed_tools`: Bash patterns the unattended runner may use (e.g. `Bash(docker compose *)`); gate/app commands are allowed automatically.
Write it with the Write tool to `<data_dir>/profile.json`, then `$RV gate full --dry-run` to show the resolved commands.

## 4. Baseline
Ask whether to run `$RV gate full` now (can take minutes). A red baseline is important: record pre-existing failures in project notes so later tasks are not blamed for them.

## 5. Project notes
Write `<data_dir>/project.md`, **≤40 lines**, only what is not obvious from the code and is useful on every task: module map (1 line each), how to run things locally, test conventions (naming, levels, fixtures, Testcontainers/Dev Services), layering and error-handling conventions, generated code to never edit, known flaky tests, baseline failures. Derive conventions from 2–3 representative files per module, not from general best practices. This file is injected at session start — keep it lean.

## 6. Tooling (ask first; local scope = this developer only)
- UI module present → Playwright MCP for exploring/authoring E2E:
  `claude mcp add playwright --scope local -- npx -y @playwright/mcp@0.0.84`
- Library docs on demand → `claude mcp add context7 --scope local -- npx -y @upstash/context7-mcp@4.5.0`
- Jira as a source → the Atlassian remote MCP (see README).
- Suggest the `superpowers` plugin (brainstorming, systematic debugging, TDD discipline) if not installed.
MCP changes take effect in the next session.

## Output
Summary: project id, data dir, stacks, gate fast/full steps (one line each), baseline result, recommendations. Next: `/ravend:run <demand>`.
