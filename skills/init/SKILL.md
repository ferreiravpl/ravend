---
name: init
description: "Configura o Ravend neste repositório, na sua máquina — descobre os comandos de build, teste e lint, monta o quality gate, escreve notas do projeto, pergunta quais dos seus MCPs usar em cada etapa e oferece o comando `ravend` no terminal. Nada é gravado no repositório. Rode de novo para refazer qualquer parte."
disable-model-invocation: true
---

# Ravend · init

Everything this skill writes goes to `<data_dir>` (`~/.ravend/projects/<project-id>/` unless `RAVEND_HOME` is set). Do **not** create or modify files in the repository (no CLAUDE.md, no scripts, no config) — other developers use the repo too.

## 1. Facts first
`RV="python3 $RAVEND_ROOT/scripts/ravend.py"` (empty `RAVEND_ROOT` → this skill's base dir + `/../../scripts/ravend.py`).
- `$RV project` → `data_dir`, `has_profile`, `base_branch`.
- `$RV detect` → modules, stacks, build tools, test runners, lint/format signals, compose files.
- Existing profile → show a short summary and ask which parts to redo (AskUserQuestion, multiSelect): gate commands (steps 2–4), project notes (5), MCP integrations (6), terminal command (7). Run only those.

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

## 6. Integrations — the developer's own MCP servers
The pipeline adapts to the tools this developer already has; install or change nothing without asking.
1. **Inventory**: `$RV mcp` (config files + `claude mcp list`: user/local/project, plugin servers, claude.ai connectors, with status; never secrets) plus the `mcp__*` tool namespaces visible in this session. Roles and the stages that use them: `$RV integrations`.
2. **Match** servers to roles by name/hint/tools (a server may fill several): atlassian/jira/linear → `issues`; github/gitlab/bitbucket → `git` (and `issues` for GitHub issues); serena/sourcegraph/code index → `context`; context7/vendor docs → `docs`; confluence/notion/drive → `knowledge`; figma → `design`; playwright/chrome-devtools → `browser`; postman/api-test → `api`; postgres/mysql/mongo → `database`; sentry/datadog/grafana → `observability`.
3. **Ask** with AskUserQuestion in the user's language, one question per role that has candidates (≤4 per call; batch the rest), `multiSelect: true`, options = candidates (name + what it would be used for, recommended first) + "Nenhum". E.g. "Você tem um MCP de contexto do código? Selecione os que o Ravend deve usar ao explorar e revisar." The user may answer "Other" with any inventory server. Skip roles without candidates; then one last question listing the uncovered roles and offering the defaults at local scope: `browser` (only with a UI module) → `claude mcp add playwright --scope local -- npx -y @playwright/mcp@0.0.84`; `docs` → `claude mcp add context7 --scope local -- npx -y @upstash/context7-mcp@4.5.0`; Jira with no MCP → the Atlassian remote MCP (README).
4. **Save** in `profile.json`: `"integrations": {"<role>": ["<exact server name as listed by $RV mcp>"]}` (omit unchosen roles). A server that is currently failing may be chosen — mention it. From then on the session start lists them, each stage uses its roles, and the headless runner allows their tools only in those stages. New MCP servers take effect in the next session.

## 7. Terminal command (ask)
Offer `$RV install-cli`: installs `ravend` in `~/.local/bin` (outside the repo, follows plugin updates) so the developer can run `ravend auto "<demanda>"` (unattended pipeline), `ravend next`, `ravend doctor`, `ravend gate full`. If the output says the dir is not on PATH, show the line to add.
Suggest the `superpowers` plugin (brainstorming, systematic debugging, TDD discipline) if not installed.

## Output
Summary: project id, data dir, stacks, gate fast/full steps (one line each), baseline result, integrations (role → server), recommendations. Then run `$RV doctor` and show anything still missing. Next: `/ravend:start <demanda>`.
