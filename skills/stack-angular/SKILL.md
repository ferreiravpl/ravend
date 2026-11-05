---
name: stack-angular
description: Angular specifics for implementing and testing changes — standalone components, signals, new control flow, TestBed with HttpTestingController, Vitest/Jest/Karma runners and reactive pitfalls. Use when a task touches an Angular app or library.
---

# Angular

**Codebase first.** Mirror an existing feature (component + service + routes + spec). Detect the era from `package.json`/`angular.json` and follow it: NgModules vs standalone, `*ngIf` vs `@if`, RxJS-heavy vs signals, reactive vs template-driven forms. Don't migrate patterns as a side effect of a task.

## Test runner (check before writing tests)
`angular.json` → `architect.test.builder`:
- `@angular/build:unit-test` → Vitest (default in recent Angular) · run `npx ng test --watch=false`
- `@angular-devkit/build-angular:karma` → Karma/Jasmine · `npx ng test --watch=false --browsers=ChromeHeadless`
- Jest builders/`jest.config.*` → `npx jest path/to/x.spec.ts`
Use the assertion/mocking API of that runner (`vi.fn` vs `jasmine.createSpy` vs `jest.fn`).

## Test levels → tools
| AC tag | Tool |
|---|---|
| `[unit]` logic | plain class/function tests; services with `TestBed.inject` |
| `[unit]` component | `TestBed` + `ComponentFixture`, query by role/text, trigger events, `await fixture.whenStable()` |
| HTTP | `provideHttpClient()` + `provideHttpClientTesting()` + `HttpTestingController` (`expectOne`, `flush`, `verify`) |
| `[e2e]`/`[visual]` | Playwright — see `ravend:e2e-playwright` |
Snippets: [references/testing.md](references/testing.md).

## Pitfalls that cause real bugs
- Manual `subscribe` without teardown → leaks/duplicate calls: prefer `async` pipe, `toSignal`, or `takeUntilDestroyed()`.
- `OnPush` components don't re-render on mutation — create new references; with signals, update via `set`/`update`.
- Nested subscribes / missing `switchMap` → race conditions on fast input (search boxes, route params).
- `any` and non-null assertions (`!`) hide contract changes from the backend — type DTOs explicitly.
- Direct DOM access (`document.querySelector`, `nativeElement.innerHTML`) breaks SSR and sanitization — use bindings/`Renderer2`.
- Forms: keep validation in the form model, show errors the way existing forms do; disable submit while pending.
- Route guards/resolvers: return `UrlTree` for redirects instead of imperative navigation inside guards.
