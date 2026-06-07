# Decisões

## T1: QA com build real, lint gate e guardrail validators

- **Determinismo por exit code**: qa_status PASS/FAIL baseado exclusivamente em exit codes. Nenhuma heurística ou interpretação de output.
- **Fallback graceful**: ferramentas de lint ausentes resultam em skip com nota, não em FAIL. lint_violations: 0 quando skipado.
- **Escopo restrito ao diff**: build e testes Java executam apenas nos módulos afetados (-pl -am). Guardrails validam apenas arquivos modificados.
- **Timeout via comando `timeout`**: usa o binário `timeout` do Linux com exit code 124 para detectar timeout, mapeado para error_type TIMEOUT.
- **Guardrails com thresholds fixos**: class-size 150 linhas, code-formatting 140 chars, unit-test-naming snake_case. Valores configuráveis no futuro se necessário.
- **Perfil como string simples**: `maven-multi`, `gradle-single`, `npm-angular` etc. Evita schema complexo para o perfil.
- **error_type nullable**: null quando qa_status=PASS, string do enum quando FAIL.

## T2: Review com score determinístico e P0/P1/P2

- **Score determinístico**: base 100, P0 cap em 50, P1 -10 cada com floor 60. Regra garante que qualquer P0 impede aprovação (score ≤ 50) e P1s acumulativos derrubam score até floor 60.
- **Threshold de aprovação**: score ≥ 95 E zero P0/P1. Na prática só aprova quando não há findings bloqueantes ou obrigatórios — score 95+ sem P0/P1 implica no máximo P2s.
- **Floor 60 para P1**: mesmo com muitos P1s, o score não cai abaixo de 60. Isso evita que acumulo de P1s mascare a gravidade de um P0 (que já cap em 50). O P0 sempre domina.
- **anti_pattern_id nos findings**: permite rastreabilidade entre findings e knowledge base, viabilizando evolução incremental do reviewer.
- **anti_patterns_to_register no output**: permite que o reviewer sinalize padrões recorrentes ainda não catalogados, sem precisar chamar knowledge-curator diretamente.
- **Schema JSON com additionalProperties: false**: garante contratos estritos, facilitando validação automatizada futura.
- **Template markdown com tabelas por severidade**: separação P0/P1/P2 em tabelas distintas facilita leitura e ação pelo implementer.

## T3: Loop de retry reviewer↔implementer + orchestrator

- **Max 3 iterações de review**: suficiente para convergência na maioria dos casos. Mais que isso indica problema estrutural.
- **Max 2 QA retries**: build/teste falhando 2x seguidas indica problema mais profundo que precisa de intervenção humana.
- **Score delta rule (+5)**: se score não subir pelo menos 5 em 2 iterações consecutivas, o loop está estagnado e deve escalar.
- **Escalada para humano**: documentar estado atual, score, ações pendentes e solicitar intervenção explícita.
- **Implementer lê ações obrigatórias**: garante que correções são focadas e não expandem escopo.

## T4: Knowledge base pré-seeded com anti-patterns

- **10 anti-patterns iniciais**: AP-1 a AP-10 cobrindo Spring (4), Quarkus (3), Angular (3) e java-generic (1 cross-stack).
- **Freq ≥ 3 = hard constraint**: anti-patterns com frequência ≥ 3 são tratados como P0 pelo reviewer. Isso reflete que padrões recorrentes são mais críticos.
- **Write-back segmentado**: reviewer registra tanto no índice mestre (shared/anti-patterns.md) quanto no segmento da stack (reviewer/anti-patterns-{stack}.md).
- **IDs sequenciais AP-{N}**: formato simples e rastreável.

## T5: Guardrails com applyTo

- **5 guardrails genéricos**: class-size (P1), code-formatting (P1), unit-test-naming (P1), context-economy (P1), minimal-change (P0).
- **applyTo por papel**: cada guardrail indica quais agentes devem carregá-lo. QA e reviewer carregam condicionalmente por stack.
- **minimal-change como P0**: não expandir escopo é a regra mais importante do implementer. Violação é bloqueante.
- **Guardrails em .lla/guardrails/**: separados de .opencode/ para manter harness config distinto de agent config.

## T6: Style policy canônico

- **Fonte única de verdade**: .lla/context/style-policy.md é a referência canônica para thresholds numéricos.
- **Precedência do projeto-alvo**: se o projeto-alvo tem checkstyle.xml, prettier ou .editorconfig, seus thresholds prevalecem.
- **Thresholds: 140 chars, 150 linhas, 30 métodos, CC 5, 3 args**: alinhados com guardrails e QA skill.

## T7: Artifact guardrails + precedência de instruções

- **Hierarquia de precedência**: desenvolvedor > Ravend > .lla/context/ > repo-alvo. Evita conflito entre instruções do harness e do projeto.
- **artifact_verified no handoff**: campo booleano que confirma persistência antes de handoff. Sem ele, o handoff não deve ocorrer.

## T9: Execution prompts por task

- **Formato XML no task-template**: seções com task_context, objective, inspect_first, interface_to_implement, edge_cases, tests_to_implement, constraints.
- **8 campos novos no task-scope.schema.json**: inspect_first, interface_to_implement, edge_cases, tests_to_implement, constraints, complexity, depends_on, parallelizable.
- **Implementer lê execution prompt**: garante contexto mínimo suficiente e foco no objetivo.

## T10: Prompt caching via system prompts estáticos

- **3 system prompts**: implementer.system.md, reviewer.system.md, qa.system.md em .opencode/agents/context/.
- **Conteúdo estável apenas**: identidade, skills base, guardrails, regras de determinismo, thresholds. Nada variável (task_id, diff, iteração).
- **Header de versão**: permite rastrear mudanças e invalidar cache quando necessário.

## T11: Session template com métricas

- **Template markdown**: feature_id, repo, branch, score_final, iterações_qa, iterações_review, skills, guardrails, artefatos, resumo, pendências.
- **Formato legível**: tabelas markdown para facilitar leitura humana.
