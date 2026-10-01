# Vitest patterns for Vite-native unit and component testing.

> TypeScript samples compile-checked 2026-09-30: TS 7.0.2 strict + noUncheckedIndexedAccess, Vitest 5.0, Vite 8.3, @vitejs/plugin-react 6.1, Testing Library (react 16.3, user-event 14.6, jest-dom 7.0), React 19. Type-checked only (tests/archetype-compile/typescript/run.sh).

## Configuration
```typescript
// vite.config.ts — defineConfig from "vitest/config" (vite's own doesn't know the `test` key)
import { defineConfig } from "vitest/config"
import react from "@vitejs/plugin-react"

export default defineConfig({
  plugins: [react()],
  test: {
    globals: true,                    // describe/it/expect/vi without imports; tsconfig "types": ["vitest/globals"]
    environment: "jsdom",             // DOM APIs for component tests
    setupFiles: ["./src/test/setup.ts"],
    css: true,                        // process CSS imports
    allowOnly: false,                 // a committed it.only fails the run instead of silencing its siblings
    retry: 0,                         // no retries to green: a flaky test is a failing test
    coverage: {
      provider: "v8",
      reporter: ["text", "lcov", "json-summary"],
      include: ["src/**/*.{ts,tsx}"],
      exclude: ["src/**/*.test.*", "src/test/**"],
    },
  },
})
```

**Evidence for the pipeline:** the command in `agent_state/config/verify-commands.json` writes JUnit
under the phase's junit directory, for example
`vitest run --reporter=default --reporter=junit --outputFile.junit=agent_state/phases/$PHASE/junit/ui.xml`.
`junit-to-sidecar.py` turns that into the gate's sidecar (`test-results-sidecar.md`).

**Jest** has no `allowOnly` switch. Use `eslint-plugin-jest`'s `no-focused-tests` and
`no-disabled-tests` rules as errors, and `jest --ci` (which refuses to write new snapshots). For JUnit
output use `jest-junit` with `JEST_JUNIT_OUTPUT_FILE=agent_state/phases/$PHASE/junit/ui.xml`.

Default test file names are `*.test.ts(x)` / `*.spec.ts(x)`. Vitest's default `include` doesn't match
`foo_test.ts`, so a file named that way silently never runs.

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
```tsx
import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { UserCard } from "./UserCard"

describe("UserCard", () => {
  it("renders user name", () => {
    render(<UserCard user={{ id: "1", name: "Alice" }} />)
    expect(screen.getByText("Alice")).toBeInTheDocument()
  })

  it("calls onEdit when button clicked", async () => {
    const user = userEvent.setup() // one per test, before render
    const onEdit = vi.fn()
    render(<UserCard user={{ id: "1", name: "Alice" }} onEdit={onEdit} />)

    await user.click(screen.getByRole("button", { name: /edit/i }))
    expect(onEdit).toHaveBeenCalledWith("1")
  })
})
```

## Mocking
```tsx
import { render, screen } from "@testing-library/react"
import { fetchUser } from "../api/client"
import { UserProfile } from "./UserProfile"
import { reportFailure } from "./report"

// Mock a module (hoisted above the imports)
vi.mock("../api/client", () => ({
  fetchUser: vi.fn(),
}))

it("fetches user on mount", async () => {
  vi.mocked(fetchUser).mockResolvedValue({ id: "1", name: "Alice" })

  render(<UserProfile userId="1" />)
  expect(await screen.findByText("Alice")).toBeInTheDocument()
})

// Spy on an existing function
it("reports a failure on stderr", () => {
  const spy = vi.spyOn(console, "error").mockImplementation(() => {})
  reportFailure("sync")
  expect(spy).toHaveBeenCalledWith(expect.stringContaining("failed"))
  spy.mockRestore()
})

// Mock timers
it("fires after a second", () => {
  vi.useFakeTimers()
  const done = vi.fn()
  setTimeout(done, 1000)
  vi.advanceTimersByTime(1000)
  expect(done).toHaveBeenCalledOnce()
  vi.useRealTimers()
})
```

## Testing Hooks
```typescript
import { act, renderHook } from "@testing-library/react"
import { useCounter } from "./useCounter"

it("increments counter", () => {
  const { result } = renderHook(() => useCounter(0))

  act(() => { result.current.increment() })
  expect(result.current.count).toBe(1)
})
```

## Snapshot Testing
```tsx
import { render } from "@testing-library/react"
import { Badge } from "./Badge"
import { formatDate } from "../utils/format"

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
- Put the TC ID at the start of the test title: `it("TC-UI-20107 shows a skeleton while loading", …)` (`test-case-traceability.md`)
- API mocks (MSW) are typed from the envelope (`msw.md`); `vi.mock` of the API client is for unit tests of non-UI modules only
- Snapshots never replace behaviour assertions. A snapshot update needs a `TEST-CHANGE <date> phase <N>: <why>` comment above the `toMatchSnapshot`/`toMatchInlineSnapshot` call, and a changed `.snap` file is recorded in `test-changes.json` (`test-case-traceability.md` §Changing an existing test)
- Use `screen.getByRole` over `getByTestId` — tests should mirror how users interact
- Use `userEvent` over `fireEvent` — it simulates real browser behavior (focus, blur, typing)
- Use `findBy*` (async) for elements that appear after state updates or fetches
- Never test implementation details (internal state, private methods) — test behavior
- Use `vi.fn()` for callbacks, `vi.mock()` for modules, `vi.spyOn()` for partial mocks

> Config blocks checked 2026-09-30 (`bash tests/archetype-compile/config-packs/run.sh --live`): 1 bash block: bash -n (macOS bash 3.2.57) + shellcheck 0.11.0.
