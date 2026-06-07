# Style Policy — Fonte Canônica de Thresholds

Este arquivo é a fonte única de verdade para thresholds numéricos de estilo de código no Ravend.

## Precedência

1. **Projeto-alvo** com checkstyle.xml, prettier, .editorconfig ou biome.json → prevalece
2. **Ravend default** (este arquivo) → usado quando o projeto-alvo não define

## Thresholds

| Métrica | Java | TypeScript/Angular |
|---------|------|---------------------|
| Linha (chars) | 140 | 140 |
| Classe (linhas) | 150 | 150 |
| Método (linhas) | 30 | 30 |
| Complexidade ciclomática | 5 | 5 |
| Argumentos (método) | 3 | 3 |

## Contagem de linhas de classe

Excluir do count:
- Declaração de package
- Declarações de import
- Linhas em branco

Incluir no count:
- Declaração da classe
- Campos
- Construtores
- Métodos
- Classes internas

## Convenção de nomenclatura de testes

Formato: `should_{expected}_when_{condition}` em snake_case.

Exemplos:
- `should_returnEmptyList_when_noProductsFound`
- `should_throwNotFoundException_when_productDoesNotExist`

## Referências cruzadas

- Guardrails: `.lla/guardrails/class-size.guardrail.md`, `.lla/guardrails/code-formatting.guardrail.md`, `.lla/guardrails/unit-test-naming.guardrail.md`
- QA skill: `.opencode/skills/sdd-qa-verification/SKILL.md`
- Review skill: `.opencode/skills/sdd-review-loop/SKILL.md`
