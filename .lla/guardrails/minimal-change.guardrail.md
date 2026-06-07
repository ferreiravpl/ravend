# Guardrail — Minimal Change

## Nome
minimal-change

## applyTo
implementer

## Severidade
P0

## Regra
Não expandir escopo da task. Implementar apenas o que está definido no execution prompt e nos critérios de aceite. Não refatorar código adjacente, não adicionar features "complementares", não criar abstrações sem necessidade real.

## Verificação
- Comparar diff com o escopo definido na task
- Verificar se cada arquivo modificado está na lista de "arquivos em escopo"
- Verificar se cada mudança é necessária para o objetivo da task

## Correção
1. Reverter mudanças fora de escopo
2. Registrar decisões de design em `decisions.md` se houver ambiguidade
3. Se escopo parece insuficiente, comunicar ao orchestrator em vez de expandir

## Exceções
- Correção de bug bloqueante descoberto durante implementação (registrar em decisions.md)
- Mudança mínima necessária para compilar (import, dependência)

## Referência
`AGENTS.md` — "Não expandir escopo sem necessidade"
