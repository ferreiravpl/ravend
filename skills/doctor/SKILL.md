---
name: doctor
description: "Diagnostica o Ravend neste repositório — Python, git, perfil, comandos do quality gate, MCPs escolhidos, gh e o comando de terminal — e diz exatamente o que está faltando e como resolver. Use quando algo não funcionar ou antes de usar o Ravend pela primeira vez num repositório."
disable-model-invocation: true
---

# Ravend · doctor

1. Run `python3 "$RAVEND_ROOT/scripts/ravend.py" doctor` (empty `RAVEND_ROOT` → this skill's base dir + `/../../scripts/ravend.py`). Its checks are code; do not re-check by hand.
2. Show the result in the user's language: errors first, then warnings, each with its fix in one line. All good → say so in one line.
3. Offer to fix what can be fixed from here, one at a time and only with consent:
   - no profile, missing gate command, MCP not configured → `/ravend:init`;
   - `ravend` command missing → `$RV install-cli`;
   - `gh` not authenticated → ask the user to run `! gh auth login`;
   - MCP failing → `claude mcp list` to see the error; re-authentication is the user's step.
Never edit `profile.json` silently: show the change first.
