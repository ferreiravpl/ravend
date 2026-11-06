---
name: continue
description: "Retoma o trabalho de onde parou — pergunta ao Ravend qual é o próximo passo da spec (implementar, verificar, corrigir, revisar ou abrir o PR) e executa, parando só quando precisa de você. Use depois de fechar a sessão, de um /clear ou quando não souber em que etapa está."
argument-hint: "[slug, só se houver mais de uma spec em andamento]"
---

# Ravend · continue

The next step is decided by code, never by you: `ravend.py next` reads the spec, the gate state and the verify/review records and answers one action. Your job is to execute it, then ask again.

`RV="python3 $RAVEND_ROOT/scripts/ravend.py"` (empty `RAVEND_ROOT` → this skill's base dir + `/../../scripts/ravend.py`).

## Loop
1. `$RV next $ARGUMENTS --json` (no argument → it picks the only active spec, or the one whose branch is checked out).
2. Tell the user one line in their language: `▸ <action>: <message>`.
3. Do what the action says:

| action | do |
|---|---|
| `start` | No active spec: tell the user to run `/ravend:start <demanda>`. Stop. |
| `choose` | Ask which spec (AskUserQuestion, options from `options`), then loop with that slug. |
| `answer` | Ask the user the `questions` (AskUserQuestion, recommended option first). Write the answers into the spec (resolve `## Open questions`, adjust criteria/tasks). Then loop. |
| `approve` | Show a 5-line summary of the spec + its path and ask for approval. Yes → `$RV spec approve <slug>`. Changes → edit the spec, ask again. |
| `build`, `fix` | Invoke `ravend:build <slug>` (it reads `next` itself to know whether it is a task or a fix). |
| `verify` | Invoke `ravend:verify <slug>`. |
| `review` | Invoke `ravend:review <slug>`. |
| `ship` | **Checkpoint**: ask the user before invoking `ravend:ship <slug>` — push and PR are visible to the team. |
| `human` | Stop. Summarize `message`, the `blocking` findings / `review` file and what was tried; hand over. |
| `done` | Say so, with the PR link if present. Stop. |

4. Back to 1 until a checkpoint, `human`, `done` or the user stops you.

## Rules
- Never skip, reorder or repeat a stage on your own judgment; if you disagree with `next`, tell the user why instead.
- If `next` returns the same action and message right after you ran that stage, the stage did not record its result (e.g. a task not ticked with `$RV task done`, a verify not recorded). Fix the record or stop and say so — do not loop.
- Keep this session's context for decisions; stages delegate noisy work to their own agents.
