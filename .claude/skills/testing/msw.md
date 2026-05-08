# MSW (Mock Service Worker) patterns for API mocking in tests and development.

## Install
```bash
npm install msw --save-dev
```

## Handler Definitions
```typescript
// src/mocks/handlers.ts
import { http, HttpResponse } from "msw"

export const handlers = [
  // GET with JSON response
  http.get("/api/users", () => {
    return HttpResponse.json([
      { id: "1", name: "Alice" },
      { id: "2", name: "Bob" },
    ])
  }),

  // GET with path parameter
  http.get("/api/users/:id", ({ params }) => {
    const { id } = params
    return HttpResponse.json({ id, name: "Alice", email: "alice@example.com" })
  }),

  // POST with request body
  http.post("/api/users", async ({ request }) => {
    const body = await request.json() as { name: string }
    return HttpResponse.json(
      { id: "3", name: body.name },
      { status: 201 }
    )
  }),

  // PATCH / PUT / DELETE
  http.patch("/api/users/:id", async ({ params, request }) => {
    const body = await request.json() as Partial<User>
    return HttpResponse.json({ id: params.id, ...body })
  }),

  http.delete("/api/users/:id", () => {
    return new HttpResponse(null, { status: 204 })
  }),

  // Error response
  http.get("/api/users/:id", ({ params }) => {
    if (params.id === "404") {
      return HttpResponse.json(
        { error: "User not found" },
        { status: 404 }
      )
    }
    return HttpResponse.json({ id: params.id, name: "Alice" })
  }),
]
```

## Node Setup (Vitest / Jest)
```typescript
// src/mocks/server.ts
import { setupServer } from "msw/node"
import { handlers } from "./handlers"

export const server = setupServer(...handlers)

// src/test/setup.ts (referenced in vitest config setupFiles)
import { beforeAll, afterEach, afterAll } from "vitest"
import { server } from "../mocks/server"

beforeAll(() => server.listen({ onUnhandledRequest: "error" }))
afterEach(() => server.resetHandlers())   // restore default handlers between tests
afterAll(() => server.close())
```

## Per-Test Overrides
```typescript
import { http, HttpResponse } from "msw"
import { server } from "../mocks/server"

it("shows error message when API fails", async () => {
  // Override just for this test — resets after each test via resetHandlers
  server.use(
    http.get("/api/users", () => {
      return HttpResponse.json(
        { error: "Internal server error" },
        { status: 500 }
      )
    })
  )

  render(<UserList />)
  expect(await screen.findByText(/something went wrong/i)).toBeInTheDocument()
})

it("handles empty list", async () => {
  server.use(
    http.get("/api/users", () => {
      return HttpResponse.json([])
    })
  )

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
    return worker.start({ onUnhandledRequest: "bypass" })
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
    http.post("/api/users", async ({ request }) => {
      const body = await request.json()
      createUser(body)
      return HttpResponse.json({ id: "3", ...body }, { status: 201 })
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
http.get("/api/users", async () => {
  await delay(2000)
  return HttpResponse.json([])
})

// Network error (simulate offline)
http.get("/api/users", () => {
  return HttpResponse.error()
})

// Passthrough (let real request go through)
http.get("/api/health", () => {
  return passthrough()
})
```

## Rules
- Define base handlers in `handlers.ts` — per-test overrides go in `server.use()`
- Always call `server.resetHandlers()` in `afterEach` — prevents test pollution
- Use `onUnhandledRequest: "error"` in tests to catch missing handlers early
- Use `onUnhandledRequest: "bypass"` in browser to allow real requests for non-mocked endpoints
- MSW intercepts at the network level — works with any HTTP client (fetch, axios, ky)
