# Tech Spec — Incremento do Ravend via Análise Comparativa com ai-workflow

## Mapeamento de escopo

### Arquivos a criar (novos)
| Arquivo | Propósito |
|---|---|
| `.lla/manifests/schemas/review-output.schema.json` | Schema de output do reviewer (score, findings, anti_patterns_to_register) |
| `.lla/manifests/schemas/qa-output.schema.json` | Schema de output do QA (status, stacks, modules, tests, error_type, lint_violations) |
| `.lla/guardrails/class-size.guardrail.md` | Max 150 linhas por classe (P1) |
| `.lla/guardrails/code-formatting.guardrail.md` | Max 140 chars por linha (P1) |
| `.lla/guardrails/unit-test-naming.guardrail.md` | snake_case em testes (P1) |
| `.lla/guardrails/context-economy.guardrail.md` | Não carregar skill/contexto sem necessidade (P1) |
| `.lla/guardrails/minimal-change.guardrail.md` | Não expandir escopo da task (P0) |
| `.lla/knowledge/shared/anti-patterns.md` | Índice mestre de anti-patterns cross-stack |
| `.lla/knowledge/reviewer/anti-patterns-spring.md` | Anti-patterns Spring (segmento) |
| `.lla/knowledge/reviewer/anti-patterns-quarkus.md` | Anti-patterns Quarkus (segmento) |
| `.lla/knowledge/reviewer/anti-patterns-angular.md` | Anti-patterns Angular (segmento) |
| `.lla/context/style-policy.md` | Fonte canônica de thresholds numéricos |
| `.lla/templates/session-template.md` | Template de sessão com métricas |
| `.lla/templates/review-template.md` | Template de review com score e P0/P1/P2 |
| `.opencode/agents/context/implementer.system.md` | System prompt estático do implementer |
| `.opencode/agents/context/reviewer.system.md` | System prompt estático do reviewer |
| `.opencode/agents/context/qa.system.md` | System prompt estático do QA |

### Arquivos a modificar (existentes)
| Arquivo | Mudança |
|---|---|
| `AGENTS.md` | Adicionar seção de precedência de instruções + artifact guardrails + regra de loop de retry |
| `.opencode/agents/qa.md` | Reescrever com workflow detalhado, permissões de bash expandidas, determinismo |
| `.opencode/agents/reviewer.md` | Adicionar score, P0/P1/P2, output JSON, max iterações, stack detection |
| `.opencode/agents/implementer.md` | Adicionar leitura de ações obrigatórias do review, leitura de execution prompt, leitura de guardrails |
| `.opencode/agents/orchestrator.md` | Adicionar orquestração do loop QA→review→correção, escalada para humano |
| `.opencode/agents/knowledge-curator.md` | Adicionar write-back segmentado, freq ≥ 3 = hard constraint |
| `.opencode/skills/sdd-qa-verification/SKILL.md` | Reescrever com workflow completo (profile detect → stack detect → build → test → lint → guardrails → output) |
| `.opencode/skills/sdd-review-loop/SKILL.md` | Reescrever com score determinístico, P0/P1/P2, max iterações, output JSON, anti-pattern detection |
| `.opencode/skills/sdd-implementation/SKILL.md` | Adicionar leitura de execution prompt, guardrails e knowledge antes de implementar |
| `.opencode/skills/sdd-task-decomposition/SKILL.md` | Adicionar geração de execution prompts por task |
| `.opencode/skills/sdd-knowledge-capture/SKILL.md` | Adicionar write-back segmentado, freq ≥ 3, anti_pattern_id |
| `.lla/manifests/task-scope.schema.json` | Adicionar campos: inspect_first, interface_to_implement, edge_cases, tests_to_implement, constraints, complexity, depends_on, parallelizable |
| `.lla/manifests/agent-handoff.schema.json` | Adicionar campo: artifact_verified |
| `.lla/manifests/knowledge-index.json` | Popular com entradas de anti-patterns |
| `.lla/templates/task-template.md` | Adicionar seção de execution prompt em XML |

## Arquitetura atual

```
.opencode/
├── agents/          9 agentes (orchestrator + 8 subagents)
├── skills/          18 skills (SDD + stack + meta)
└── commands/        10 commands

.lla/
├── context/         6 arquivos (majoridade placeholder)
├── sdd/current/     9 artefatos de estado
├── manifests/       3 schemas + 2 manifests + knowledge-index
├── knowledge/       reviewer/ implementer/ shared/ (vazios)
└── templates/       4 templates
```

**Gaps:**
- QA: instrutivo, sem build real, sem lint, sem guardrails
- Review: qualitativo, sem score, sem retry, sem output JSON
- Knowledge: vazio, sem anti-patterns, sem frequência
- Guardrails: inexistentes
- System prompts: misturados nos agent.md
- Execution prompts: inexistentes
- Session template: inexistente
- Precedência de instruções: não definida

