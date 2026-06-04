---
name: spring-review
description: Checklist de revisão para mudanças em codebases Spring.
compatibility: opencode
---
## Objetivo
Revisar mudanças Spring com foco em corretude, clareza de camadas e manutenção.

## Quando usar
Use quando a task envolver backend Spring.

## O que avaliar
- controller sem lógica excessiva
- service com responsabilidade clara
- repository coerente com o padrão do projeto
- DTOs e validações consistentes
- transação no lugar certo
- impacto em teste e regressão
- aderência ao padrão real da aplicação

## Sinais de problema
- controller orquestrando regra de negócio
- service monolítico
- repository fazendo papel indevido
- validação espalhada de forma confusa
- divergência forte da convenção do projeto

## Como classificar findings
- bloqueante: quebra corretude, contrato, segurança, transação crítica ou teste essencial
- importante: fere claramente manutenção, clareza ou padrão central
- melhoria: refino não bloqueante
