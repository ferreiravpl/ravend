---
name: remember
description: "Guarda uma lição específica deste projeto (de um finding de review, de uma correção sua ou de uma falha repetida do gate) para o Ravend não repetir o erro. A lição fica só na sua máquina e aparece no início de cada sessão."
argument-hint: "<lição ou finding a guardar>"
---

# Ravend · remember

Knowledge is per developer and per project, stored at `<data_dir>/knowledge/` (`data_dir` from `python3 "$RAVEND_ROOT/scripts/ravend.py" project`). It is never committed. Its index is injected at session start, so it must stay short.

## Capture only if all are true
- **Specific to this codebase** (a convention, a trap, an integration quirk) — not general advice the model already knows ("use constructor injection").
- **Reusable** — likely to matter again in a future task.
- **Not enforceable by a tool** already present. If a linter/formatter/ArchUnit/ESLint rule could enforce it, propose that rule to the developer instead (enforcement beats memory).
- **Observed**, not hypothetical — cite where it came from (review-N, file, date).

## Write
1. Check `<data_dir>/knowledge/index.md` for an existing lesson on the same topic → update it (add the new occurrence) instead of duplicating.
2. New lesson file `<data_dir>/knowledge/<kebab-topic>.md`, ≤12 lines:
   ```markdown
   ---
   scope: <module/layer/stack, e.g. backend/service, frontend/forms>
   source: <spec slug / review-N / date>
   ---
   # <rule in imperative form>
   Why: <the failure it prevents, concretely>
   Do: <the pattern to follow, with a file in this repo as example>
   Don't: <the anti-pattern as seen here>
   ```
3. Add/refresh one line in `index.md`: `- <rule in ≤15 words> (<scope>) → <file>.md`.
4. Keep the index ≤25 lines: merge or delete stale lessons rather than growing it.

Tell the developer what was saved (one line) — they can edit or delete any file there.
