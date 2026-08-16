---
description: Retoma a execução a partir do estado persistido atual.
agent: orchestrator
---
Retome o fluxo atual usando os artefatos em `.lla/sdd/current/`.

Identifique tasks ativas (subdiretórios de `current/` que não sejam `shared/`).
Se houver mais de uma task ativa e nenhum `task_id` for fornecido, liste as tasks e peça ao dev para escolher.
Se houver apenas uma task ativa, retome ela automaticamente.

Para cada task ativa, leia `.lla/sdd/current/{task_id}/progress.md` para identificar a fase atual, o próximo passo e os bloqueios.
Artefatos compartilhados (intake, prd, tech-spec, tasks) estão em `.lla/sdd/current/shared/`.
