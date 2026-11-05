---
name: start
description: "Começa uma demanda nova e conduz até o PR — escreve a spec do tamanho certo, implementa com testes, verifica, faz o review e pede sua autorização antes de abrir o PR. Aceita texto livre, chave do Jira (PROJ-123) ou issue do GitHub (#45 ou URL)."
argument-hint: "<demanda | PROJ-123 | #45>"
disable-model-invocation: true
---

# Ravend · start

You are the orchestrator; there is no separate orchestrator agent. The order of the stages is not yours to decide: after the spec exists, `ravend.py next` decides every step (same state machine as `/ravend:continue` and the headless runner).

1. **Spec** — invoke `ravend:spec` with `$ARGUMENTS`. It decides the tier.
2. **Trivial** (no spec written) → invoke `ravend:build` with the change description, then `python3 "$RAVEND_ROOT/scripts/ravend.py" gate full`. Green → ask the user before invoking `ravend:ship` (no slug: trivial change). Stop.
3. **Everything else** → invoke `ravend:continue <slug>` and let it drive until a checkpoint (spec approval for large, PR authorization) or a stop.

Tell the user in one line, in their language, what happens next at each handover. Everything needed to resume lives on disk, so after `/clear` or a new session the user only needs `/ravend:continue`.

For unattended runs (CI, background), point the user to `ravend auto "<demanda>"` in the terminal.
