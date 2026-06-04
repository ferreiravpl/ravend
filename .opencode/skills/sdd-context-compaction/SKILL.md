---
name: sdd-context-compaction
description: Compacta o estado de sessões longas em arquivos persistentes.
compatibility: opencode
---
## Objetivo
Reduzir pressão de contexto e preservar continuidade.

## Quando usar
Use em transições de fase ou quando o histórico estiver grande.

## Procedimento
1. Resuma progresso e decisões em arquivos próprios.
2. Atualize manifests ativos.
3. Elimine dependência de memória conversacional longa.
