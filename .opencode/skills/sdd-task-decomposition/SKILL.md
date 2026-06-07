---
name: sdd-task-decomposition
description: Quebra uma demanda em tarefas pequenas com critérios de aceite, execution prompts e handoff objetivo.
compatibility: opencode
---
## Objetivo
Reduzir a demanda a tarefas executáveis e verificáveis.

## Quando usar
Use após a spec ou quando houver plano suficiente para implementação.

## Procedimento

1. Divida o trabalho em tarefas pequenas.
2. Defina arquivos em escopo e fora de escopo.
3. Defina critérios de aceite e validação.
4. **Gere execution prompts** para cada task no formato XML:
   ```xml
   <execution_prompt>
     <task_context>de onde vem, por que existe</task_context>
     <objective>objetivo claro e delimitado</objective>
     <inspect_first>arquivos a inspecionar antes de implementar</inspect_first>
     <interface_to_implement>interface ou contrato a implementar</interface_to_implement>
     <edge_cases>casos de borda a considerar</edge_cases>
     <tests_to_implement>testes a implementar ou verificar</tests_to_implement>
     <constraints>restrições: guardrails, padrões, limites</constraints>
   </execution_prompt>
   ```
5. Atualize `tasks.md` com execution prompts e `task-scope.json` com campos novos (inspect_first, interface_to_implement, edge_cases, tests_to_implement, constraints, complexity, depends_on, parallelizable).

## Regras

- Cada task deve ser independente o suficiente para ser implementada por um subagent.
- Execution prompts devem conter contexto mínimo suficiente — nem mais, nem menos.
- Tasks paralelas devem ser marcadas com `parallelizable: true`.
- Dependências devem ser explícitas em `depends_on`.
