---
name: qa-e2e-playwright
description: Valida fluxos de UI via navegador real com o MCP Playwright. Use quando o diff contiver UI/frontend (Angular, componentes HTML/TS) e o QA precisar validar comportamento navegável além de testes unitários.
compatibility: opencode
---
## Objetivo

Validar fluxos de interface com navegador real via MCP Playwright, como gate E2E opcional do pipeline de QA. É o complemento do `sdd-qa-verification` quando existe UI no diff.

## Quando usar

Use APENAS quando:
- O diff contém frontend (`.ts`, `.html`, `.css` em projeto Angular, ou qualquer UI navegável)
- Build e testes unitários já passaram no `sdd-qa-verification`
- O MCP `playwright` está disponível no harness

NÃO use para mudanças backend-only. E2E é opcional — nunca bloqueia por indisponibilidade do browser.

## Procedimento

1. **Detectar alvo**: identifique a URL base da aplicação (`.lla/context/stack.md`, `angular.json` port, `application.properties`/`application.yml` server.port, ou pergunte ao orchestrator).
2. **Iniciar a aplicação** (se não estiver rodando):
   - Angular dev server: `timeout 120 npm run start --prefix <diretório>` ou `ng serve`
   - Backend: `timeout 120 mvn spring-boot:run -pl <modulo>` / `./mvnw quarkus:dev`
   - Aguarde readiness (poll na URL até responder).
3. **Navegar e inspecionar**: use o MCP playwright para abrir a URL e inspecionar o estado (snapshot acessível/árvore DOM).
4. **Exercitar o fluxo da task**: interaja com os elementos relevantes — preencha campos, clique, submeta. Cubra os casos de sucesso E o principal caminho de erro da task.
5. **Assertar comportamento**: confirme no snapshot que o estado pós-interação corresponde ao esperado (mensagem, navegação, conteúdo renderizado).
6. **Capturar evidência**: salve screenshot da evidência em `.lla/sdd/current/{task_id}/e2e-{fluxo}.png`.
7. **Registrar resultado**: anote o resultado no `qa-report.md` como step `e2e-playwright` (PASS/FAIL/SKIP) com 1-2 frases do que foi validado.

## Regras

- E2E valida comportamento visível — não substitui testes unitários nem lint.
- Se o browser não iniciar ou o MCP falhar após 1 tentativa, marque `e2e-playwright: SKIP` com nota no `detail` — nunca faça o QA inteiro falhar por isso.
- Não automatize fluxos fora do escopo da task.
- No output JSON do QA (`qa-output.schema.json`), reflita E2E no campo `detail`; o schema não exige campo próprio.

## Fallback

Sem frontend no diff → SKIP sem executar. Sem MCP disponível → SKIP com nota. Aplicação não inicia → FAIL apenas se a task for UI e a aplicação era esperada; caso contrário SKIP com nota.