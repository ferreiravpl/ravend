# Ravend — plugin development

This repo is a Claude Code plugin (and its own marketplace). User-facing docs: README.md (pt-BR).

## Layout
- `skills/*/SKILL.md` — prompts. Bodies in English (token-efficient), user-facing output follows the user's language. Keep each SKILL.md short; put long material in `references/`.
- `agents/*.md` — only reviewer, verifier, implementer. Add an agent only for context isolation or independence, never for "role play".
- `hooks/hooks.json` → `scripts/ravend.py hook <event>`. Hooks must be no-ops in repos without a local profile and must never crash a session.
- `scripts/ravend.py` — runtime (stdlib only, Python 3.8+). `scripts/ravend_run.py` — headless runner.
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
