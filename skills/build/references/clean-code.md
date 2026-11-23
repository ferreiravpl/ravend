# Clean code standard

Applies to code written for the current spec (production and tests). Pre-existing code outside the task stays as it is. The project's written rules (project notes, AGENTS.md/CLAUDE.md, linters) win over this file; the codebase's style (naming, layout, idioms) is mirrored, its complexity is not.

## Readability first
The goal is code a developer who never saw the spec understands in **30 seconds per function**: the name says what it does, the body reads as a few named steps. Complexity limits are ceilings, not targets — never trade an `if` for a denser expression (nested lambdas, ternaries, chained calls, ad-hoc pairs) just to lower a metric. A plain `if` with an early return beats a clever pipeline.

## Control flow
- Guard clauses and early returns instead of `if / else if / else` ladders; no `else` after `return`/`throw`/`continue`.
- Nesting ≤ 2 levels inside a function — **a lambda counts as a level**. A lambda whose body holds another pipeline, a loop, or more than one condition becomes a named method (pass it as a method reference).
- Ternary only picks a value. If either side recurses, throws, has an effect, or runs a pipeline → `if` with early return.
- A compound condition (`&&`, `||`) or a negated chain or comparison (`!order.getItems().isEmpty()`, `!x.equals(y)`) gets a name: a predicate method (`hasItems(order)`, `isOutOfStock(item)`) or a local variable. Negating one well-named predicate (`!isSnakeCase(name)`, `not(Order::isPaid)`) is already readable — leave it.
- The same `switch`/`if` chain over a type or status in more than one place → one lookup table, map or polymorphic method.

## Functions
- One job, one level of abstraction: a function either **orchestrates** named steps or **does** one low-level step, never both. The name says the job. Aim for ≤ 15 lines.
- ≤ 3 parameters. More → a parameter object/record. No boolean flag parameters: two functions instead.
- Return values; don't mutate arguments or outer objects. No `void` method that fills a parameter; no side effects inside pipelines (`forEach`/`peek` changing a builder, list or map declared outside) — build the value with a function that returns it.
- An expression used twice in a function → a local variable with a name.
- Prefer immutable values (records, data classes, `final`/`const`, readonly) and pure functions; keep side effects at the edges.

## Pipelines (streams, LINQ, array chains)
- A pipeline with more than 3 operations, or one that answers a question ("which orders are overdue?"), lives in its own method named after the answer: `overdueOrders()`. The caller reads the name, not the pipeline.
- Each step does one thing; logic inside a step goes to a named method. No pipeline nested inside another pipeline's lambda.
- Never use pairs (`Map.entry`, `Map.Entry`, tuples, 2-element arrays) as a value that travels between steps or methods: declare a small record/type with named fields.

## Names, literals and types
- Intention-revealing names, no abbreviations or one-letter names outside trivial lambdas/loops (`request`, not `b`). A variable named after what it holds (`entry`, not `example`, for a map entry).
- **No magic literals.** Every number, character or string whose meaning depends on the domain or a protocol gets a named constant or a helper: positions, weights, moduli, status codes, limits, header values, message fragments (`CHECK_DIGIT_MODULUS = 11`, `digitAt(code, i)` instead of `code.charAt(i) - '0'`). Only `0`, `1`, `-1`, `""` and the like used for their arithmetic meaning stay inline.
- Library navigation chains (`a.getB().getC().get(KEY).getD()`) live in one adapter method named in domain terms; the rest of the code calls it. Raw types and casts from a library are confined there too.
- Real types for structured data: no `Object[]`, untyped maps, nested collections (`Map<Integer, Set<String>>`) or tuples as domain data, no index-based field access, no cast chains or avoidable unchecked suppressions.

## DRY, YAGNI, KISS
- **DRY**: one source of truth for each piece of knowledge — a catalog, a config, a mapping, a test setup, a default every row shares. Adding the next item should mean editing one place. Two pipelines with the same shape over different sources → one method with the source as parameter.
- **YAGNI**: no branch, parameter, option, extension point or input type that no acceptance criterion needs. Validate at system boundaries; don't defend against cases that cannot occur inside.
- **KISS**: the simplest construct the team already reads; standard library before a new abstraction; one obvious way.

## Tests
- A test body is arrange / act / assert in a few lines that state the scenario; walking structures, filtering and building labels go to helpers named after what they return (`pendingInvoices()`, `fieldsMissingFrom(schema, payload)`).
- One shared helper/fixture/builder per setup — reuse what earlier tasks of the spec created; never copy setup between test classes.
- Data tables: one row per line through a named builder/factory (`post("/orders").created().conflict("ORDER_EXISTS")`), shared defaults in the builder, no positional constructors with nested collections.
- Variations of one case → a parameterized/table test. Resource lifecycle through the framework (fixtures, `@AutoClose`, `afterEach`), not hand-written open/close pairs.
- Test names describe the behavior (`rejectsCouponBelowMinimum`), not ids.

## Comments
- Business code and tests: comment only the **why** — a business rule, an external constraint, a non-obvious trap. Never restate the **what**. Doc comments on public API only when they add something the signature doesn't (unit, format, invariant, thrown errors); no `@param id the id`.
- Foundation, infra and configuration (IaC, Helm values, CI workflows, build files, shared libraries' public API, framework config): comment each non-obvious setting, value or workaround with its reason and source (limit, incident, vendor docs) — readers can't infer intent from a value.
- Never in code: references to the delivery process — review rounds, task ids, spec slugs, acceptance-criterion numbers, story ids, "decided on <date>". They go in commit messages and the PR.
- No commented-out code.
- Language: follow the repository's rule (see the session's language note).
