---
name: spring-implementation
description: Padrões e checklist para implementar mudanças em codebases Spring.
compatibility: opencode
---
## Objetivo
Aplicar boas práticas de implementação em Spring respeitando o padrão real da aplicação.

## Quando usar
Use quando a task envolver backend Spring.

## Quando não usar
Não use para Quarkus ou Angular.
Não use para impor arquitetura teórica se a codebase já tiver convenção consolidada.

## O que observar primeiro
- padrão de controllers, services e repositories
- forma como DTOs e validações são usados
- estratégia de transação da aplicação
- estilo de testes predominante
- convenções de erro, resposta e mapeamento

## Princípios
- seguir a arquitetura existente;
- não mover regra de negócio para controller;
- manter service coeso;
- evitar transaction sem critério;
- reaproveitar padrões já aceitos pelo time.

## Checklist de implementação
1. Controller está fino e sem lógica indevida.
2. Service concentra a lógica que realmente pertence ao caso de uso.
3. Repository está consistente com a convenção existente.
4. DTOs e validações seguem o padrão do projeto.
5. Transações estão onde fazem sentido.
6. Não há camadas artificiais só por formalidade.
7. Testes acompanham a alteração no nível adequado.
8. A mudança está pequena e legível.

## Armadilhas comuns
- controller inchado
- service gigante e sem foco
- transaction colocada por hábito
- mapeamento espalhado de forma inconsistente
- criar novas abstrações sem ganho real

## Saída esperada
- implementação aderente ao padrão do projeto
- baixo acoplamento adicional
- clareza entre camadas
- testes coerentes com a mudança
