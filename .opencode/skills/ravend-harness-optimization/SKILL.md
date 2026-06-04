---
name: ravend-harness-optimization
description: Analisa e otimiza o próprio harness Ravend com foco em simplicidade, rastreabilidade e economia de contexto.
compatibility: opencode
---
## Objetivo
Otimizar o próprio Ravend sem inflar complexidade.

## Quando usar
Use quando o usuário pedir para:
- otimizar o fluxo;
- revisar a arquitetura do Ravend;
- reduzir tokens;
- simplificar agentes, skills ou commands;
- melhorar handoff e contexto.

## Quando não usar
Não use para implementar features do produto.
Não use para mudanças operacionais pequenas da aplicação que não envolvam o harness.

## Entradas esperadas
- `AGENTS.md`
- `opencode.json`
- `.opencode/agents/`
- `.opencode/commands/`
- `.opencode/skills/`
- `.lla/context/ravend-identity.md`
- `.lla/context/ravend-optimization.md`
- `.lla/manifests/`

## Procedimento
1. Entender o problema real do fluxo.
2. Separar sintomas de causas.
3. Identificar duplicação, excesso de agentes, excesso de contexto e handoff ruim.
4. Propor a menor mudança que gere ganho real.
5. Explicar trade-offs.
6. Se solicitado, aplicar a mudança incrementalmente.

## Checklist
- resolve o problema real?
- reduz complexidade?
- reduz contexto?
- melhora rastreabilidade?
- evita prompt monolítico?
- usa recursos nativos do OpenCode?

## Critérios de saída
- recomendação objetiva;
- trade-offs claros;
- proposta incremental;
- sem automação desnecessária.
