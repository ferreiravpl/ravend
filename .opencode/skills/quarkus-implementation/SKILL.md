---
name: quarkus-implementation
description: Padrões e checklist para implementar mudanças em codebases Quarkus.
compatibility: opencode
---
## Objetivo
Aplicar boas práticas de implementação em Quarkus respeitando o padrão real da codebase.

## Quando usar
Use quando a task envolver backend Quarkus.

## Quando não usar
Não use para Spring ou Angular.
Não use para impor um estilo genérico de Java se o projeto já tiver um padrão claro diferente.

## O que observar primeiro
- estrutura real dos módulos
- padrão dominante de resources, services e persistência
- convenção de DTOs, mapeadores e validação
- estilo de testes da aplicação
- bibliotecas e extensões já adotadas pelo projeto

## Princípios
- seguir o padrão dominante da codebase;
- evitar abstração antecipada;
- manter responsabilidade clara entre camadas;
- preferir mudança pequena e coesa;
- reutilizar componentes existentes antes de criar novos.

## Checklist de implementação
1. A mudança está limitada à task ativa.
2. A responsibility split entre resource, service e persistência está clara.
3. O contrato da API segue o padrão do projeto.
4. A validação acontece no lugar coerente com a codebase.
5. Tratamento de erro está consistente com o restante do sistema.
6. A alteração não introduz acoplamento desnecessário.
7. Os testes seguem o padrão existente.
8. A solução evita overengineering.

## Armadilhas comuns
- colocar regra de negócio diretamente em resource
- criar service ou mapper só por formalismo
- misturar persistência com lógica de orquestração
- inventar padrão novo sem necessidade
- aumentar a superfície de alteração para resolver problema pequeno

## Saída esperada
- implementação pequena, legível e alinhada com a codebase
- testes compatíveis com o padrão já existente
- decisões relevantes registradas em `decisions.md`
