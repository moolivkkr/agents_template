# Playwright patterns for browser E2E testing.

## Configuration

Pipeline runs test the **deployed** build: Wave 3.5 deploys the committed code, and every browser tier
targets `APP_BASE_URL`. On lab-cluster projects that is qa, `http://<app>-qa.localhost:18080`. There is
no `webServer` for those runs. A dev server would test code that nobody deployed.

```typescript
// playwright.config.ts
import { defineConfig, devices } from "@playwright/test"

const baseURL = process.env.APP_BASE_URL            // set by the pipeline; required
if (!baseURL) throw new Error("APP_BASE_URL is not set — run against the deployed app (Wave 3.5), not a dev server")
const junitFile = process.env.PW_JUNIT_FILE ?? `agent_state/phases/${process.env.PHASE ?? "local"}/junit/e2e.xml`

export default defineConfig({
  testDir: "./e2e",
  timeout: 30_000,
  expect: { timeout: 5_000 },
  forbidOnly: true,                 // a committed test.only fails the run instead of silencing its siblings
  retries: 0,                       // no retries to green: a flaky test is a failing test
  failOnFlakyTests: true,           // Playwright ≥ 1.52: if anyone raises retries, a pass-on-retry still fails the run
  workers: process.env.CI ? 2 : undefined,
  reporter: [["list"], ["junit", { outputFile: junitFile }], ["html", { open: "never" }]],
  use: {
    baseURL,
    screenshot: "only-on-failure",
    trace: "retain-on-failure",     // with retries 0, "on-first-retry" would never record a trace
    video: "retain-on-failure",
  },
  projects: [
    { name: "chromium", use: { ...devices["Desktop Chrome"] } },
    { name: "mobile", use: { ...devices["Pixel 5"] } },
  ],
})
```

A developer running locally sets `APP_BASE_URL=http://localhost:<port>` against a stack they started
themselves.

### Flake policy

- `retries: 0`. A test that fails intermittently **fails**. Fix the cause: a selector racing the UI, an
  unawaited request, shared data between tests, or a real race in the product. Many "flaky" e2e tests
  are double-submits and ordering bugs.
- `failOnFlakyTests: true` (Playwright 1.52 and later) keeps that true if retries are ever turned on:
  a pass-on-retry is reported as flaky and fails the run. `junit-to-sidecar.py` also counts any test
  that failed and then passed as `flaky`, and the gate blocks on `flaky > 0`.
- To quarantine a test you can't fix this phase, record it in the sidecar's `quarantined[]` with an
  issue link and an `expires` date no more than 14 days out (`test-results-sidecar.md`). Never
  quarantine with a silent `test.skip`.
- To prove a new or changed test is stable before handing it off, run it repeatedly:
  `npx playwright test <file> --repeat-each=5`.

## Page Object Pattern
```typescript
// e2e/pages/login.page.ts
import { type Page, type Locator } from "@playwright/test"

export class LoginPage {
  readonly emailInput: Locator
  readonly passwordInput: Locator
  readonly submitButton: Locator

  constructor(private page: Page) {
    this.emailInput = page.getByLabel("Email")
    this.passwordInput = page.getByLabel("Password")
    this.submitButton = page.getByRole("button", { name: "Sign in" })
  }

  async goto() {
    await this.page.goto("/login")
  }

  async login(email: string, password: string) {
    await this.emailInput.fill(email)
    await this.passwordInput.fill(password)
    await this.submitButton.click()
  }
}
```

## Locator Strategies (prefer accessible selectors)
```typescript
// Best — role-based (mirrors screen reader / user intent)
page.getByRole("button", { name: "Submit" })
page.getByRole("heading", { level: 1 })
page.getByRole("link", { name: /dashboard/i })
page.getByRole("textbox", { name: "Search" })

// Good — label and text
page.getByLabel("Email address")
page.getByText("Welcome back")
page.getByPlaceholder("Search...")

// Acceptable — test IDs (when no accessible selector exists)
page.getByTestId("user-avatar")

// Avoid — CSS / XPath selectors (fragile)
```

## Test Structure
```typescript
import { test, expect } from "@playwright/test"
import { LoginPage } from "./pages/login.page"

test.describe("Authentication", () => {
  test("user can log in and see dashboard", async ({ page }) => {
    const loginPage = new LoginPage(page)
    await loginPage.goto()
    await loginPage.login("alice@example.com", "password123")

    await expect(page).toHaveURL("/dashboard")
    await expect(page.getByRole("heading", { name: "Dashboard" })).toBeVisible()
  })

  test("shows error on invalid credentials", async ({ page }) => {
    const loginPage = new LoginPage(page)
    await loginPage.goto()
    await loginPage.login("alice@example.com", "wrong")

    await expect(page.getByRole("alert")).toContainText("Invalid credentials")
  })
})
```

## Assertions
```typescript
// Element assertions (auto-waiting, auto-retrying)
await expect(page.getByText("Success")).toBeVisible()
await expect(page.getByRole("button")).toBeEnabled()
await expect(page.getByRole("textbox")).toHaveValue("alice@example.com")
await expect(page.getByTestId("item-list")).toHaveCount(3)

// Page assertions
await expect(page).toHaveURL(/.*dashboard/)
await expect(page).toHaveTitle("Dashboard | App")

// Negative assertions
await expect(page.getByText("Error")).not.toBeVisible()
```

