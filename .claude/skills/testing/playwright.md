# Playwright patterns for browser E2E testing.

## Configuration
```typescript
// playwright.config.ts
import { defineConfig, devices } from "@playwright/test"

export default defineConfig({
  testDir: "./e2e",
  timeout: 30_000,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: [["html", { open: "never" }]],
  use: {
    baseURL: "http://localhost:3000",
    screenshot: "only-on-failure",
    trace: "on-first-retry",
  },
  projects: [
    { name: "chromium", use: { ...devices["Desktop Chrome"] } },
    { name: "mobile", use: { ...devices["Pixel 5"] } },
  ],
  webServer: {
    command: "npm run dev",
    port: 3000,
    reuseExistingServer: !process.env.CI,
  },
})
```

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
```typescript
// Mock API response
await page.route("**/api/users", (route) =>
  route.fulfill({
    status: 200,
    contentType: "application/json",
    body: JSON.stringify([{ id: "1", name: "Alice" }]),
  })
)

// Wait for a specific API call
const responsePromise = page.waitForResponse("**/api/users")
await page.getByRole("button", { name: "Load" }).click()
const response = await responsePromise
expect(response.status()).toBe(200)
```

## Authentication State (reuse login)
```typescript
// e2e/auth.setup.ts
import { test as setup } from "@playwright/test"

setup("authenticate", async ({ page }) => {
  await page.goto("/login")
  await page.getByLabel("Email").fill("admin@example.com")
  await page.getByLabel("Password").fill("password")
  await page.getByRole("button", { name: "Sign in" }).click()
  await page.waitForURL("/dashboard")
  await page.context().storageState({ path: ".auth/user.json" })
})

// Use in config: { storageState: ".auth/user.json" }
```

## Run Commands
```bash
npx playwright test                       # run all tests
npx playwright test --project=chromium    # specific browser
npx playwright test e2e/login.spec.ts     # specific file
npx playwright test --ui                  # interactive UI mode
npx playwright show-report                # view HTML report
npx playwright codegen http://localhost:3000  # record actions
```

## Rules
- Use `getByRole` as the primary locator — it enforces accessibility
- Never use hard `waitForTimeout` — use auto-waiting assertions or `waitForResponse`
- Use page objects for pages with 3+ interactions — keeps tests readable
- Enable `screenshot: "only-on-failure"` and `trace: "on-first-retry"` for debugging CI failures
- Run `npx playwright install` in CI to ensure browsers are present
