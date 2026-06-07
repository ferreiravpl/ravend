# Intake — Incremento do Ravend via Análise Comparativa com ai-workflow

## Objetivo
Incrementar o harness do Ravend com as melhores técnicas identificadas no ai-workflow (GitHub Copilot CLI pipeline), priorizando os gaps críticos: QA sem build real, review sem score numérico, ausência de loop de retry, knowledge base vazia, falta de guardrails e ausência de prompt caching.

## Origem
Análise comparativa 100% de ambos os workflows, documentada em `/home/feven/Desktop/ravend-increment-plan.md`.

## Restrições
- Preservar os princípios do Ravend: minimalismo de contexto, menor caminho seguro, simplicidade
- Não transcrever elementos específicos do projeto gumga-anymarket (guardrails de ML, DTO builder, required-args-constructor)
- Não transcrever skills de Azure DevOps / GitLab / commit-and-open-mr
- Não empacotar checkstyle.xml — usar o do projeto-alvo
- Manter separação estático/dinâmico para prompt caching
- Cada incremento deve ser independente e incremental

## Fatos
1. Ravend tem 9 agentes, 18 skills, 10 commands, 3 schemas — estrutura sólida mas com gaps operacionais
2. ai-workflow tem review com score 0-100 determinístico, QA com build real + lint gate, loop de retry (max 3 review, max 2 QA), knowledge pré-seeded com anti-patterns, 8 guardrails com applyTo, 5 system prompts cacheáveis, execution prompts por task em XML, session template com métricas
3. Ravend é superior em: minimalismo, auto-otimização, fast path, contexto seletivo, stack-routing centralizado, compaction nativa, resume de fluxo, delegação consciente
4. O plano de incremento define 12 incrementos + 4 sugestões extras, priorizados P0→P3
5. O operador solicitou atenção especial a: loop de review por pontuação reviewer↔implementer, QA com build, knowledge base, prompt caching

## Hipóteses
1. Score determinístico no review melhora convergência e rastreabilidade sem sacrificar qualidade
2. QA com build real é viável no OpenCode via permissões de bash
3. Prompt caching via system.md separados funciona com o runtime do OpenCode
4. Guardrails genéricos (class-size, code-formatting, unit-test-naming) aplicam à maioria dos projetos Java/Angular
5. Execution prompts em XML são mais efetivos que instruções livres para o implementer

## Dúvidas
1. O OpenCode suporta prompt caching de prefixo estável de forma transparente, ou precisa de configuração explícita?
2. O operador quer implementar todos os incrementos (P0+P1+P2) ou apenas P0 nesta iteração?
3. Guardrails de DTO builder e required-args-constructor devem ficar como exemplos comentados ou nem isso?

## Sinais de aceite
- QA executa build real (mvn/npm), testes com escopo restrito e lint gate
- Review produz score 0-100 com dedução determinística e P0/P1/P2
- Loop de retry reviewer↔implementer com max 3 iterações e escalada
- Knowledge base pré-seeded com anti-patterns e frequência
- Guardrails com applyTo carregados condicionalmente por stack
- Style policy como fonte canônica de thresholds
- Schemas de output para QA e reviewer
- Session template com métricas
- Artifact guardrails (verificação de persistência)
- Regra de precedência de instruções no AGENTS.md