## Solução proposta

### P0 — Gates de qualidade

#### 1. QA com build real
O agente QA passa de instrutivo para executável. Workflow:
1. Detectar perfil do projeto (Maven/Gradle, npm/pnpm/yarn, multi-module vs single)
2. Detectar stacks do diff (ou receber via input)
3. Build Java: `mvn compile -pl $MODULES -am -DskipTests` com timeout 300s
4. Testes Java: `mvn test -pl $MODULES -Dtest=$CLASSES` com timeout 180s, escopo restrito
5. Build Angular: `npm run build` com timeout 300s
6. Testes Angular: `npx ng test --watch=false` com timeout 180s
7. Lint gate: checkstyle (precedência do projeto-alvo) + ESLint (se disponível)
8. Guardrail validators: class-size, code-formatting, unit-test-naming
9. Output JSON conforme qa-output.schema.json
10. Salvar qa-report.md

Regra de determinismo: PASS/FAIL baseado EXCLUSIVAMENTE em exit codes. Nunca julgamento subjetivo.

#### 2. Review com score determinístico
O agente reviewer passa de qualitativo para quantificável. Workflow:
1. Carregar skills: review baseline (sempre) + stack-specific (condicional)
2. Carregar knowledge: anti-patterns.md (índice mestre) + segmento da stack
3. Carregar guardrails condicionais por stack
4. Ler diff e decisions.md (se existir)
5. Analisar diff contra TODOS os critérios das skills carregadas
6. Classificar findings: P0 (bloqueante), P1 (deve corrigir), P2 (opcional)
7. Calcular score: base 100, P0→min 50, P1→-10 cada (floor 60), P2→sem dedução
8. Verificar anti-patterns: registrar anti_pattern_id nos findings
9. Produzir output JSON conforme review-output.schema.json
10. Salvar review_{iteration}.md

Aprovação: score ≥ 95 e sem P0/P1. Reprovação: score < 95 ou P0/P1 presentes com ações obrigatórias.

#### 3. Loop de retry reviewer↔implementer
O orchestrator orquestra o loop:
1. Após implementação → QA (max 2 retries)
2. QA PASS → reviewer (max 3 iterações)
3. Reviewer REPROVED → implementer corrige ações obrigatórias → QA → reviewer
4. Se score não subir ≥ 5 pontos em 2 iterações consecutivas → escalada para humano
5. Se max iterações atingido → escalada para humano
6. Reviewer APPROVED → aceite

### P1 — Defesa em camadas

#### 4. Knowledge pré-seeded
Popular `.lla/knowledge/` com anti-patterns do ai-workflow adaptados:
- `shared/anti-patterns.md`: índice mestre (AP-1 a AP-5+)
- `reviewer/anti-patterns-spring.md`: field injection, findAll sem Pageable, N+1, catch genérico
- `reviewer/anti-patterns-quarkus.md`: @Singleton sem CDI proxy, blocking no event loop, persist sem @Transactional
- `reviewer/anti-patterns-angular.md`: subscribe sem cleanup, uso de any, DOM direto

Regra: freq ≥ 3 = hard constraint (equivalente a P0). Write-back: reviewer registra tanto no índice quanto no segmento.

#### 5. Guardrails com applyTo
Criar `.lla/guardrails/` com guardrails genéricos:
- `class-size.guardrail.md` — max 150 linhas, P1, applyTo: implementer, qa, reviewer
- `code-formatting.guardrail.md` — max 140 chars, P1, applyTo: implementer, qa
- `unit-test-naming.guardrail.md` — snake_case, P1, applyTo: implementer, qa
- `context-economy.guardrail.md` — não carregar >3 skills sem necessidade, P1, applyTo: orchestrator
- `minimal-change.guardrail.md` — não expandir escopo, P0, applyTo: implementer

Carregamento condicional: QA e reviewer carregam guardrails conforme stack detectada.

#### 6. Style policy canônico
Criar `.lla/context/style-policy.md` com thresholds:
- Linha: 140 chars (Java e TS)
- Classe: 150 linhas (excl. package/import/blank)
- Método: 30 linhas
- Complexidade ciclomática: 5
- Argumentos: 3

Precedência: projeto-alvo com checkstyle/prettier/editorconfig prevalece.

#### 7. Artifact guardrails
Regra global: todo agente confirma persistência do artefato antes de handoff.
Campo `artifact_verified: boolean` no agent-handoff.json.

