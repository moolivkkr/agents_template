# MSW (Mock Service Worker) patterns for API mocking in tests and development.

## Install
```bash
npm install msw --save-dev
```

> **MSW 3 (3.0.0 shipped 2026-09-28; `latest` is 3.0.1, checked 2026-09-30).** The option that decides what
> happens to a request no handler matches is now `onUnhandledFrame` (`"error" | "warn" | "bypass"` or a
> callback); MSW 2's `onUnhandledRequest` no longer exists in 3.x and fails to type-check. Use the name
> for the major in your lockfile; the examples below are MSW 3. `msw/native` was removed in 3.0.
> **Svelte:** pin `msw@^2.15` while tests run under `svelteTesting()` — its `browser` resolve condition
> stops `msw/node` 3.x from loading (see `frameworks/svelte.md`).

## Mocks are typed from the envelope — never hand-shaped

Every mocked response uses the one envelope in `api/response-envelope.md`:
- success is `{ data, meta: { request_id, pagination? } }`;
- an error is `{ error: { code, message, details?, request_id, retryable } }`.

Build them through typed helpers, and give every handler its response type through MSW's generics.
A mock that drifts from the contract then fails to **type-check**, instead of quietly testing a shape
the server never sends. That drift was the board review's DEV-03/ARCH-01 finding: a "✅ CORRECT" mock
contradicted the API.

```typescript
// src/mocks/envelope.ts — the only way tests build API bodies
import { HttpResponse } from "msw"
import type { ApiSuccess, ApiErrorBody, Pagination } from "../api/types"   // generated from the contract

let seq = 0
const rid = () => `test-${++seq}`

export const ok = <T>(data: T, status = 200) =>
  HttpResponse.json<ApiSuccess<T>>({ data, meta: { request_id: rid() } }, { status })

export const page = <T>(items: T[], p: Partial<Pagination> = {}) =>
  HttpResponse.json<ApiSuccess<T[]>>({
    data: items,
    meta: { request_id: rid(), pagination: { next_cursor: null, has_more: false, limit: 20, ...p } },
  })

export const apiError = (status: number, code: string, message: string, extra: Partial<ApiErrorBody["error"]> = {}) =>
  HttpResponse.json<ApiErrorBody>(
    { error: { code, message, request_id: rid(), retryable: status === 429 || status >= 503, ...extra } },
    { status },
  )
```

## Handler Definitions
```typescript
// src/mocks/handlers.ts
import { http, HttpResponse, type PathParams } from "msw"
import type { ApiSuccess, ApiErrorBody } from "../api/types"
import type { User, CreateUserInput } from "../api/types"
import { ok, page, apiError } from "./envelope"
import { userFixture } from "./fixtures"          // typed fixture builders: userFixture({ name: "Alice" })

type Res<T> = ApiSuccess<T> | ApiErrorBody

export const handlers = [
  // List: data is ALWAYS an array, pagination in meta
  http.get<PathParams, never, Res<User[]>>("/api/v1/users", () =>
    page([userFixture({ id: "u1", name: "Alice" }), userFixture({ id: "u2", name: "Bob" })])),

  // Single resource
  http.get<{ id: string }, never, Res<User>>("/api/v1/users/:id", ({ params }) =>
    params.id === "missing"
      ? apiError(404, "NOT_FOUND", "User not found.")
      : ok(userFixture({ id: params.id }))),

  // Create: request bodies are the payload itself, not wrapped
  http.post<PathParams, CreateUserInput, Res<User>>("/api/v1/users", async ({ request }) => {
    const body = await request.json()
    return ok(userFixture({ id: "u3", name: body.name }), 201)
  }),

  http.delete("/api/v1/users/:id", () => new HttpResponse(null, { status: 204 })),
]
```

`src/api/types` is generated from the contract (OpenAPI → `openapi-typescript`, or the types
`api_developer` publishes with `api-contracts.md`). Hand-written copies drift. If the project has no
generated types yet, report that instead of inventing a shape.

