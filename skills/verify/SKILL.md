---
name: verify
description: "Prova que a spec está pronta — roda o quality gate completo (build, todos os testes, lint, integração, E2E), confere se cada critério de aceite tem um teste que passa e escreve os testes de API/E2E que faltam. Não altera código de produção."
argument-hint: "<slug>"
---

# Ravend · verify

> **`--headless`**: never ask the user anything, and make your **final message exactly the JSON object in *Output*** — also when blocked or failing (use the blocked/FAIL form). The headless runner parses it.

Verification is evidence, not opinion: every acceptance criterion maps to a test that ran green in the full gate.

## 1. Full gate
`RV="python3 $RAVEND_ROOT/scripts/ravend.py"` (fallback: this skill's base dir + `/../../scripts/ravend.py`).
Integrations (`$RV project` → `integrations`, roles for `verify`): `browser`, `api`, `database`, `design`, `observability`.
Run `$RV gate full`. It runs every `gate.full` step from the local profile against the branch diff, starts the app when a step needs it, and prints only failure excerpts plus log paths. Do not re-run the same commands by hand to "double-check" — trust the gate output.

## 2. Acceptance-criteria matrix
Read `<data_dir>/specs/<slug>/spec.md`. For each AC find the test that proves it (search test names/descriptions for the behavior or an `AC<n>` tag; read the test to confirm it actually asserts the "then" clause). Classify:
- **covered** — a test asserts it and ran in the gate;
- **weak** — a test exists but does not assert the outcome (e.g. only "no exception", only status 200 without body, snapshot of nothing);
- **missing**.

## 3. Close gaps
- `[unit]`/`[api]` gaps → write the test (see `ravend:api-tests` for API level), run it. The `api` integration can exercise the endpoint to learn the real contract and `database` can confirm persistence — the proof is still a test in the repo.
- `[e2e]`/`[visual]` gaps → delegate to the `ravend:verifier` agent with: spec path, the AC ids, app URL/start info from the profile, and the `browser` (default: Playwright MCP) and `design` server names. It explores the UI with that browser MCP and writes durable `@playwright/test` specs following `ravend:e2e-playwright`; browser snapshots stay in its context, not here.
- Never change production code in this skill. If a new test exposes a real bug, record it as failing and record it with `--uncovered` so `next` sends it back to build as a fix.
- Re-run `$RV gate full` after adding tests.

## 4. Optional depth (large tier, or when the profile defines the steps)
Diff coverage and mutation testing run as `gate.full` steps when configured (e.g. JaCoCo + diff-cover, PIT `-DtargetClasses`, Stryker `--mutate <changed files>`). Surviving mutants in changed lines → treat as weak tests.

## 5. Record
- Write `<data_dir>/specs/<slug>/verify.md`: date, gate result (step → status), AC matrix (AC → test file::name → covered/weak/missing), evidence paths (screenshots/traces under `<data_dir>/specs/<slug>/evidence/`).
- Then record it for the state machine: `$RV verify record <slug>` plus one `--uncovered "AC2: why"` per missing/weak criterion. The runtime takes the gate result from its own last `gate full` and refuses if that gate did not run on exactly this code — re-run the gate, then record. If the data dir is read-only (sandbox), say so in the output instead.

## Output
Interactive: gate status, matrix summary, gaps closed/remaining, next step (`/ravend:continue`).
`--headless`: end with exactly one JSON object `{"gate": "PASS"|"FAIL", "uncovered_criteria": ["AC2: ..."], "summary": "..."}`.
