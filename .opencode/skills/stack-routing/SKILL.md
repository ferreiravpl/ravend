---
name: stack-routing
description: Identifica stack dominante e orienta o planner a selecionar as skills corretas.
compatibility: opencode
---
## Objetivo
Ajudar o planner a decidir qual stack domina a task.

## Quando usar
Use antes de implementação e review quando a stack da task não estiver explícita.

## Procedimento
1. Ler estrutura do repo.
2. Procurar sinais em arquivos de build, pastas e convenções.
3. Identificar se a task é:
   - Quarkus
   - Spring
   - Angular
   - full stack
4. Selecionar a menor combinação de skills necessária.

## Heurísticas úteis
- presença de `angular.json`, `src/app`, `package.json` com Angular indica frontend Angular;
- presença de `pom.xml` ou `build.gradle` com convenções do projeto ajuda a diferenciar backend Java;
- o padrão real da codebase vale mais que regra genérica.

## Saída esperada
- stack dominante
- natureza da mudança
- skills recomendadas
