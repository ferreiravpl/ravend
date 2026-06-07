# Tasks — Incremento do Ravend

## T1 — QA com build real, lint gate e guardrail validators (P0)
- **Stack:** ravend (harness)
- **Depende de:** —
- **Paralela com:** T2, T3
- **Arquivos em escopo:**
  - `.opencode/agents/qa.md` (reescrever)
  - `.opencode/skills/sdd-qa-verification/SKILL.md` (reescrever)
  - `.lla/manifests/schemas/qa-output.schema.json` (criar)
- **Fora de escopo:** guardrails (T5), style-policy (T6), knowledge (T4)
- **Critérios de aceite:**
  1. QA agent tem workflow detalhado: profile detect → stack detect → build → testes → lint → guardrails → output
  2. QA executa build real (mvn compile / npm build) com timeout
  3. QA executa testes com escopo restrito aos módulos afetados
  4. QA executa lint gate (checkstyle do projeto-alvo + ESLint se disponível)
  5. QA produz output JSON conforme qa-output.schema.json
  6. PASS/FAIL baseado em exit codes, nunca em julgamento subjetivo
  7. Fallback graceful se ferramenta indisponível (skip com nota)
- **Validação:** ler qa.md e SKILL.md e verificar que workflow é executável; validar schema JSON

## T2 — Review com score determinístico e P0/P1/P2 (P0)
- **Stack:** ravend (harness)
- **Depende de:** —
- **Paralela com:** T1, T3
- **Arquivos em escopo:**
  - `.opencode/agents/reviewer.md` (reescrever)
  - `.opencode/skills/sdd-review-loop/SKILL.md` (reescrever)
  - `.lla/manifests/schemas/review-output.schema.json` (criar)
  - `.lla/templates/review-template.md` (criar)
- **Fora de escopo:** loop de retry (T3), knowledge (T4), guardrails (T5)
- **Critérios de aceite:**
  1. Reviewer produz score 0-100 com regras de dedução determinísticas
  2. Findings classificados em P0/P1/P2 com ações obrigatórias quando reprovado
  3. Aprovação: score ≥ 95 e sem P0/P1
  4. Reviewer carrega skills condicionalmente por stack
  5. Reviewer produz output JSON conforme review-output.schema.json
  6. Reviewer verifica anti-patterns e registra anti_pattern_id nos findings
  7. Template de review com score, status, P0/P1/P2 e ações obrigatórias
- **Validação:** ler reviewer.md e SKILL.md e verificar regras de score; validar schema JSON

## T3 — Loop de retry reviewer↔implementer + orchestrator (P0)
- **Stack:** ravend (harness)
- **Depende de:** T1, T2 (precisa que QA e reviewer tenham output estruturado)
- **Paralela com:** nenhuma (depende de T1 e T2)
- **Arquivos em escopo:**
  - `.opencode/agents/orchestrator.md` (atualizar)
  - `.opencode/agents/implementer.md` (atualizar — ler ações obrigatórias do review)
  - `AGENTS.md` (atualizar — regras de loop e escalada)
- **Fora de escopo:** execution prompts (T9), session template (T12)
- **Critérios de aceite:**
  1. Orchestrator orquestra loop: implementer → QA → reviewer → (correção → QA → reviewer) → aceite
  2. Max 3 iterações de review, max 2 retries de QA
  3. Score delta rule: se score não subir ≥ 5 em 2 iterações consecutivas, escalada
  4. Escalada para humano se max iterações atingido
  5. Implementer lê ações obrigatórias do review e corrige
  6. AGENTS.md documenta regras de loop e escalada
- **Validação:** ler orchestrator.md e AGENTS.md e verificar regras de loop

