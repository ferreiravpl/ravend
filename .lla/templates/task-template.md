# Template de Task

- id:
- título:
- propósito:
- entradas:
- arquivos em escopo:
- fora de escopo:
- passos:
- validação:
- definição de pronto:

## Execution Prompt

```xml
<execution_prompt>
  <task_context>{{contexto da task — de onde vem, por que existe}}</task_context>
  <objective>{{objetivo claro e delimitado}}</objective>
  <inspect_first>{{lista de arquivos a inspecionar antes de implementar}}</inspect_first>
  <interface_to_implement>{{interface ou contrato a implementar, se aplicável}}</interface_to_implement>
  <edge_cases>{{casos de borda a considerar}}</edge_cases>
  <tests_to_implement>{{testes a implementar ou verificar}}</tests_to_implement>
  <constraints>{{restrições: guardrails, padrões, limites}}</constraints>
</execution_prompt>
```
