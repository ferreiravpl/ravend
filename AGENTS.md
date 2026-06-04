# Ravend — Regras Operacionais do Orquestrador

## Missão

Orquestrar desenvolvimento de software com SDD como fluxo padrão:

intake -> PRD -> tech spec -> task decomposition -> implementação -> QA -> review -> loop até aceite

## Regras principais

- O fluxo SDD é o padrão, não a única opção.
- O menor fluxo seguro deve ser preferido.
- Se já existir plano suficiente, o sistema pode seguir por fast path.
- O estado relevante deve ser persistido em `.lla/sdd/current/`.
- Contratos operacionais devem ficar em `.lla/manifests/`.
- Conhecimento incremental deve ser seletivo, nunca carregado integralmente por padrão.
- Use Markdown para raciocínio humano e JSON para contratos operacionais.
- Não expandir escopo sem necessidade.
- Não usar commands como cérebro do sistema; commands são portas de entrada.

## Fluxos permitidos

### Fluxo completo
Use quando a demanda estiver mal especificada ou tiver impacto arquitetural relevante.

### Fast path de implementação
Use quando já existir task bem delimitada e plano suficiente.

### Fast path de QA
Use quando o objetivo for validar tecnicamente um escopo já definido.

### Fast path de review
Use quando o objetivo for revisar mudança existente.

## Política de persistência

Arquivos principais em `.lla/sdd/current/`:
- `intake.md`
- `prd.md`
- `tech-spec.md`
- `tasks.md`
- `progress.md`
- `decisions.md`
- `qa-report.md`
- `review-report.md`
- `acceptance.md`

## Política de manifests

Arquivos principais em `.lla/manifests/`:
- `task-scope.json`
- `agent-handoff.json`
- `knowledge-index.json`

Esses manifests existem para reduzir ambiguidade entre agentes.

## Política de knowledge

A knowledge base fica em `.lla/knowledge/` e é dividida por:
- `reviewer/`
- `implementer/`
- `shared/`

Regras:
- não carregar tudo por padrão;
- primeiro consultar `knowledge-index.json`;
- depois carregar apenas entradas compatíveis com stack, camada, role e issue-type.

## Política de delegação

O agente principal é `orchestrator`.

Ele pode delegar para:
- `intake`
- `spec-writer`
- `planner`
- `task-decomposer`
- `implementer`
- `qa`
- `reviewer`
- `knowledge-curator`

## Regras de qualidade

- QA valida, não redesenha a solução.
- Reviewer revisa, não implementa correções.
- Implementer implementa apenas uma task delimitada por vez.
- Planner planeja e delega; não deve virar implementador.
- Knowledge-curator sintetiza aprendizado; não registra transcrição bruta.
