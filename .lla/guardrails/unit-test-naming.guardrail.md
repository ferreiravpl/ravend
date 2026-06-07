# Guardrail — Unit Test Naming

## Nome
unit-test-naming

## applyTo
implementer, qa

## Severidade
P1

## Regra
Nomes de métodos de teste devem seguir `snake_case` no formato: `should_{expected}_when_{condition}`.

Exemplos válidos:
- `should_returnEmptyList_when_noProductsFound`
- `should_throwNotFoundException_when_productDoesNotExist`
- `should_createOrder_when_validInput`

Exemplos inválidos:
- `testReturnEmptyList` (camelCase sem semântica)
- `test1` (sem descrição)
- `shouldReturnEmptyListWhenNoProductsFound` (camelCase)

## Verificação
```bash
find . -path "*/test/*" -name "*.java" | while read f; do
  grep -n "@Test" -A1 "$f" | grep -E "void [a-z]+[A-Z]" && \
    echo "VIOLATION: $f — test method not in snake_case"
done
```

## Correção
Renomear método de teste para `should_{expected}_when_{condition}` em snake_case.

## Exceções
- Projetos com convenção estabelecida diferente (verificar padrão dominante na codebase)
- Testes de integração com naming convencional do framework

## Referência
`.lla/context/style-policy.md` — convenção de nomenclatura