## API Mocking and Network

E2E and acceptance specs hit the real deployed API. Mock a route only to force a state the real
backend can't produce on demand, such as a network failure or a 503. When you do, build the body from
the envelope types (`api/response-envelope.md`) so the mock can't drift from the contract:

```typescript
import type { ApiSuccess, ApiErrorBody } from "../src/api/types"   // generated from the contract

// Force the error state
await page.route("**/api/v1/users", (route) =>
  route.fulfill({
    status: 503,
    contentType: "application/json",
    body: JSON.stringify({ error: { code: "UNAVAILABLE", message: "Try again shortly.", request_id: "e2e", retryable: true } } satisfies ApiErrorBody),
  })
)
// Force the network failure path
await page.route("**/api/v1/users", (route) => route.abort("internetdisconnected"))

// Wait for a specific API call
const responsePromise = page.waitForResponse("**/api/users")
await page.getByRole("button", { name: "Load" }).click()
const response = await responsePromise
expect(response.status()).toBe(200)
```

## Accessibility (page level)

`@axe-core/playwright` exports **`AxeBuilder`**. `injectAxe` and `checkA11y` belong to a different
package, `axe-playwright`, and don't exist here.

```typescript
import { test, expect } from "@playwright/test"
import AxeBuilder from "@axe-core/playwright"

test("TC-A11Y-20101 order form has no WCAG 2.2 AA violations", async ({ page }) => {
  await page.goto("/orders/new")
  const results = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"])
    .analyze()
  expect(results.violations.map((v) => `${v.id}: ${v.nodes.map((n) => n.target).join(" ")}`)).toEqual([])
})
```

This runs in a real browser, so `color-contrast` is checked here. Component tests with `jest-axe` can't
check contrast.

## Security rows (abuse-case matrix)

```typescript
test("TC-SEC-20105 SESSION-STORAGE: no token in web storage after sign-in", async ({ page, context }) => {
  await signIn(page, persona("buyer"))
  await page.reload()
  const stored = await page.evaluate(() => JSON.stringify({ ...localStorage, ...sessionStorage }))
  expect(stored).not.toMatch(/eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\./)          // JWT-shaped values
  const session = (await context.cookies()).find((c) => c.name === SESSION_COOKIE)
  expect(session).toMatchObject({ httpOnly: true, secure: true })
})

test("TC-SEC-20106 XSS-RENDER: a stored script payload renders as text", async ({ page }) => {
  const payload = '<img src=x onerror="window.__xss=1">'
  await createNoteViaApi(persona("buyer"), payload)          // through the product API, as the persona
  await page.goto("/notes")
  await expect(page.getByText(payload)).toBeVisible()
  expect(await page.evaluate(() => (window as any).__xss)).toBeUndefined()
})
```

## Authentication State (reuse login)
```typescript
// e2e/auth.setup.ts
import { test as setup } from "@playwright/test"

setup("authenticate", async ({ page }) => {
  // Credentials come from the environment the seed step populated. Never commit them.
  const email = process.env.E2E_ADMIN_EMAIL, password = process.env.E2E_ADMIN_PASSWORD
  if (!email || !password) throw new Error("E2E_ADMIN_EMAIL / E2E_ADMIN_PASSWORD not set")
  await page.goto("/login")
  await page.getByLabel("Email").fill(email)
  await page.getByLabel("Password").fill(password)
  await page.getByRole("button", { name: "Sign in" }).click()
  await page.waitForURL("/dashboard")
  await page.context().storageState({ path: ".auth/user.json" })   // gitignore .auth/
})

// Use in config: { storageState: ".auth/user.json" }
```

## Run Commands

In the pipeline the command comes from `agent_state/config/verify-commands.json` (`commands."test:e2e"`),
with `APP_BASE_URL` and `PHASE` exported. These are the building blocks:

```bash
APP_BASE_URL=http://app-qa.localhost:18080 npx playwright test          # run all tests against qa
npx playwright test --project=chromium    # specific browser
npx playwright test e2e/login.spec.ts     # specific file
npx playwright test e2e/login.spec.ts --repeat-each=5   # prove a new test is stable
npx playwright test --ui                  # interactive UI mode (local debugging only)
npx playwright show-report                # view HTML report
npx playwright show-trace test-results/<test>/trace.zip   # inspect a failure's trace
npx playwright codegen "$APP_BASE_URL"    # record actions
```

## Rules
- Use `getByRole` as the primary locator — it enforces accessibility
- Never use hard `waitForTimeout` — use auto-waiting assertions or `waitForResponse`
- Use page objects for pages with 3+ interactions — keeps tests readable
- `retries: 0`, `forbidOnly: true`, `failOnFlakyTests: true`; traces, screenshots and videos retained on failure
- Put the TC ID at the start of every test title: `test("TC-E2E-20101 buyer places an order", …)` (`test-case-traceability.md`)
- Target `APP_BASE_URL` (the deployed build); never start a dev server for pipeline runs
- Every test creates its own data with run-unique identifiers (e.g. an email with the run id), so tests stay independent and re-runnable against a shared qa environment
- Run `npx playwright install` in CI to ensure browsers are present
