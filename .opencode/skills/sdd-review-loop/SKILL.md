---
name: sdd-review-loop
description: Avalia aderência ao escopo, qualidade e risco com score determinístico, findings P0/P1/P2 e output JSON estruturado.
compatibility: opencode
---

## Objetivo

Avaliar aderência ao escopo, qualidade e risco com score determinístico e classificação de findings em P0/P1/P2.

## Quando usar

Use após implementação ou após QA quando houver gate de review.

## Procedimento

1. **Carregar skills**: `sdd-review-loop` (baseline, sempre) + skill stack-specific condicional (`quarkus-review`, `spring-review`, `angular-review`) conforme stack detectada no diff.
2. **Carregar knowledge**: índice de anti-patterns em `.lla/knowledge/reviewer/` + segmento da stack em `.lla/knowledge/reviewer/{stack}/` quando existir.
3. **Carregar guardrails condicionais**: `.lla/guardrails/{stack}.md` quando existir.
4. **Ler diff e contexto**: `git diff`, `.lla/sdd/current/decisions.md` (se existir), `.lla/sdd/current/qa-report.md` (se existir).
5. **Analisar contra critérios**: verificar diff contra TODOS os critérios das skills carregadas (baseline + stack-specific + guardrails).
6. **Classificar findings** por severidade (P0/P1/P2) — ver regras abaixo.
7. **Calcular score** — ver regras de dedução abaixo.
8. **Verificar anti-patterns**: cruzar findings com o índice de knowledge; registrar `anti_pattern_id` nos findings quando houver correspondência.
9. **Produzir output JSON** conforme `.lla/manifests/schemas/review-output.schema.json`.
10. **Salvar review**: `.lla/sdd/current/review_{iteration}.md` usando template `.lla/templates/review-template.md`.
11. **Sinalizar aprendizado reutilizável**: preencher `anti_patterns_to_register` no output quando detectar padrão recorrente sem entrada no knowledge.

## Score Deduction Rules

| Evento | Efeito no score |
|--------|----------------|
| Base | 100 |
| Cada P0 encontrado | `score = min(score, 50)` (cap em 50) |
| Cada P1 encontrado | `score -= 10` (floor 60) |
| Cada P2 encontrado | sem dedução |
| Resultado final | `max(0, score)` |

Exemplo: 1 P0 + 2 P1 → `min(100, 50) = 50`, depois `50 - 20 = 30`, mas floor 60 → `60`.

## Severity Classification Rules

| Severidade | Critério |
|------------|----------|
| **P0** | Quebra corretude, contrato de API, segurança, teste essencial, transação crítica ou arquitetura crítica. Qualquer bug funcional visível, vazamento de dados, ou quebra de build. |
| **P1** | Fere claramente manutenção, clareza, aderência a padrão central da stack, ou convenção dominante do projeto. Lógica em camada errada, validação inconsistente, divergência forte do padrão. |
| **P2** | Refino opcional e localizado. Melhoria de legibilidade, nome, organização menor que não afeta corretude nem manutenção significativa. |

## Threshold de aprovação

- **APPROVED**: score ≥ 95 e zero P0 e zero P1.
- **REJECTED**: score < 95 ou qualquer P0/P1 presente.

## Determinismo

- Score e severidade baseados APENAS em critérios objetivos listados nas skills carregadas.
- Não deduzir por preferência estilística sem critério explícito na skill.
- Cada finding deve referenciar o critério objetivo violado.
- Dois reviewers com as mesmas skills e o mesmo diff devem produzir o mesmo score.
