---
name: quarkus-implementation
description: Padrões e checklist para implementar mudanças em codebases Quarkus.
compatibility: opencode
---
## Objetivo
Aplicar boas práticas de implementação em Quarkus.

## Quando usar
Use quando a task envolver backend Quarkus.

## Verificar antes de implementar
- organização por camadas já existente no projeto
- recursos CDI e escopo corretos
- consistência com padrões REST existentes
- validações e tratamento de erro já adotados no projeto
- testes compatíveis com o padrão atual da codebase

## Armadilhas comuns
- criar abstrações desnecessárias
- fugir do padrão já usado pelo projeto
- misturar responsabilidade de recurso, serviço e persistência
- adicionar complexidade sem necessidade

## Procedimento
1. Ler convenções e stack do projeto.
2. Ler arquivos vizinhos da mesma feature.
3. Reusar padrões do projeto antes de criar novos.
4. Implementar a menor mudança segura.
