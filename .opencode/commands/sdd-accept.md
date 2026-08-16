---
description: Consolida aceite da entrega atual quando QA e review estiverem satisfatórios.
agent: orchestrator
---
Consolide o aceite da entrega atual.

Para a task especificada (ou a única ativa):
1. Leia `.lla/sdd/current/{task_id}/qa-report.md` e `.lla/sdd/current/{task_id}/review_{N}.md`.
2. Atualize `.lla/sdd/current/{task_id}/progress.md` com status final.
3. Atualize `.lla/sdd/current/shared/acceptance.md` com referência à task aceita.
4. **Gerar session.md**: crie `.lla/sdd/current/{task_id}/session.md` usando o template `.lla/templates/session-template.md`, preenchendo todos os campos:
   - **Meta**: feature_id (id da demanda), repo e branch (`git branch --show-current` + `git remote get-url origin`), data atual
   - **Métricas**: score_final do review mais recente; iterações_review = nº de `review_{N}.md` existentes; iterações_qa e skills/guardrails registrados no progress.md (se não registrados, use "N/A")
   - **Artefatos**: listar os arquivos de `.lla/sdd/current/{task_id}/` com seus paths
   - **Arquivos modificados**: `git diff --name-status` da entrega
   - **Resumo**: 2-3 frases sobre o que foi entregue
   - **Pendências**: itens P2 remanescentes ou notas do review final; "N/A" se nenhuma
5. **Arquivar**: mova `.lla/sdd/current/{task_id}/` (incluindo session.md) para `~/.ravend/archive/{date}_{task_id}-{slug}/`.
   - Crie `~/.ravend/archive/` se não existir.
   - O slug é derivado do título da task (sanitizado, max 40 chars).
6. Se todas as tasks da demanda foram aceitas, mova `.lla/sdd/current/shared/` para `~/.ravend/archive/{date}_shared-{demand-slug}/`.
