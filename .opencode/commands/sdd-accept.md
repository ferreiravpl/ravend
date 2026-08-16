---
description: Consolida aceite da entrega atual quando QA e review estiverem satisfatórios.
agent: orchestrator
---
Consolide o aceite da entrega atual.

Para a task especificada (ou a única ativa):
1. Leia `.lla/sdd/current/{task_id}/qa-report.md` e `.lla/sdd/current/{task_id}/review_{N}.md`.
2. Atualize `.lla/sdd/current/{task_id}/progress.md` com status final.
3. Atualize `.lla/sdd/current/shared/acceptance.md` com referência à task aceita.
4. **Arquivar**: mova `.lla/sdd/current/{task_id}/` para `~/.ravend/archive/{date}_{task_id}-{slug}/`.
   - Crie `~/.ravend/archive/` se não existir.
   - O slug é derivado do título da task (sanitizado, max 40 chars).
5. Se todas as tasks da demanda foram aceitas, mova `.lla/sdd/current/shared/` para `~/.ravend/archive/{date}_shared-{demand-slug}/`.
