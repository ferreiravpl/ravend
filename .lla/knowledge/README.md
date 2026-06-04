# Base de Conhecimento

## Objetivo

Armazenar aprendizado incremental sem forçar carga de contexto total.

## Regras

- Nunca carregar toda a base por padrão.
- Sempre consultar primeiro `.lla/manifests/knowledge-index.json`.
- Carregar somente entradas relevantes à role, framework, camada e tipo de problema.
- Preferir uma lição por arquivo.
- Preferir orientação compacta a transcrição longa.

## Estrutura

- `reviewer/`: lições originadas de review
- `implementer/`: guardrails de implementação
- `shared/`: convenções ou lições compartilhadas
