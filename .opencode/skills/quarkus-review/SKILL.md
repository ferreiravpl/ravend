---
name: quarkus-review
description: Checklist de revisão para mudanças em codebases Quarkus.
compatibility: opencode
---
## Objetivo
Revisar mudanças Quarkus com foco em corretude, clareza, coesão e risco.

## Quando usar
Use quando a task envolver backend Quarkus.

## O que avaliar
- aderência ao padrão real do projeto
- clareza de separação entre resource, service e persistência
- consistência do contrato da API
- coerência da validação
- tratamento de erro
- impacto em manutenção e teste
- presença de complexidade desnecessária

## Sinais de problema
- resource com lógica demais
- service artificial sem responsabilidade clara
- persistência vazando para camadas erradas
- excesso de abstração para mudança simples
- divergência grande do padrão dominante do projeto

## Como classificar findings
- bloqueante: quebra corretude, contrato, segurança, teste essencial ou arquitetura crítica
- importante: prejudica clareza, manutenção ou aderência relevante ao padrão
- melhoria: ajuste útil, mas não bloqueante
