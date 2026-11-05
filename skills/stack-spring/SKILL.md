---
name: stack-spring
description: Spring Boot specifics for implementing and testing changes — test slices, Testcontainers, Surefire/Gradle commands and version pitfalls (Boot 3/4, jakarta, transactions, JPA). Use when a task touches a Spring Boot module.
---

# Spring Boot

**Codebase first.** Before writing code, open one existing feature similar to the task (controller → service → repository → tests) and mirror its structure, naming, DTO mapping, error handling and test style. Everything below is fallback when the repo has no precedent.

## Check the version
`pom.xml`/`build.gradle`: Spring Boot 3.x (Java 17+, `jakarta.*`) vs 4.x (Spring Framework 7, Jackson 3, `@MockitoBean`). Don't use APIs from a newer version than the project's. Context7 MCP (if configured) for exact APIs.

## Test levels → tools
| AC tag | Spring tool |
|---|---|
| `[unit]` | JUnit 5 + Mockito (`@ExtendWith(MockitoExtension.class)`), AssertJ — no Spring context |
| `[api]` web contract | `@WebMvcTest(XController.class)` + `MockMvc`/`MockMvcTester` + `@MockitoBean` for collaborators |
| `[api]` end-to-end in JVM | `@SpringBootTest(webEnvironment = RANDOM_PORT)` + RestAssured/`RestClient` + Testcontainers DB |
| persistence | `@DataJpaTest` + Testcontainers (`@ServiceConnection`), not H2 when prod is Postgres/MySQL |
Snippets: [references/testing.md](references/testing.md).

## Commands
- One class: `./mvnw -q test -Dtest=OrderServiceTest` · pattern: `-Dtest='Order*Test'` · method: `-Dtest=OrderServiceTest#should_x`
- Multi-module: `./mvnw -q -pl <module> -am test -Dtest=... -Dsurefire.failIfNoSpecifiedTests=false`
- ITs (Failsafe, `*IT`): `./mvnw -q verify -Dit.test=OrderApiIT`
- Gradle: `./gradlew test --tests 'OrderServiceTest'`
- Run: `./mvnw spring-boot:run -Dspring-boot.run.profiles=local`

## Pitfalls that cause real bugs
- `@Transactional` is ignored on private methods and on self-invocation (`this.method()`); also check `readOnly` and rollback rules (checked exceptions don't roll back by default).
- Lazy associations outside a transaction → `LazyInitializationException`; loops over lazy collections → N+1 (use `JOIN FETCH`/`@EntityGraph`, or DTO projections).
- `spring.jpa.open-in-view` default true hides lazy-loading problems that explode in tests or async code.
- Validation needs `@Valid`/`@Validated` at the boundary; return errors the way the project does (often `ProblemDetail`/`@RestControllerAdvice`).
- `@MockBean` is deprecated since Boot 3.4 → `@MockitoBean`. Mixing JUnit 4 and 5 annotations silently skips tests.
- Changing a JPA entity without a migration (Flyway/Liquibase) breaks other environments — add the migration when the project uses one.
- Never log secrets/PII; don't widen CORS or security matchers to make a test pass.
