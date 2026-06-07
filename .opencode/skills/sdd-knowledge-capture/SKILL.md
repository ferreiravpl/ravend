---
name: sdd-knowledge-capture
description: Converte findings recorrentes em conhecimento pequeno, indexado e reutilizável com write-back segmentado.
compatibility: opencode
---
## Objetivo
Capturar aprendizado sem inflar contexto futuro. Write-back segmentado por stack.

## Quando usar
Use quando houver finding recorrente ou lição reaproveitável, especialmente quando:
- O reviewer detectar anti-pattern sem entrada no knowledge
- O implementer encontrar padrão recorrente em correções
- O QA identificar violação de guardrail frequente

## Procedimento

1. **Condense a lição** em orientação prática (máx. 5 linhas por entrada).
2. **Escolha a categoria correta**: reviewer, implementer ou shared.
3. **Identifique a stack**: spring, quarkus, angular ou java-generic.
4. **Write-back segmentado**:
   - Adicione a entrada no **índice mestre** (`.lla/knowledge/shared/anti-patterns.md`)
   - Adicione a entrada no **segmento da stack** (`.lla/knowledge/reviewer/anti-patterns-{stack}.md`)
   - Se a stack não tiver segmento, crie o arquivo
5. **Atualize o índice** `.lla/manifests/knowledge-index.json` com nova entrada.
6. **Atribua ID**: use formato `AP-{N}` sequencial (consulte último ID no índice).
7. **Registre frequência**: inicie com `freq: 1`. Se já existir entrada similar, incremente `freq`.

## Regra de frequência

- `freq ≥ 3` → **hard constraint** (equivalente a P0 na review)
- O reviewer deve tratar anti-patterns com freq ≥ 3 como bloqueantes
- O implementer deve evitar anti-patterns com freq ≥ 3 como regra obrigatória

## Formato de entrada no índice mestre

```markdown
## AP-{N} — {Título}

| Campo | Valor |
|-------|-------|
| **Padrão** | descrição do padrão |
| **Stack** | spring/quarkus/angular/java-generic |
| **Severidade** | P0/P1/P2 |
| **Correção** | o que fazer em vez disso |
| **Frequência** | N |
| **Exemplo** | código violador → código correto |
```

## Formato de entrada no segmento

```markdown
## AP-{N} — {Título}
- **Padrão:** descrição curta
- **Severidade:** P0/P1/P2
- **Correção:** o que fazer
- **Freq:** N (hard constraint se ≥ 3)
```

## Formato de entrada no knowledge-index.json

```json
{
  "id": "AP-{N}",
  "file": "shared/anti-patterns.md",
  "role": ["reviewer", "implementer"],
  "framework": ["{stack}"],
  "layer": ["{camadas afetadas}"],
  "issue_type": ["{tipo do problema}"],
  "pattern": "descrição curta",
  "severity": "P0/P1/P2",
  "freq": N
}
```
