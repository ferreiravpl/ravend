---
name: event-tests
description: "Como provar critérios [contract], [async] e [migration] — contrato produtor/consumidor, consumidor idempotente (duplicado, fora de ordem, concorrente), DLQ, jobs com relógio controlável e migration compatível. Carregada quando um comportamento assíncrono precisa ser provado."
---

# Event-driven tests

The deliverable is a test in the repo that runs in the gate. Async behavior is proven with deterministic tests (controlled clock, harness that delivers messages explicitly), never with `sleep`. **Codebase first**: if the project has a test kit for its messaging (fakes, consumer/job harness, fixture loader), use it — never build a second one.

## Which level proves what
| AC tag | Proves | Typical test |
|---|---|---|
| `[contract]` | producer and consumer agree on the payload | producer serializes == golden fixture; consumer deserializes the fixture (and ignores unknown fields) |
| `[async]` | a message/job has its effect exactly once, whatever the delivery order | integration test with the real DB (Testcontainers/Dev Services) + broker fake or emulator |
| `[migration]` | the schema change is safe online and with the previous app version | migrate, then run the previous version's queries/tests against the new schema |

## [async] — what each test must cover (pick those the AC implies)
1. **Happy path**: message in → state changed → outgoing event recorded (outbox row or fake publisher), in the same transaction as the change.
2. **Duplicate**: same message id twice → one effect. Assert on the effect (rows, calls), not on logs.
3. **Out of order**: a state-carrying (snapshot/versioned) event older than what was applied → ignored; a fact event (something happened) is never dropped for its version — only deduplicated.
4. **Concurrency**: two consumers/replicas process the same item at once (two threads + a latch, or two transactions) → one wins, the other is a no-op (unique constraint, optimistic lock, `SKIP LOCKED`).
5. **Failure handling**: transient error (dependency down, timeout) → retried, not dead-lettered; permanent error (invalid payload, rule violated) → dead-letter at once.
6. **Expiry/timers**: with an injectable clock, advance time instead of waiting; a job that finds the aggregate already changed is a no-op.
Snippets (Quarkus and Spring): [references/patterns.md](references/patterns.md).

## [contract] rules
- Fixtures are versioned JSON files next to the event definition (or in the shared contracts repo). Never regenerate a fixture to make a producer test pass — a changed fixture is a contract change: additive only, or a new version.
- Producer test: build the event from a domain object → serialize → compare with the fixture ignoring field order (JSON assert), with fixed ids/timestamps from the test clock.
- Consumer test: read the fixture (plus one with an extra unknown field) → deserialize → handler produces the expected effect.
- Contract lives in another repository (`related_repos`)? Read the fixture from there in the test only if the project already does; otherwise the test uses the copy the build pulls (library artifact).

## [migration] rules
- Forward-only, expand/contract: add nullable/defaulted columns and new tables; renames and drops come in a later release.
- Test: apply all migrations on a fresh DB (the integration tests already do) **and** run the previous version's repository/queries against it when the project supports it; otherwise assert the old columns/tables still exist and old inserts still succeed.
- Locks: long operations use `CREATE INDEX CONCURRENTLY` (outside a transaction), `lock_timeout`, batched backfills — flag a migration that rewrites a big table in one statement.

## Don'ts
- No `Thread.sleep`/polling loops without a deadline; use Awaitility (with a timeout) only where the framework delivers asynchronously.
- No shared broker/DB state across tests; each test creates its data and a unique message id.
- Do not mock the repository in `[async]` tests — the dedup/lock lives in the database.
