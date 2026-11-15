---
name: stack-quarkus
description: "Particularidades de Quarkus para implementar e testar — @QuarkusTest, Dev Services, @InjectMock, transações, threads, mensageria, native, ArchUnit e Flyway. Carregada automaticamente quando a task mexe num módulo Quarkus."
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
| native image | `@QuarkusIntegrationTest` run with `-Dnative` (slow: gate.full or CI only, never gate.fast) |
| layering (hexagonal/onion) | ArchUnit test (`@AnalyzeClasses` + `layeredArchitecture()`, or jMolecules rules) — it is a normal unit test in the gate |
| messaging/jobs | see `ravend:event-tests`; AWS emulator (LocalStack/Floci) via Dev Services or Testcontainers when the project uses one |
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
- Native image: classes reached only by reflection (DTOs/events serialized by Jackson, records in a shared contracts jar) need `@RegisterForReflection` (or `targets = {...}` for classes from other jars); resources need `quarkus.native.resources.includes`. A JVM-green build can still fail native — when the project ships native, keep a native IT in gate.full or rely on CI (`ravend` follows it after the PR).
- Time: inject a `Clock` bean (tests replace it); `Instant.now()`/`LocalDate.now()` in domain or job code makes deadlines untestable.
- Domain layer stays framework-free when the project is hexagonal: no `jakarta.*`/`io.quarkus.*` imports in `domain` — the ArchUnit test fails otherwise.
- Flyway: migrations are immutable once merged (checksum); new change = new `V<n>__*.sql`. `quarkus.flyway.migrate-at-start` in tests only if the project does it.
- Scheduled business work: `@Scheduled` runs on every replica — business timers belong in a persisted job table (or the project's job abstraction), not in-memory schedulers.
- Panache entities with public fields: don't add getters/setters "for consistency" if the project uses field access.