## Node Setup (Vitest / Jest)
```typescript
// src/mocks/server.ts
import { setupServer } from "msw/node"
import { handlers } from "./handlers"

export const server = setupServer(...handlers)

// src/test/setup.ts (referenced in vitest config setupFiles)
import { beforeAll, afterEach, afterAll } from "vitest"
import { server } from "../mocks/server"

beforeAll(() => server.listen({ onUnhandledFrame: "error" }))   // MSW 2: onUnhandledRequest
afterEach(() => server.resetHandlers())   // restore default handlers between tests
afterAll(() => server.close())
```

## Per-Test Overrides
```typescript
import { http, HttpResponse } from "msw"
import { server } from "../mocks/server"

it("TC-UI-20102 shows the error state when the API fails", async () => {
  // Override just for this test — resets after each test via resetHandlers
  server.use(http.get("/api/v1/users", () => apiError(503, "UNAVAILABLE", "Try again shortly.")))

  render(<UserList />)
  expect(await screen.findByRole("alert")).toHaveTextContent(/try again/i)
  expect(screen.getByRole("button", { name: /retry/i })).toBeVisible()
})

it("TC-UI-20103 shows the empty state for an empty list", async () => {
  server.use(http.get("/api/v1/users", () => page([])))   // data: [] — never null

  render(<UserList />)
  expect(await screen.findByText("No users found")).toBeInTheDocument()
})
```

## Browser Setup (Storybook / Dev Server)
```bash
# Generate service worker file
npx msw init public/ --save
```

```typescript
// src/mocks/browser.ts
import { setupWorker } from "msw/browser"
import { handlers } from "./handlers"

export const worker = setupWorker(...handlers)

// src/main.tsx — enable only in development
async function enableMocking() {
  if (import.meta.env.DEV) {
    const { worker } = await import("./mocks/browser")
    return worker.start({ onUnhandledFrame: "bypass" })   // MSW 2: onUnhandledRequest
  }
}

enableMocking().then(() => {
  ReactDOM.createRoot(document.getElementById("root")!).render(<App />)
})
```

## Request Assertions
```typescript
it("sends correct data on form submit", async () => {
  const createUser = vi.fn()
  server.use(
    http.post<PathParams, CreateUserInput>("/api/v1/users", async ({ request }) => {
      const body = await request.json()
      createUser(body)
      return ok(userFixture({ id: "u3", ...body }), 201)
    })
  )

  render(<CreateUserForm />)
  await userEvent.type(screen.getByLabelText("Name"), "Charlie")
  await userEvent.click(screen.getByRole("button", { name: "Create" }))

  await waitFor(() => {
    expect(createUser).toHaveBeenCalledWith({ name: "Charlie" })
  })
})
```

## Response Helpers
```typescript
// Delay (simulate slow network)
http.get("/api/v1/users", async () => {
  await delay(2000)
  return page([])
})

// Network error (simulate offline)
http.get("/api/v1/users", () => {
  return HttpResponse.error()
})

// Passthrough (let real request go through)
http.get("/healthz", () => {
  return passthrough()
})
```

## Rules
- Every body comes from `ok` / `page` / `apiError` (or `HttpResponse.json<ApiSuccess<T>>`), typed from the generated contract types — never a literal object shape
- Test both `data: [...]` and `data: []` for lists, a found resource and a 404 `NOT_FOUND` for single resources, and every documented error code
- Define base handlers in `handlers.ts` — per-test overrides go in `server.use()`
- Always call `server.resetHandlers()` in `afterEach` — prevents test pollution
- Use `onUnhandledFrame: "error"` (MSW 2: `onUnhandledRequest`) in tests to catch missing handlers early
- Use `onUnhandledFrame: "bypass"` (MSW 2: `onUnhandledRequest`) in the browser to let non-mocked requests through
- MSW intercepts at the network level — works with any HTTP client (fetch, axios, ky)

> Config blocks checked 2026-09-30 (`bash tests/archetype-compile/config-packs/run.sh --live`): 2 bash blocks: bash -n (macOS bash 3.2.57) + shellcheck 0.11.0.
