# Guardrail — Code Formatting

## Nome
code-formatting

## applyTo
implementer, qa

## Severidade
P1

## Regra
Nenhuma linha deve exceder 140 caracteres.

## Verificação
```bash
find . -name "*.java" -o -name "*.ts" -o -name "*.html" | while read f; do
  awk 'length > 140 { print "VIOLATION: " FILENAME ":" NR ": " length " chars" }' "$f"
done
```

## Correção
Quebrar linha em ponto natural (após vírgula, antes de operador, após parêntese). Não truncar strings.

## Exceções
- URLs ou imports longos que não suportam quebra
- Linhas geradas automaticamente

## Precedência
Se o projeto-alvo tem checkstyle.xml, prettier ou .editorconfig com threshold diferente, o do projeto-alvo prevalece.

## Referência
`.lla/context/style-policy.md` — threshold de linha
