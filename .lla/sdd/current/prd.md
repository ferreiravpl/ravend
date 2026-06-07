# PRD — Incremento do Ravend via Análise Comparativa com ai-workflow

## Problema
O Ravend tem arquitetura sólida (princípios, agentes, skills, commands) mas gaps operacionais críticos: QA não executa build real, review não produz score numérico, não há loop de retry entre reviewer e implementer, knowledge base está vazia, não existem guardrails, não há separação de prompts estáticos/dinâmicos para caching, e faltam contratos de output entre agentes. Esses gaps fazem o Ravend funcionar como orquestrador de promessas em vez de orquestrador de resultados.

## Objetivo
Tornar o Ravend funcionalmente equivalente ao ai-workflow nos gates de qualidade (QA com build, review com score, loop de retry), adicionando defesa em camadas (knowledge, guardrails, style policy) e melhorias estruturais (schemas de output, execution prompts, session template, prompt caching, artifact guardrails, precedência de instruções).

## Não objetivos
- Replicar elementos específicos do projeto gumga-anymarket (guardrails de ML, DTO builder, required-args-constructor)
- Integrar com Azure DevOps ou GitLab
- Empacotar checkstyle.xml no harness
- Criar automação de commit/push/PR
- Substituir o princípio de minimalismo do Ravend por cerimônia excessiva

## Usuários / Atores
- **Operador do Ravend** — usa o harness para conduzir desenvolvimento assistido por IA
- **Agentes Ravend** — consomem as novas skills, guardrails, schemas e knowledge
- **Projetos-alvo** — recebem QA com build real e review com score

## Escopo

### Dentro do escopo (P0 — crítico)
1. QA com build real, testes com escopo restrito, lint gate e guardrail validators
2. Review com score 0-100 determinístico, P0/P1/P2 e output JSON estruturado
3. Loop de retry reviewer↔implementer (max 3 iterações, max 2 QA retries, escalada)

### Dentro do escopo (P1 — defesa em camadas)
4. Knowledge base pré-seeded com anti-patterns e frequência (freq ≥ 3 = hard constraint)
5. Guardrails com applyTo (class-size, code-formatting, unit-test-naming, context-economy, minimal-change)
6. Style policy como fonte canônica de thresholds numéricos
7. Artifact guardrails — verificação de persistência antes de handoff
8. Precedência de instruções do pipeline sobre repositório-alvo

### Dentro do escopo (P2 — estrutura e observabilidade)
9. Execution prompts estruturados por task (XML com task_context, objective, inspect_first, interface, edge_cases, tests, constraints)
10. Schemas de output por agente (review-output, qa-output, plan-output)
11. Prompt caching via system prompts estáticos separados
12. Session template com métricas de execução

### Fora do escopo
- Guardrails específicos de projeto (mercadolivre, dto-builder, required-args)
- Skills de Azure DevOps / GitLab / commit-and-open-mr
- Checkstyle.xml empacotado
- metrics.jsonl (overengineering)
- Codebase-discovery skill (stack-routing já cobre)

## Restrições
- Preservar princípios do Ravend: minimalismo, menor caminho seguro, simplicidade
- Cada incremento deve ser independente e incremental
- Não aumentar complexidade sem ganho claro
- Guardrails genéricos no harness, específicos em .lla/context/ do projeto
- Projeto-alvo com regras próprias prevalece sobre defaults do Ravend

## Critérios de aceite
1. QA executa build real (mvn compile / npm build) com timeout e escopo restrito aos módulos afetados
2. QA executa testes unitários com escopo restrito e reporta PASS/FAIL com error_type
3. QA executa lint gate (checkstyle do projeto-alvo + ESLint) e guardrail validators
4. Review produz score 0-100 com regras de dedução determinísticas (base 100, P0→min 50, P1→-10, P2→sem dedução)
5. Review classifica findings em P0/P1/P2 com ações obrigatórias quando reprovado
6. Review produz output JSON validável por schema
7. Loop de retry: max 3 iterações de review, max 2 retries de QA, escalada para humano se não convergir
8. Knowledge base tem anti-patterns pré-seeded com IDs, stack, severidade, correção e frequência
9. Guardrails são carregados condicionalmente por stack e validados pelo QA
10. Style policy define thresholds canônicos (linha 140, classe 150, método 30, complexidade 5)
11. Artifact guardrails: agente confirma persistência antes de handoff
12. AGENTS.md tem regra de precedência: desenvolvedor > Ravend > projeto-alvo
13. Execution prompts em XML por task com inspect_first, interface, edge_cases, tests, constraints
14. Schemas de output para QA e reviewer validam handoff máquina-a-máquina
15. System prompts estáticos separados para implementer, reviewer e QA
16. Session template com métricas (iterações QA, review, skills, guardrails, score final)

## Riscos
- Score determinístico pode ser rígido demais para casos edge → mitigar com score_override_reason
- QA com build real depende de ferramentas no ambiente → mitigar com QA profile auto-detect e fallback graceful
- Guardrails podem conflitar com convenções do projeto-alvo → mitigar com precedência do projeto
- Mais schemas = mais manutenção → mitigar com schemas pequenos e additionalProperties: false
- Prompt caching depende do runtime → mitigar: separar system.md é boa prática independente de caching
