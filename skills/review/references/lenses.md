# Review lenses

A lens is an extra checklist for a risk area (`profile.risk[].lenses`). `ravend next` lists the lenses a review of this code must cover; the reviewer reports which ones it checked in `"lenses"`. Each item below is a question to answer against the diff, with a concrete failure scenario when the answer is "no". Unknown lens names: review for the risk the name describes.

## money
- Amounts as integers in the minor unit (cents) or a decimal type — never float/double; rounding rule explicit and identical on every side of a split.
- Every operation that creates or moves money is idempotent (idempotency key derived from the operation, not random per retry).
- State transitions follow an explicit table; an out-of-order or late provider event is recorded, not applied blindly.
- A refund/void/chargeback path exists for each capture path; reconciliation data is persisted with the operation.

## concurrency
- Two replicas or two retries running the same handler/job: is the effect applied once? (dedup key, unique constraint, optimistic lock, `SELECT … FOR UPDATE SKIP LOCKED`).
- No external call (HTTP, broker, provider) while a DB transaction is open.
- Message consumers: duplicate, out-of-order and replayed messages handled; transient vs permanent errors distinguished (retry with backoff vs dead-letter).
- Timers/jobs persisted, not in-memory schedulers; time read from an injectable clock.

## security
- AuthN/AuthZ on every new endpoint, including admin routes and object ownership checks (IDOR).
- Input validation at the boundary; no injection (SQL, command, template, header).
- Secrets only from the secret store; none in code, logs, test fixtures or error messages.
- Rate limits / abuse paths on login, OTP and other enumerable endpoints.

## privacy
- No personal data in logs, metrics labels, traces or events that do not need it.
- New personal data has an owner, a retention rule and is covered by deletion/anonymization flows.
- Exports and admin views return only the subject's data.

## contract
- API and event changes are additive; a breaking change gets a new version published in parallel.
- Consumers ignore unknown fields; producers keep required fields.
- Contract tests (golden fixtures / OpenAPI) updated on both producer and consumer sides.

## migration
- Expand/contract: the previous app version still works against the new schema (no rename/drop in the same release).
- Long operations are safe online (`CREATE INDEX CONCURRENTLY`, `lock_timeout`, batched backfills).
- Forward-only; rollback = previous app version, not a down migration.

## infra
- Blast radius: what existing resources does the change replace or destroy? (`-/+`, `destroy` in the plan, renamed resources without `moved` blocks).
- Least privilege: IAM policies scoped to resources of this environment; no `*` actions/resources without reason.
- Stateful resources protected (`prevent_destroy`, deletion protection, backups, versioning); public access blocked by default.
- Environment isolation: names/tags carry the environment; staging cannot read production secrets or queues.
- CI/CD: actions pinned (version or SHA), minimal `permissions:`, OIDC instead of long-lived keys, no secrets echoed.
