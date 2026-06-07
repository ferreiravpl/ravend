# Guardrail — Context Economy

## Nome
context-economy

## applyTo
orchestrator

## Severidade
P1

## Regra
Não carregar mais de 3 skills em um mesmo agente sem necessidade explícita. Não carregar documentação inteira sem escopo. Não passar o repositório inteiro para subagents.

## Verificação
- Contar skills carregadas no handoff do agente
- Verificar se cada skill é necessária para a tarefa específica
- Se >3 skills: justificar no handoff ou remover

## Correção
1. Identificar skills estritamente necessárias para a tarefa
2. Remover skills que não contribuem para o objetivo
3. Usar `knowledge-index.json` para carregar apenas entradas relevantes
4. Preferir resumo incremental a contexto longo

## Exceções
- Tarefas full-stack que legitimamente precisam de skills de backend + frontend
- Primeira execução do fluxo SDD completo (intake → PRD → spec → tasks)

## Referência
`AGENTS.md` — Princípios de economia de tokens
