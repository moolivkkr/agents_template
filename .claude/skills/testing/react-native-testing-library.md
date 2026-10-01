# React Native Testing Library (RNTL) — component and integration tier

> Code samples compile-checked: tsc (TypeScript 7.0.2, strict + noUncheckedIndexedAccess) against react-native 0.87.1, RNTL 14.0.1 and msw 2.15.0; the Jest config, setup, providers and the 4-state, userEvent and accessibility tests ran (5 tests, Jest 29.7, @react-native/jest-preset 0.87.1); the navigation excerpt type-checked only (`tests/archetype-compile/ui-packs/run.sh`, 2026-09-30).

Jest + `@testing-library/react-native` for testing RN screens and components in Node, with no
device. This is where most mobile coverage belongs. Strategy and tier map: `mobile-testing-strategy.md`.

> **Version note (verified 2026-09-29).** RNTL v14 (June 2026) requires React 19+ and makes `render`,
> `fireEvent` and `act` **async**: you must `await` them. It removed `renderAsync`, `update`,
> `getQueriesForElement` and the `UNSAFE_*` queries. Queries return host elements only, and text must
> be inside `<Text>`. On RNTL v13 or earlier the same tests work without the `await` on `render`, so
> check `package.json` before writing tests. Codemods exist for v13 → v14.

## Setup

```js
// jest.config.js — RN >= 0.85 uses the extracted preset
module.exports = {
  preset: '@react-native/jest-preset',   // Expo projects: preset: 'jest-expo'
  setupFilesAfterEnv: ['./jest.setup.ts'],
  // msw@2's `msw/node` export maps the preset's "react-native" condition to null; "node" lets Jest find it
  testEnvironmentOptions: { customExportConditions: ['node', 'require', 'react-native'] },
  // msw@2's ESM-only dependencies ship .mjs files: run them through Babel like the app's code
  transform: { '^.+\\.(js|mjs|ts|tsx)$': 'babel-jest' },
  transformIgnorePatterns: [
    'node_modules/(?!((jest-)?react-native|@react-native(-community)?|expo(nent)?|@expo|react-navigation|@react-navigation|@shopify/flash-list|rettime|until-async|@open-draft)/)',
  ],
};
```

Verified 2026-09-30 on RN 0.87.1, Jest 29.7 (what the RN 0.87 app template pins), RNTL 14.0.1 and msw 2.15.0:
without those three settings `msw/node` is not found, then fails to parse. **Pin `msw@^2` for this tier:**
MSW 3 is ESM-only and its interceptors use `import.meta`, which this CommonJS setup can't load (see "MSW for
React Native" below). `@shopify/flash-list` v2 also ships untranspiled ESM, so it is in the pattern.

```tsx
// test/providers.tsx — every screen test renders inside this. A fresh QueryClient per test; no retries (a
// retried 503 would hide the error state); gcTime Infinity, so no 5-minute GC timer keeps Jest running.
import { useState, type ReactNode } from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

export function TestProviders({ children }: { children: ReactNode }) {
  const [client] = useState(() => new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: Infinity } } }));
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}
```

Matchers such as `toBeOnTheScreen`, `toHaveTextContent`, `toBeVisible`, `toHaveAccessibleName`,
`toBeDisabled`, `toBeChecked` and `toHaveStyle` are built into RNTL v12.4+. Do not add
`@testing-library/jest-native`.

## Query priority (accessibility-first)

1. `getByRole('button', { name: 'Save' })`: proves the element is reachable by screen readers too.
2. `getByLabelText('Email')`: form inputs.
3. `getByText('Welcome back')`: non-interactive content.
4. `getByTestId('orders.list')`: only when there is no accessible name. Use the testID contract.

If you cannot find an interactive element with `getByRole`, that is an accessibility defect. Record
it as a `TC-MA11Y-*` failure; do not fall back silently to `getByTestId`.

## Component test — the 4 states (TC-MCMP-*)

Every screen is tested in **loading, error, empty and data** states, the same as the web
`ui_test_agent`.

Mock bodies come from the typed envelope helpers in `msw.md` (`ok`, `page`, `apiError`), so a
mock that drifts from `api/response-envelope.md` fails to type-check. The TC ID goes in the test
title, where the JUnit report carries it (`test-case-traceability.md`).