#### 8. Precedência de instruções
Hierarquia no AGENTS.md:
1. Instruções explícitas do desenvolvedor na conversa
2. Regras do Ravend (AGENTS.md, skills, guardrails)
3. Contexto do projeto carregado via .lla/context/ do Ravend
4. Instruções do repositório-alvo (para entendimento, não para substituir regras)

### P2 — Estrutura e observabilidade

#### 9. Execution prompts por task
Template XML no task-template.md com seções: task_context, objective, inspect_first, interface_to_implement, edge_cases, tests_to_implement, constraints.

Campos novos no task-scope.schema.json: inspect_first, interface_to_implement, edge_cases, tests_to_implement, constraints, complexity, depends_on, parallelizable.

#### 10. Schemas de output
- `review-output.schema.json`: review_status, score, findings[], summary, anti_patterns_to_register[]
- `qa-output.schema.json`: qa_status, stacks_validated, modules, test_classes, tests_passed, tests_failed, detail, error_type, lint_violations

#### 11. Prompt caching via system.md
Criar `.opencode/agents/context/` com system prompts estáveis:
- `implementer.system.md`: identidade, skills base, guardrails, princípios
- `reviewer.system.md`: identidade, skills base, regras de determinismo, thresholds
- `qa.system.md`: identidade, regras de determinismo, workflow resumido

Regra: conteúdo estável no system.md, conteúdo variável no handoff/prompt dinâmico.

#### 12. Session template
Criar `.lla/templates/session-template.md` com: feature_id, repo, branch, score_final, iterações_qa, iterações_review, skills_carregadas, guardrails_ativados, artefatos_gerados, resumo, arquivos_modificados, pendências.

## Interfaces e contratos

### review-output.schema.json
```json
{
  "review_status": "APPROVED|REJECTED",
  "score": 0-100,
  "findings": [
    {
      "severity": "P0|P1|P2",
      "file": "string",
      "line": "int|null",
      "description": "string",
      "action": "string",
      "anti_pattern_id": "string|null"
    }
  ],
  "summary": "string",
  "anti_patterns_to_register": [
    {
      "pattern": "string",
      "stack": "spring|quarkus|angular|java-generic",
      "severity": "P0|P1|P2",
      "correction": "string",
      "example": "string"
    }
  ],
  "iteration": "int",
  "score_delta": "int"
}
```

### qa-output.schema.json
```json
{
  "qa_status": "PASS|FAIL",
  "profile": "string",
  "stacks_validated": ["string"],
  "modules": "string",
  "test_classes": "string",
  "tests_passed": "int",
  "tests_failed": "int",
  "detail": "string",
  "error_type": "BUILD_ERROR|TEST_FAILURE|LINT_FAILURE|TIMEOUT|null",
  "lint_violations": "int",
  "guardrail_violations": "int"
}
```

### task-scope.schema.json (campos novos)
```json
{
  "inspect_first": ["string"],
  "interface_to_implement": "string",
  "edge_cases": ["string"],
  "tests_to_implement": ["string"],
  "constraints": ["string"],
  "complexity": "LOW|MEDIUM|HIGH",
  "depends_on": ["string"],
  "parallelizable": "boolean"
}
```

## Modelo de dados / migrações
Nenhuma migração de banco. Todos os dados são arquivos markdown/JSON versionados no repo.

## Riscos e trade-offs

| Risco | Probabilidade | Impacto | Mitigação |
|---|---|---|---|
| QA com build real depende de ferramentas no ambiente | Média | Alto | QA profile auto-detect + fallback graceful (skip com nota se ferramenta indisponível) |
| Score determinístico rígido demais | Baixa | Médio | Campo score_override_reason + precedência do desenvolvedor |
| Guardrails conflitam com projeto-alvo | Média | Baixo | Precedência: projeto-alvo > Ravend default |
| System prompts dessincronizados dos agent.md | Baixa | Médio | Versionar system.md com header de versão |
| Loop de retry consome tokens demais | Média | Médio | Score delta rule (parar se não subir ≥ 5) + max 3 iterações |
| Knowledge pré-seeded é opinativo | Baixa | Baixo | Marcar como seed — sistema evolui organicamente |

## Estratégia de testes
- Teste manual: executar `/sdd-start` com demanda de teste e verificar que QA roda build, review produz score, loop converge
- Teste de schema: validar que outputs JSON conformam aos schemas
- Teste de guardrails: criar arquivo Java > 150 linhas e verificar que QA detecta violação
- Teste de knowledge: verificar que anti-patterns são carregados pelo reviewer e referenciados nos findings
- Teste de session: verificar que session.md é gerado ao final do fluxo

## Rollout / rollback
- Incremental: implementar P0 primeiro, validar, depois P1, depois P2
- Rollback: cada incremento é independente — reverter um arquivo não afeta os outros
- Backup: `.lla/backups/` já existe — versionar arquivos antes de modificar
