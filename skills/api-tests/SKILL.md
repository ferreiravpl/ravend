---
name: api-tests
description: Write durable API/integration tests for acceptance criteria tagged [api] — HTTP contract, status codes, validation and persistence through the real stack (Spring MockMvc/RestAssured, Quarkus @QuarkusTest, Testcontainers/Dev Services, optional OpenAPI contract checks). Use when backend behavior exposed over HTTP must be proven.
---

# API tests

The deliverable is a test in the repo that runs in the gate, not a manual request. Prefer the level that proves the AC with the least machinery.

## Choose the level
| Need | Spring | Quarkus |
|---|---|---|
| request mapping, validation, error format, serialization | `@WebMvcTest` + MockMvc, services mocked | `@QuarkusTest` + RestAssured with `@InjectMock` |
| full flow incl. persistence/transactions | `@SpringBootTest(RANDOM_PORT)` + RestAssured + Testcontainers `@ServiceConnection` | `@QuarkusTest` + Dev Services DB |
| packaged artifact / container | Failsafe IT against the jar | `@QuarkusIntegrationTest` |
Snippets per stack: `ravend:stack-spring` / `ravend:stack-quarkus` references.

## What each API AC test asserts
1. Status code **and** body shape/values of the success path (not just 200).
2. The main error path of the AC: validation (400 with the project's error format), not found (404), conflict (409), auth (401/403) when relevant.
3. Side effects that matter: persisted state (re-fetch via API or repository), emitted events/messages when the AC says so.
4. Idempotency/pagination/sorting rules when the AC mentions them.
Name/describe the test with the AC id.

## Contract check (when an OpenAPI spec exists)
- Spring springdoc → `/v3/api-docs`; Quarkus smallrye-openapi → `/q/openapi`.
- If the change alters the contract, make sure the generated spec reflects it (annotations, DTO schema) and that frontend clients/types generated from it are regenerated the way the project does.
- Optional fuzzing in gate.full when the tool is available: `schemathesis run http://localhost:8080/v3/api-docs --checks all` (needs `needs_app`).

## Rules
- Real database through Testcontainers/Dev Services when production uses it; H2 only if the project already standardizes on it.
- Tests create their own data and do not depend on order; never point tests at shared environments.
- Don't loosen security config to make a test pass — authenticate the test client the way existing tests do.
