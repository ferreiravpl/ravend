---
name: ravend-self-evolution
description: Guia a evolução incremental do próprio Ravend como sistema agentic do repositório.
compatibility: opencode
---
## Objetivo
Permitir que o Ravend evolua o próprio harness de forma segura e incremental.

## Quando usar
Use quando o usuário pedir para:
- adicionar uma capacidade nova ao Ravend;
- revisar a identidade do Ravend;
- ajustar o fluxo SDD;
- mudar o desenho de agents, skills ou commands.

## Quando não usar
Não use para tarefas normais de feature do produto.

## Procedimento
1. Identificar qual parte do Ravend precisa evoluir.
2. Decidir se a mudança cabe melhor em:
   - `AGENTS.md`
   - agent
   - skill
   - command
   - contexto estável
   - manifest
3. Preferir a menor mudança sustentável.
4. Atualizar documentação quando necessário.
5. Preservar coerência com a identidade do Ravend.

## Armadilhas comuns
- criar agente novo quando uma skill basta;
- mover lógica demais para commands;
- colocar contexto variável em arquivo estável;
- crescer o harness sem necessidade real.
