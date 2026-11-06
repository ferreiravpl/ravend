---
name: stack-react
description: "Particularidades de React (Vite/Next) para implementar e testar — Vitest/Jest com Testing Library, MSW para rede, testes relacionados, tokens de estilo e armadilhas de hooks. Carregada automaticamente quando a task mexe num app React."
---

# React

**Codebase first.** Mirror an existing component/hook/page and its tests: state management (local state, Context, Zustand/Redux, TanStack Query), styling (Tailwind tokens, CSS modules), data fetching, file layout. Don't introduce a new library for a task.

## Test levels → tools
| AC tag | Tool |
|---|---|
| `[unit]` logic/hooks | Vitest (or Jest) — pure functions, `renderHook` |
| `[unit]` component | `@testing-library/react` + `@testing-library/user-event`, query by role/label/text (what the user sees), never by class names |
| network | MSW handlers (if the project uses them) or mocked fetch module |
| `[e2e]`/`[visual]` | Playwright — see `ravend:e2e-playwright`; visual changes → `toHaveScreenshot` |
Snippets: [references/testing.md](references/testing.md).

## Commands
- Related tests only: `npx vitest related src/components/Cart.tsx --run` · Jest: `npx jest --findRelatedTests <files>`
- One file: `npx vitest run src/components/Cart.test.tsx`
- Typecheck: `npx tsc -b` (Vite project references) or `npx tsc --noEmit`
- Build: `npm run build`

## Pitfalls that cause real bugs
- `useEffect` with missing/unstable deps → stale data or infinite loops; derive values during render instead of syncing state in effects.
- State updates based on previous state must use the updater form (`setX(x => …)`).
- List keys must be stable ids, not indexes, when items can reorder/delete.
- Async effects need cancellation (AbortController / ignore flag) to avoid setting state after unmount or out-of-order responses.
- Design tokens: when the project has a theme (Tailwind `@theme`, CSS variables), use tokens — hardcoded colors/spacing were the most common review rejection in practice.
- Accessibility is testable: interactive elements must be buttons/links with accessible names; Testing Library role queries catch regressions.
