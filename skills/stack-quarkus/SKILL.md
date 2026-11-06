---
name: stack-quarkus
description: "Particularidades de Quarkus para implementar e testar — @QuarkusTest com RestAssured, Dev Services, @InjectMock, Panache/transações, modelo de threads e comandos. Carregada automaticamente quando a task mexe num módulo Quarkus."
---

# Quarkus

**Codebase first.** Mirror an existing resource → service → persistence flow and its tests. Check `pom.xml`/`build.gradle` for the Quarkus version and the extensions in use (Quarkus REST vs legacy RESTEasy Classic, Hibernate ORM vs Reactive, Panache active record vs repository) — never mix paradigms the project doesn't use.

## Test levels → tools
| AC tag | Quarkus tool |
|---|---|
| `[unit]` | plain JUnit 5 + Mockito, no `@QuarkusTest` (fast) |
| `[api]` | `@QuarkusTest` + RestAssured (app boots once per test run; Dev Services start DB/Kafka containers automatically — Docker required) |
| collaborator mocking | `@InjectMock` (needs `quarkus-junit5-mockito`; bean must be normal-scoped, e.g. `@ApplicationScoped`, not `@Singleton`) |
| DB isolation | `@TestTransaction` (rolls back) or explicit cleanup |
| packaged app | `@QuarkusIntegrationTest` (runs against the built artifact; no injection) |
Snippets: [references/testing.md](references/testing.md).

## Commands
- One class: `./mvnw -q test -Dtest=OrderResourceTest` · Gradle: `./gradlew test --tests OrderResourceTest`
- Continuous testing while developing: `./mvnw quarkus:test`
- Dev mode: `./mvnw quarkus:dev` (Dev UI at `/q/dev-ui`, OpenAPI at `/q/openapi` with smallrye-openapi)
- Test config: `%test.` prefix in `application.properties`.

## Pitfalls that cause real bugs
- Threading (Quarkus REST): endpoints returning `Uni`/`Multi` run on the **event loop** — blocking calls there (JDBC, `Thread.sleep`, blocking clients) stall the server; use `@Blocking` or reactive clients. Endpoints with plain return types run on worker threads by default.
- Writes need `@Transactional` (Hibernate ORM) or `@WithTransaction` (Panache reactive); don't mix ORM and Reactive in the same flow.
- `@Singleton` beans are not proxied: no `@InjectMock`, no lazy init — use `@ApplicationScoped` unless the project deliberately uses `@Singleton`.
- Config injected with `@ConfigProperty` is read at startup; build-time properties can't change at runtime.
- Native image: reflection on DTOs may need `@RegisterForReflection` when the project builds native.
- Panache entities with public fields: don't add getters/setters "for consistency" if the project uses field access.
