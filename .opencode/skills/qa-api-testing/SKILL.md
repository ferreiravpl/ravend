---
name: qa-api-testing
description: Valida contratos de API em runtime via MCP api-test (HTTP requests com assertions e import OpenAPI). Use quando o diff contiver backend (Java/Spring/Quarkus, controllers, resources, services expostos) e o QA precisar validar endpoints reais além dos testes unitários.
compatibility: opencode
---
## Objetivo

Validar contratos de API no runtime via MCP `api-test`: exercitar os endpoints do escopo da task com assertions determinísticas de status code e shape da resposta. Complementa o `sdd-qa-verification` para backend.

## Quando usar

Use APENAS quando:
- O diff contém backend (`.java`/`.kt` com controllers/resources/services expostos como API)
- Build e testes unitários já passaram no `sdd-qa-verification`
- O MCP `api-test` está disponível no harness

NÃO use para mudanças frontend-only. API runtime é opcional — nunca bloqueia por indisponibilidade da aplicação.

## Procedimento

1. **Subir a aplicação** (se não estiver rodando):
   - Spring: `timeout 180 ./mvnw spring-boot:run -pl <modulo>` ou `mvn spring-boot:run`
   - Quarkus: `timeout 180 ./mvnw quarkus:dev` ou `mvn quarkus:dev`
   - Aguarde readiness: poll na URL base até responder (default `http://localhost:8080`; confira a porta real em `application.properties`/`application.yml`/`application.properties quarkus`).
2. **Detectar contrato**: procure spec OpenAPI exposta — Springdoc: `/v3/api-docs`; Quarkus SmallRye: `/q/openapi`. Se disponível, importe a spec no MCP `api-test` para ganhar schema de referência.
3. **Mapear endpoints do escopo**: derive dos arquivos modificados (controllers/resources) os endpoints afetados pela task.
4. **Exercitar os endpoints**: para cada um, teste o fluxo de sucesso E o principal caminho de erro da task, com payloads realistas derivados do contrato.
5. **Assertar**: use as assertions do MCP `api-test` — status code esperado (2xx/4xx), content-type, campos essenciais do body, shape contra o schema quando importado.
6. **Salvar evidência**: registre as respostas/assertions em `.lla/sdd/current/{task_id}/api-{endpoint-sanitizado}.json`.
7. **Registrar resultado**: anote no `qa-report.md` como step `api-testing` (PASS/FAIL/SKIP) com 1-2 frases do que foi validado.

## Regras

- Asserção é fato observável: status code e body reais da resposta, nunca suposição.
- Teste apenas endpoints do escopo da task — não varra a API inteira.
- Se a aplicação não subir após 1 tentativa, `SKIP` com nota no `detail` — nunca faça o QA inteiro falhar por isso.
- Não crie dados de teste fora do escopo (sem poluir banco/prod); use payloads idempotentes quando possível.

## Fallback

Sem backend no diff → SKIP sem executar. Sem MCP disponível → SKIP com nota. Sem spec OpenAPI → testar pelos contratos lidos do código (controllers/DTOs) e anotar a ausência de schema no `detail`.