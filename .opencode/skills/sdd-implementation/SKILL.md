---
name: sdd-implementation
description: Guia a implementação de uma única task com contexto mínimo suficiente, execution prompts e guardrails.
compatibility: opencode
---
## Objetivo
Implementar sem inflar escopo nem contexto.

## Quando usar
Use quando existir task ativa delimitada.

## Procedimento

1. **Leia a task ativa** e apenas artefatos relevantes.
2. **Leia o execution prompt** da task (seção `<execution_prompt>` no tasks.md ou campo no task-scope.json).
3. **Siga o execution prompt**: inspecione arquivos listados em `inspect_first` antes de implementar.
4. **Carregue guardrails** condicionais da stack (`.lla/guardrails/`) antes de implementar.
5. **Carregue knowledge** relevante (consulte `knowledge-index.json` por stack e camada).
6. **Implemente a mudança delimitada** seguindo constraints do execution prompt.
7. **Registre decisões** importantes em `.lla/sdd/current/{task_id}/decisions.md`.

O `task_id` é fornecido pelo orchestrator no prompt ou handoff.

## Regras

- Não implemente nada fora do escopo do execution prompt.
- Se o execution prompt não cobrir algo necessário, registre em decisions.md e comunique ao orchestrator.
- Respeite guardrails como hard constraints (especialmente `minimal-change` — P0).
- Quando chamado para correção pós-review, leia ações obrigatórias do review e corrija apenas P0/P1.
- Quando chamado para correção pós-QA, leia qa-report e corrija apenas o que causou a falha.
