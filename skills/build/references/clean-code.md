# Clean code standard

Applies to code written for the current spec (production and tests). Pre-existing code outside the task stays as it is. The project's written rules (project notes, AGENTS.md/CLAUDE.md, linters) win over this file; the codebase's style (naming, layout, idioms) is mirrored, its complexity is not.

## Control flow
- Guard clauses and early returns instead of `if / else if / else` ladders; no `else` after `return`/`throw`/`continue`.
- Nesting ≤ 2 levels inside a function. Deeper → extract a function or invert the condition.
- A compound condition gets a name: a well-named predicate function or local variable.
- The same `switch`/`if` chain over a type or status in more than one place → one lookup table, map or polymorphic method.
- Use the language's idioms when they remove branching and still read plainly (Optional/streams, `?.`/`??`, pattern matching, comprehensions). Never golf.

## Functions
- One job, one level of abstraction; the name says the job. Aim for ≤ 20 lines and cyclomatic complexity ≤ 5 (the gate's limit, if any, is the hard ceiling).
- ≤ 3 parameters. More → a parameter object/record. No boolean flag parameters: two functions instead.
- Return values; don't mutate arguments. A `void` method that fills or changes a parameter (output parameter) becomes a function that returns the new value. Commands (change state) and queries (return data) stay separate.
- Prefer immutable values (records, data classes, `final`/`const`, readonly) and pure functions; keep side effects at the edges.

## Names and types
- Intention-revealing names, no abbreviations or one-letter names outside trivial lambdas/loops (`request`, not `b`).
- Named constants for values that carry meaning (limits, formats, protocol keys); not for the obvious (`0`, `""`).
- Real types for structured data: no `Object[]`, untyped maps or tuples as ad-hoc structs, no index-based field access, no cast chains or avoidable unchecked suppressions.

## DRY, YAGNI, KISS
- **DRY**: one source of truth for each piece of knowledge — a catalog, a config, a mapping, a test setup. Adding the next item should mean editing one place. Duplicate *knowledge*, not lines that merely look alike, is what to remove.
- **YAGNI**: no branch, parameter, option, extension point or input type that no acceptance criterion needs. Validate at system boundaries; don't defend against cases that cannot occur inside.
- **KISS**: the simplest construct the team already reads; standard library before a new abstraction; one obvious way.

## Tests
- Each test reads as a scenario: arrange, act, assert, with helpers/builders hiding SDK and setup noise.
- One shared helper/fixture/builder per setup — reuse what earlier tasks of the spec created; never copy setup between test classes.
- Variations of one case → a parameterized/table test. Resource lifecycle through the framework (fixtures, `@AutoClose`, `afterEach`), not hand-written open/close pairs.
- Test names describe the behavior (`rejectsCouponBelowMinimum`), not ids.

## Comments
- Business code and tests: comment only the **why** — a business rule, an external constraint, a non-obvious trap. Never restate the **what**. Doc comments on public API only when they add something the signature doesn't (unit, format, invariant, thrown errors); no `@param id the id`.
- Foundation, infra and configuration (IaC, Helm values, CI workflows, build files, shared libraries' public API, framework config): comment each non-obvious setting, value or workaround with its reason and source (limit, incident, vendor docs) — readers can't infer intent from a value.
- Never in code: references to the delivery process — review rounds, task ids, spec slugs, acceptance-criterion numbers, story ids, "decided on <date>". They go in commit messages and the PR.
- No commented-out code.
- Language: follow the repository's rule (see the session's language note).