## T4 — Knowledge base pré-seeded com anti-patterns (P1)
- **Stack:** ravend (harness)
- **Depende de:** —
- **Paralela com:** T1, T2, T5, T6, T7, T8
- **Arquivos em escopo:**
  - `.lla/knowledge/shared/anti-patterns.md` (criar)
  - `.lla/knowledge/reviewer/anti-patterns-spring.md` (criar)
  - `.lla/knowledge/reviewer/anti-patterns-quarkus.md` (criar)
  - `.lla/knowledge/reviewer/anti-patterns-angular.md` (criar)
  - `.lla/manifests/knowledge-index.json` (popular)
  - `.opencode/skills/sdd-knowledge-capture/SKILL.md` (atualizar — write-back segmentado, freq ≥ 3)
  - `.opencode/agents/knowledge-curator.md` (atualizar — write-back segmentado, freq ≥ 3)
- **Fora de escopo:** anti-patterns específicos de projeto (gumga)
- **Critérios de aceite:**
  1. Índice mestre com AP-1 a AP-5+ (pattern, stack, severidade, correção, frequência)
  2. Segmentos por stack com anti-patterns relevantes
  3. Regra: freq ≥ 3 = hard constraint (equivalente a P0)
  4. knowledge-index.json populado com entradas para cada anti-pattern
  5. knowledge-capture skill inclui write-back segmentado e freq ≥ 3
- **Validação:** ler anti-patterns.md e verificar formato; validar knowledge-index.json

## T5 — Guardrails com applyTo (P1)
- **Stack:** ravend (harness)
- **Depende de:** —
- **Paralela com:** T1, T2, T4, T6, T7, T8
- **Arquivos em escopo:**
  - `.lla/guardrails/class-size.guardrail.md` (criar)
  - `.lla/guardrails/code-formatting.guardrail.md` (criar)
  - `.lla/guardrails/unit-test-naming.guardrail.md` (criar)
  - `.lla/guardrails/context-economy.guardrail.md` (criar)
  - `.lla/guardrails/minimal-change.guardrail.md` (criar)
- **Fora de escopo:** guardrails específicos de projeto (mercadolivre, dto-builder, required-args)
- **Critérios de aceite:**
  1. Cada guardrail tem: nome, applyTo, severidade, regra, correção
  2. class-size: max 150 linhas, P1
  3. code-formatting: max 140 chars, P1
  4. unit-test-naming: snake_case, P1
  5. context-economy: não carregar >3 skills sem necessidade, P1
  6. minimal-change: não expandir escopo, P0
- **Validação:** ler cada guardrail e verificar formato e conteúdo

## T6 — Style policy canônico (P1)
- **Stack:** ravend (harness)
- **Depende de:** —
- **Paralela com:** T1, T2, T4, T5, T7, T8
- **Arquivos em escopo:**
  - `.lla/context/style-policy.md` (criar)
- **Fora de escopo:** checkstyle.xml empacotado
- **Critérios de aceite:**
  1. Fonte única de verdade para thresholds numéricos
  2. Linha: 140 chars, Classe: 150 linhas, Método: 30 linhas, Complexidade: 5, Argumentos: 3
  3. Regra de precedência: projeto-alvo com checkstyle/prettier prevalece
  4. Referenciado pelos guardrails e pela skill de QA
- **Validação:** ler style-policy.md e verificar thresholds

## T7 — Artifact guardrails + precedência de instruções (P1)
- **Stack:** ravend (harness)
- **Depende de:** —
- **Paralela com:** T1, T2, T4, T5, T6, T8
- **Arquivos em escopo:**
  - `AGENTS.md` (atualizar — precedência + artifact guardrails)
  - `.lla/manifests/schemas/agent-handoff.schema.json` (atualizar — artifact_verified)
- **Fora de escopo:** loop de retry (T3)
- **Critérios de aceite:**
  1. AGENTS.md tem seção de precedência: desenvolvedor > Ravend > .lla/context/ > repo-alvo
  2. AGENTS.md tem regra de artifact guardrails: confirmar persistência antes de handoff
  3. agent-handoff.schema.json tem campo artifact_verified
