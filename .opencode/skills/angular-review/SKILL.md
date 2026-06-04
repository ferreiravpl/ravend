---
name: angular-review
description: Checklist de revisão para mudanças em codebases Angular.
compatibility: opencode
---
## Objetivo
Revisar mudanças Angular com foco em clareza, consistência, fluxo de dados e manutenção.

## Quando usar
Use quando a task envolver frontend Angular.

## O que avaliar
- responsabilidade clara do componente
- template legível
- lógica excessiva fora do lugar
- coerência entre componente, service e utilitário
- aderência ao padrão de reatividade do projeto
- impacto em teste, regressão funcional e manutenção

## Sinais de problema
- componente fazendo papel demais
- template difícil de entender
- service ausente onde deveria existir
- duplicação de regra
- quebra do padrão predominante do frontend

## Como classificar findings
- bloqueante: quebra funcional, contrato de interface importante, teste essencial ou regressão clara
- importante: compromete manutenção, legibilidade ou padrão central
- melhoria: refino opcional e localizado
