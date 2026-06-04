---
name: spring-implementation
description: Padrões e checklist para implementar mudanças em codebases Spring.
compatibility: opencode
---
## Objetivo
Aplicar boas práticas de implementação em Spring.

## Quando usar
Use quando a task envolver backend Spring.

## Verificar antes de implementar
- organização por camadas adotada no projeto
- uso coerente de services, controllers e repositories
- padrão de DTOs e validação já existente
- convenções de transação já adotadas
- testes coerentes com a codebase

## Armadilhas comuns
- lógica demais no controller
- service inchado sem necessidade
- transação em lugar inadequado
- divergência do padrão já consolidado na aplicação

## Procedimento
1. Ler convenções e stack do projeto.
2. Ler exemplos próximos da mesma feature.
3. Reusar o padrão dominante.
4. Implementar a menor mudança segura.
