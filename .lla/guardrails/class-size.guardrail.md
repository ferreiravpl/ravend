# Guardrail — Class Size

## Nome
class-size

## applyTo
implementer, qa, reviewer

## Severidade
P1

## Regra
Nenhuma classe deve exceder 150 linhas (excluindo package, imports e linhas em branco).

## Verificação
```bash
find . -name "*.java" -newer .git/MERGE_HEAD | while read f; do
  count=$(grep -v -E '^(package |import |$)' "$f" | wc -l)
  if [ "$count" -gt 150 ]; then
    echo "VIOLATION: $f has $count lines (max 150)"
  fi
done
```

## Correção
Extrair lógica em classe colaboradora, service ou component auxiliar. Não apenas quebrar linhas.

## Exceções
- Classes geradas (mapstruct, querydsl, openapi-generator)
- Configuration classes com muitos `@Bean` (avaliar se pode ser dividida)

## Referência
`.lla/context/style-policy.md` — threshold de classe
