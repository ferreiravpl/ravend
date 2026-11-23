# Ravend — plugin development

This repo is a Claude Code plugin (and its own marketplace). User-facing docs: README.md (pt-BR) — always the current state; change history goes in PR bodies, never in the README. Every version bump adds one pt-BR line per change to CHANGELOG.md (the update notice shows them; a unit test fails without an entry for the current version).

## Layout
- `skills/*/SKILL.md` — prompts. Bodies in English (token-efficient); `description` and `argument-hint` in pt-BR (shown in the `/` menu); everything shown to the user (questions, options, summaries) is pt-BR — the SessionStart hook injects this rule; skills that ask say it too. Keep each SKILL.md short; put long material in `references/`.
- `agents/*.md` — only reviewer, verifier, implementer. Add an agent only for context isolation or independence, never for "role play".
- `hooks/hooks.json` → `scripts/ravend.py hook <event>`. Hooks must be no-ops in repos without a local profile and must never crash a session.
- `scripts/ravend.py` — CLI entry point; the runtime lives in `scripts/ravend_lib/` (stdlib only, Python 3.8+), one module per responsibility: core, gating, mcp, detection, flow (state machine `next` + state records), diagnostics, hooks, cli. Modules import only modules listed before them (no cycles). `scripts/ravend_auto.py` — headless runner (`ravend auto`), driven by the same `next`.
- `docs/ARCHITECTURE.md` — architecture reference (pt-BR). A structural change (new file, module, stage) updates it in the same PR.
- The order of stages lives only in `next_action` (ravend.py). Skills and the runner ask it; never encode stage order in a prompt.
- Per-project data lives in `~/.ravend/projects/<id>/` (`RAVEND_HOME`); nothing is ever written into the target repo.

## Rules
- Anything that must be guaranteed (gate, formatting, protected paths, loop limits) belongs in code, not in prompt text.
- Changing a skill/agent → run the evals for the affected behavior. Changing the runtime → run the unit tests.

## Checks
```bash
python3 -m unittest discover -s tests
claude plugin validate . && claude plugin validate skills --strict && claude plugin validate agents
claude plugin eval . --scaffold --trust-plugin --allow-tools Bash Write Edit Agent --runs 1 --ablation none
```