```tsx
import { render, screen, userEvent } from '@testing-library/react-native';
import { http } from 'msw';
import { server } from '../test/msw-server';
import { page, apiError } from '../test/envelope';        // typed helpers (msw.md)
import { orderFixture } from '../test/fixtures';
import { TestProviders } from '../test/providers';       // a screen with TanStack Query needs its provider
import { OrdersScreen } from './OrdersScreen';

test('TC-MCMP-20112 renders orders from GET /api/v1/orders (data state)', async () => {
  server.use(http.get('*/api/v1/orders', () => page([orderFixture({ id: 'o1', total_cents: 4200, status: 'open' })])));
  await render(<OrdersScreen />, { wrapper: TestProviders });
  expect(await screen.findByText('Order o1')).toBeOnTheScreen();
});

test('TC-MCMP-20113 shows the empty state when data is []', async () => {
  server.use(http.get('*/api/v1/orders', () => page([])));
  await render(<OrdersScreen />, { wrapper: TestProviders });
  expect(await screen.findByText(/no orders yet/i)).toBeOnTheScreen();
});

test('TC-MCMP-20114 shows a retry on 503 UNAVAILABLE', async () => {
  server.use(http.get('*/api/v1/orders', () => apiError(503, 'UNAVAILABLE', 'Try again shortly.')));
  await render(<OrdersScreen />, { wrapper: TestProviders });
  expect(await screen.findByRole('button', { name: /retry/i })).toBeOnTheScreen();
});
```

## Interactions — prefer `userEvent`

```tsx
jest.useFakeTimers();                       // press() waits ~130ms of real time, so fake timers keep tests fast
const user = userEvent.setup();
await render(<LoginScreen />);
await user.type(screen.getByLabelText('Email'), 'a@b.co');
await user.press(screen.getByRole('button', { name: 'Sign in' }));
expect(await screen.findByText('Welcome')).toBeOnTheScreen();
```

`userEvent` runs the full press/type event sequence (pressIn → press → pressOut, focus, change).
`fireEvent` fires one handler and misses bugs in the others. Use `fireEvent` only for events
`userEvent` doesn't cover (e.g. `fireEvent.scroll` with a custom payload).

## MSW for React Native

```ts
// test/msw-server.ts — Jest runs in Node, so use msw/node here
import { setupServer } from 'msw/node';
export const server = setupServer();

// jest.setup.ts
import { server } from './test/msw-server';
beforeAll(() => server.listen({ onUnhandledRequest: 'error' }));   // msw@2's name (MSW 3: onUnhandledFrame)
afterEach(() => server.resetHandlers());
afterAll(() => server.close());
```

Jest tests run in Node, so `msw/node` is the correct entry point for the component and integration
tiers, with **`msw@^2`** and the three Jest settings in §Setup. MSW 3 (3.0.0, 2026-09-28) does not load
under `@react-native/jest-preset`: it ships ESM only, and even with msw and its dependencies transformed,
`@mswjs/interceptors` stops at `import.meta.url` (checked with msw 3.0.1 on 2026-09-30). The separate
`msw/native` entry (in-app mocking, e.g. for demos) also exists only in 2.x; MSW 3 removed it.
`onUnhandledRequest: 'error'` makes an un-mocked call fail the test instead of reaching a real server.
When MSW 3 becomes loadable here, the option is named `onUnhandledFrame` (`testing/msw.md`), and the old
key is ignored rather than rejected at run time, so rename it in the same change.

## Navigation

Render the screen inside a real `NavigationContainer` with the real navigator, and assert on the
destination screen's content. Do not assert on mocked `navigate` calls: that tests your mock, not
the navigation.

```tsx
await render(<NavigationContainer><RootStack /></NavigationContainer>);
await user.press(screen.getByRole('button', { name: 'View order o1' }));
expect(await screen.findByRole('header', { name: 'Order o1' })).toBeOnTheScreen();
```

## Native modules

Use each library's official Jest mock (AsyncStorage, react-native-reanimated/mock,
@react-native-community/netinfo/jest). Anything that needs a real native implementation, such as
camera, biometrics, push or secure storage, belongs in the device tier (`TC-MPLT-*`).

## Accessibility assertions in the component tier (TC-MA11Y-*)

```tsx
const save = screen.getByRole('button', { name: 'Save order' });
expect(save).toHaveAccessibleName('Save order');
expect(save).not.toBeDisabled();
```

Also enforce at lint time with `eslint-plugin-react-native-a11y`. RNTL can't measure touch-target
size or contrast (Node has no layout engine), so those are checked on the device by
`mobile_platform_auditor`.

## Render performance (optional, TC-MPERF-*)

`reassure` (Callstack) measures render count and duration against a baseline branch. Use it for list
screens and anything the BRD has an NFR-PERF target for.

## Anti-patterns

- Snapshot tests as the only assertion: they pass whatever is rendered. Assert on behaviour.
- `getByTestId` everywhere: it hides missing accessible names.
- Asserting `jest.fn()` navigation mocks were called: prove the destination rendered instead.
- Forgetting `await` on `render` / `userEvent` with RNTL v14: the test passes vacuously before the UI settles.
- Inventing mock response shapes: copy them from `api-contracts.md`.