- **Validação:** ler AGENTS.md e verificar seções novas; validar schema

## T8 — Schemas de output (P2)
- **Stack:** ravend (harness)
- **Depende de:** T1, T2 (schemas referenciam outputs de QA e reviewer)
- **Paralela com:** T9, T10, T11, T12
- **Arquivos em escopo:**
  - `.lla/manifests/schemas/review-output.schema.json` (criar — se já criou em T2, apenas verificar)
  - `.lla/manifests/schemas/qa-output.schema.json` (criar — se já criou em T1, apenas verificar)
- **Fora de escopo:** plan-output schema (task-scope já cobre)
- **Critérios de aceite:**
  1. review-output.schema.json valida output do reviewer
  2. qa-output.schema.json valida output do QA
  3. Schemas são referenciados nas skills e nos agentes
- **Validação:** validar schemas com exemplos de output

## T9 — Execution prompts por task (P2)
- **Stack:** ravend (harness)
- **Depende de:** —
- **Paralela com:** T8, T10, T11, T12
- **Arquivos em escopo:**
  - `.lla/templates/task-template.md` (atualizar — seção de execution prompt)
  - `.lla/manifests/schemas/task-scope.schema.json` (atualizar — campos novos)
  - `.opencode/skills/sdd-task-decomposition/SKILL.md` (atualizar — gerar execution prompts)
  - `.opencode/skills/sdd-implementation/SKILL.md` (atualizar — ler execution prompt)
- **Fora de escopo:** alterar task-decomposer.md agent (mudança mínima)
- **Critérios de aceite:**
  1. task-template.md tem seção de execution prompt em XML
  2. task-scope.schema.json tem campos: inspect_first, interface_to_implement, edge_cases, tests_to_implement, constraints, complexity, depends_on, parallelizable
  3. sdd-task-decomposition gera execution prompts
  4. sdd-implementation lê e segue execution prompt
- **Validação:** ler templates e schemas atualizados

## T10 — Prompt caching via system prompts estáticos (P2)
- **Stack:** ravend (harness)
- **Depende de:** T1, T2 (system prompts referenciam identidade de QA e reviewer)
- **Paralela com:** T8, T9, T11, T12
- **Arquivos em escopo:**
  - `.opencode/agents/context/implementer.system.md` (criar)
  - `.opencode/agents/context/reviewer.system.md` (criar)
  - `.opencode/agents/context/qa.system.md` (criar)
- **Fora de escopo:** system prompts para outros agentes (intake, spec-writer, etc.)
- **Critérios de aceite:**
  1. Cada system.md tem conteúdo estável (identidade, skills base, regras, thresholds)
  2. Conteúdo variável (task_id, diff, iteração) NÃO está no system.md
  3. Header de versão para rastrear mudanças
- **Validação:** ler system.md e verificar que não há conteúdo variável

## T11 — Session template com métricas (P2)
- **Stack:** ravend (harness)
- **Depende de:** —
- **Paralela com:** T8, T9, T10, T12
- **Arquivos em escopo:**
  - `.lla/templates/session-template.md` (criar)
- **Fora de escopo:** automação de geração de session.md (command sdd-accept)
- **Critérios de aceite:**
  1. Template com: feature_id, repo, branch, score_final, iterações_qa, iterações_review, skills, guardrails, artefatos, resumo, pendências
  2. Formato markdown legível
- **Validação:** ler template e verificar campos

## T12 — Atualizar progress.md e decisions.md (finalização)
- **Stack:** ravend (harness)
- **Depende de:** T1-T11
- **Paralela com:** nenhuma
- **Arquivos em escopo:**
  - `.lla/sdd/current/progress.md` (atualizar)
  - `.lla/sdd/current/decisions.md` (atualizar)
- **Critérios de aceite:**
  1. progress.md refleta estado de todas as tasks
  2. decisions.md registre decisões tomadas durante implementação
