---
name: e2e-playwright
description: "Como escrever testes E2E e visuais duráveis com @playwright/test para critérios [e2e] ou [visual] — setup, exploração da tela por um MCP de navegador, locators resilientes, asserções web-first, screenshots e traces. Carregada automaticamente quando um comportamento de UI precisa ser provado."
---

# E2E with Playwright

The deliverable is a **test file in the repo** that runs in the gate and in CI — not a one-off browser session. The `browser` integration (the developer's browser MCP; Playwright MCP by default) is for *exploring* the UI to discover structure and selectors; the result must be a `*.spec.ts`.

## 1. Setup (only if missing — ask before adding dependencies)
- Existing `playwright.config.*` → follow it (testDir, baseURL, projects).
- None → propose: `npm i -D @playwright/test && npx playwright install chromium`, plus a minimal config:
  ```ts
  import { defineConfig } from '@playwright/test';
  export default defineConfig({
    testDir: 'e2e',
    use: { baseURL: 'http://localhost:4200', trace: 'retain-on-failure', screenshot: 'only-on-failure' },
    webServer: { command: 'npm run start', url: 'http://localhost:4200', reuseExistingServer: true, timeout: 120_000 },
  });
  ```
  `webServer` starts the frontend itself. If the backend must be up, the gate step uses `needs_app` (profile `app`).
- Register the gate step in the local profile if absent: `{"name": "e2e", "cwd": "<web>", "run": "npx playwright test"}` in `gate.full`.

## 2. Explore (browser MCP, when available)
Navigate to the page, take accessibility snapshots, perform the flow once. Note roles, accessible names, labels and URLs. Keep exploration short; snapshots are large.

## 3. Write the test
```ts
import { test, expect } from '@playwright/test';

test.describe('checkout @order-pagination', () => {
  test('AC3: shows validation error for invalid coupon', async ({ page }) => {
    await page.goto('/cart');
    await page.getByLabel('Coupon').fill('NOPE');
    await page.getByRole('button', { name: 'Apply' }).click();
    await expect(page.getByRole('alert')).toHaveText(/invalid coupon/i);
  });
});
```
- Title starts with the AC id; describe tagged with `@<slug>` so `npx playwright test --grep @<slug>` runs just this feature.
- Locators: `getByRole` > `getByLabel` > `getByText` > `getByTestId`. No CSS/XPath chains tied to styling.
- Web-first assertions (`await expect(locator).toBeVisible()/toHaveText()`); never `waitForTimeout`.
- Test data: create it through the API or fixtures in the test, independent of other tests and of existing data; clean up if it persists.
- Cover the success path and the main error path of each AC.

## 4. Visual ACs
`await expect(page).toHaveScreenshot('cart-dark.png', { fullPage: true, maxDiffPixelRatio: 0.01 })` (or a locator screenshot for a component). First run creates baselines with `--update-snapshots`; review them visually before committing. Baselines are OS/browser specific — if CI runs on Linux and the developer on macOS, generate baselines in the CI image (or in Docker `mcr.microsoft.com/playwright`).

## 5. Run & evidence
`npx playwright test --grep @<slug>`; on failure inspect `test-results/**/trace.zip` (`npx playwright show-trace`). Copy screenshots that prove visual ACs to `<data_dir>/specs/<slug>/evidence/`.

Optional: Playwright's own test agents (`npx playwright init-agents --loop=claude`) provide planner/generator/healer agents for larger suites.
