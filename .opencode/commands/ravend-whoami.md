---
description: Explica quem é o Ravend, como está operando e quais capacidades estão ativas.
agent: orchestrator
---
Explique quem é o Ravend neste repositório.

Inclua:
- identidade operacional
- fluxo padrão
- contexto carregado
- commands principais
- skills relevantes
- forma de otimização do próprio harness

## Auto-check de referências

Antes de responder, valide a saúde do harness:

1. Parseie todos os JSONs em `.lla/manifests/` e `.lla/manifests/schemas/` — reporte qualquer JSON inválido.
2. Verifique que paths locais referenciados em skills, agents e commands (ex.: `.lla/...`, `.opencode/...`) existem em disco — reporte referências quebradas.
3. No final do output, declare: `check: OK` ou liste os problemas encontrados.
