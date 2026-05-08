# Vitest patterns for Vite-native unit and component testing.

## Configuration
```typescript
// vite.config.ts
import { defineConfig } from "vite"
import react from "@vitejs/plugin-react"

export default defineConfig({
  plugins: [react()],
  test: {
    globals: true,                    // no need to import describe/it/expect
    environment: "jsdom",             // DOM APIs for component tests
    setupFiles: ["./src/test/setup.ts"],
    css: true,                        // process CSS imports
    coverage: {
      provider: "v8",
      reporter: ["text", "lcov"],
      include: ["src/**/*.{ts,tsx}"],
      exclude: ["src/**/*.test.*", "src/test/**"],
    },
  },
})
```

## Setup File
```typescript
// src/test/setup.ts
import "@testing-library/jest-dom/vitest"
import { cleanup } from "@testing-library/react"
import { afterEach } from "vitest"

afterEach(() => {
  cleanup()
})
```

## Basic Test Structure
```typescript
import { describe, it, expect } from "vitest"
import { formatCurrency } from "../utils/format"

describe("formatCurrency", () => {
  it("formats USD", () => {
    expect(formatCurrency(1234.5, "USD")).toBe("$1,234.50")
  })

  it("returns empty string for NaN", () => {
    expect(formatCurrency(NaN, "USD")).toBe("")
  })
})
```

## React Component Testing
```typescript
import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { UserCard } from "./UserCard"

describe("UserCard", () => {
  it("renders user name", () => {
    render(<UserCard user={{ id: "1", name: "Alice" }} />)
    expect(screen.getByText("Alice")).toBeInTheDocument()
  })

  it("calls onEdit when button clicked", async () => {
    const onEdit = vi.fn()
    render(<UserCard user={{ id: "1", name: "Alice" }} onEdit={onEdit} />)

    await userEvent.click(screen.getByRole("button", { name: /edit/i }))
    expect(onEdit).toHaveBeenCalledWith("1")
  })
})
```

## Mocking
```typescript
// Mock a module
vi.mock("../api/client", () => ({
  fetchUser: vi.fn(),
}))
import { fetchUser } from "../api/client"

it("fetches user on mount", async () => {
  vi.mocked(fetchUser).mockResolvedValue({ id: "1", name: "Alice" })

  render(<UserProfile userId="1" />)
  expect(await screen.findByText("Alice")).toBeInTheDocument()
})

// Spy on an existing function
const spy = vi.spyOn(console, "error").mockImplementation(() => {})
// ...
expect(spy).toHaveBeenCalledWith(expect.stringContaining("failed"))
spy.mockRestore()

// Mock timers
vi.useFakeTimers()
vi.advanceTimersByTime(1000)
vi.useRealTimers()
```

## Testing Hooks
```typescript
import { renderHook, waitFor } from "@testing-library/react"
import { useCounter } from "./useCounter"

it("increments counter", () => {
  const { result } = renderHook(() => useCounter(0))

  act(() => { result.current.increment() })
  expect(result.current.count).toBe(1)
})
```

## Snapshot Testing
```typescript
it("matches snapshot", () => {
  const { container } = render(<Badge variant="success">Active</Badge>)
  expect(container.firstChild).toMatchSnapshot()
})

// Inline snapshot — value auto-updated by Vitest
it("formats output", () => {
  expect(formatDate(new Date("2024-01-15"))).toMatchInlineSnapshot(`"Jan 15, 2024"`)
})
```

## Run Commands
```bash
vitest                     # watch mode (dev)
vitest run                 # single run (CI)
vitest run --coverage      # with coverage report
vitest run src/utils/      # run tests in specific directory
vitest run -t "formats"    # run tests matching name pattern
```

## Rules
- Use `screen.getByRole` over `getByTestId` — tests should mirror how users interact
- Use `userEvent` over `fireEvent` — it simulates real browser behavior (focus, blur, typing)
- Use `findBy*` (async) for elements that appear after state updates or fetches
- Never test implementation details (internal state, private methods) — test behavior
- Use `vi.fn()` for callbacks, `vi.mock()` for modules, `vi.spyOn()` for partial mocks
