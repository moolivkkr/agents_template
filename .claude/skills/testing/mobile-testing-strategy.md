# Mobile Testing Strategy — React Native on iOS + Android

The hub pack for mobile testing. `mobile_test_agent` writes the tests, `mobile_e2e_orchestrator` runs
them on simulators and emulators, and `mobile_platform_auditor` reviews what automation can't prove.
Tool packs: `react-native-testing-library.md` (component tier), `maestro.md` / `detox.md` /
`appium-mobile.md` (device tier), `../frameworks/react-native.md` (platform facts).

> **Currency note (verified 2026-09-29).** React Native 0.87 is current and runs only on the New
> Architecture (Legacy was removed in 0.82). Expo SDK 57 ships RN 0.86. RN 0.87 minimums are iOS 15.1
> and Android minSdk 24. Re-check these against `docs/IMPLEMENTATION_GUIDELINES.md` and
> `reactnative.dev/versions` before relying on them. Tool support lags RN releases: see the Detox
> version window in `detox.md`.

---

## 1. Why mobile needs its own tiers

A web Playwright suite proves nothing about a React Native app. There is no DOM: RN renders native
views, and platform behaviour diverges in ways the JS layer never sees:

| Divergence | iOS | Android | Test that catches it |
|---|---|---|---|
| Back navigation | swipe-from-edge gesture | hardware/gesture back button | device-tier flow per platform |
| Permissions | one-shot prompt, then Settings only | runtime prompt, "don't ask again" | device tier with permission state set |
| Keyboard | covers inputs unless handled | `adjustResize`/`adjustPan` from the manifest | device tier, both platforms |
| Deep links | Universal Links + custom scheme | App Links (verified) + intent filters | device tier `openLink` per platform |
| Background/kill | suspended quickly, state restoration | process death under memory pressure | lifecycle flow: background, kill, relaunch |
| Fonts/text scaling | Dynamic Type | font scale + display size | a11y tier at largest scale |
| Safe areas | notch / Dynamic Island / home indicator | display cutouts, gesture nav bar | screenshot per device class |

**Rule:** every workflow tested on the device tier runs on BOTH platforms. "It passed on iOS" is
half a result. Record per-platform PASS/FAIL separately and never merge them into one status.

## 2. The mobile test pyramid (TC-* tiers)

| Tier | TC prefix | Tool | Runs on | Owner | Speed |
|---|---|---|---|---|---|
| Unit (pure logic, hooks, reducers, formatters) | `TC-UNIT-*` | Jest | Node | `mobile_test_agent` | ms |
| Component (screen renders, 4 states, interactions) | `TC-MCMP-*` | Jest + RNTL | Node (no device) | `mobile_test_agent` | ms–s |
| Integration (screen + mocked API from contracts) | `TC-MINT-*` | Jest + RNTL + MSW v2 | Node | `mobile_test_agent` | s |
| Device E2E (real app binary, both platforms) | `TC-ME2E-*` | Maestro (default) / Detox / Appium | simulator + emulator | written by `mobile_test_agent`, run by `mobile_e2e_orchestrator` | min |
| Platform behaviour (permissions, deep links, lifecycle, offline, push) | `TC-MPLT-*` | device E2E tool | simulator + emulator | same as above | min |
| Accessibility (labels, roles, touch targets, text scaling) | `TC-MA11Y-*` | RNTL queries + device audit | Node + device | `mobile_test_agent` + `mobile_platform_auditor` | s–min |
| Visual (screenshot per screen × device class) | `TC-MVIS-*` | E2E tool screenshots + diff | device | `mobile_e2e_orchestrator` | min |
| Performance (cold start, list scroll FPS, render count) | `TC-MPERF-*` | reassure (render), Flashlight (Android), launch timing | Node + device | `mobile_e2e_orchestrator` | min |

The component tier carries most of the coverage. The device tier covers only what needs a real
binary: navigation between screens, native modules, permissions, deep links, lifecycle, and
per-platform rendering. Do not re-test in Maestro what RNTL already proves.

## 3. Choosing the device-tier tool

| Situation | Choose | Why |
|---|---|---|
| Default for a new RN/Expo app | **Maestro** | Black-box YAML flows, one flow for both platforms, no app instrumentation, not tied to an RN version window, and EAS Workflows has a built-in `maestro` job |
| RN version inside Detox's supported window, and you need gray-box sync (auto-wait on JS/network idle) | **Detox** | Synchronises with the RN bridge and runloop, so tests are less flaky on animation-heavy apps. Check the window first (`detox.md`) |
| Real iOS devices, a device farm (BrowserStack/Sauce/AWS Device Farm), or an app that mixes RN and fully native screens | **Appium** (XCUITest + UiAutomator2) | WebDriver protocol that device farms support. Maestro and Detox run on iOS simulators only |

Record the choice as a decision (`docs/DECISIONS.md`) with its reason. If the RN version is outside
Detox's supported window, choosing Detox is a BLOCKING risk unless the decision records a spike
that proves it works.

## 4. testID contract (what makes every tier addressable)

A shared `testID` convention is what lets one selector work in RNTL, Maestro, Detox and Appium:

- Every interactive element and every assertion target gets `testID="<screen>.<element>"`, e.g.
  `login.email`, `login.submit`, `orders.list`, `orders.row.<id>`. Use kebab or dot style, but the
  same style everywhere.
- The UX wireframe spec lists each screen's testIDs. The `mobile_test_agent` fails a TC it cannot
  address rather than inventing a selector.
- RNTL: prefer `getByRole` / `getByLabelText` (the accessible query proves a11y at the same time).
  Use `getByTestId` only when there is no accessible name.
- Maestro: `id: "login.email"`. Detox: `by.id('login.email')`. Appium: accessibility id `~login.email`
  on iOS. Android exposure of testID as `resource-id` depends on RN version and view type, so confirm
  it in Appium Inspector before writing Android locators.
- Never select by displayed text alone on the device tier. Text changes with locale, and a locale
  switch then breaks every test.

## 5. Device and OS matrix

Keep the matrix in `docs/IMPLEMENTATION_GUIDELINES.md` §Mobile. Minimum viable matrix per CI run:

| Slot | iOS | Android | Purpose |
|---|---|---|---|
| Latest | newest iPhone simulator on the latest iOS in the CI Xcode | Pixel-class emulator on the latest stable API level | current users |
| Minimum | small-screen iPhone (SE class) on the project's `min_ios` | small/low-density emulator on `min_android_api` | old OS + small screen: the layout and API-level bugs |
| Tablet (only if the BRD lists tablet support) | iPad simulator | tablet emulator | split view, orientation |

Every FR-* flow runs on "Latest" for both platforms. "Minimum" runs at least the smoke flows plus
every flow that touches an OS-version-dependent API (permissions, notifications, photo picker,
biometrics).

## 6. What must be tested on a device (the TC-MPLT-* checklist)

Generate one TC per applicable row. `spec_writer` / `ux_designer` enumerate these in `/plan`.

1. **Cold start** — the app launches to the expected first screen with no red-box/LogBox error.
2. **Auth persistence** — log in, kill the app, relaunch: still logged in (token in secure storage, not AsyncStorage).
3. **Background → foreground** — state preserved. On Android, also after process death ("Don't keep activities" or `adb shell am kill`).
4. **Deep link / universal link** — each route in the linking config opens the right screen, cold and warm, logged in and logged out (logged out redirects to login, then continues to the target).
5. **Permission granted / denied / denied-permanently** — each permission the app requests. Denied must show a recoverable path (explain + open Settings), never a dead end.
6. **Offline / flaky network** — the offline state renders, queued actions replay or fail visibly, and nothing spins forever.
7. **Back navigation** — Android hardware back on every screen and iOS swipe-back where enabled. Neither exits the app unexpectedly or skips a confirm-discard dialog.
8. **Keyboard** — every form field stays visible when focused on the smallest device, and submit is reachable.
9. **Orientation / text scale** — at the largest accessibility text size nothing is clipped. Rotation is locked or handled.
10. **Push notification tap** (if in scope) — tapping a notification routes to the right screen from killed and background states.

## 7. Mocking and test data

- **Component/integration tier:** mock HTTP with MSW v2. Bodies are built by the typed envelope
  helpers in `msw.md`, from the generated contract types (`api/response-envelope.md` +
  `docs/design/phases/N/specs/api-contracts.md`), never hand-shaped. Same rule as the web
  `ui_test_agent`. **Pin
  `msw@^2` for React Native.** MSW 3.0.0 (2026-09-28) removed `msw/native` in favour of
  `@msw/react-native`, which could not be found on npm at the time of writing. Mock native modules
  via their official Jest mocks (e.g. `@react-native-async-storage/async-storage/jest/async-storage-mock`).
- **Device tier:** run against `APP_BASE_URL`, the backend Wave 3.5 deployed: qa on lab-cluster
  projects, the compose stack otherwise. How each device reaches it:
  - **iOS simulator** shares the Mac's network, so use `APP_BASE_URL` as is. If the app can't resolve
    `*.localhost`, use `http://127.0.0.1:<port>` and send the original host in the `Host` header.
  - **Android emulator:** its `localhost` is the emulator itself, and the Mac's loopback is
    `10.0.2.2`. Rewrite the host to `10.0.2.2`, **keep the port**, and send the original host in the
    `Host` header. The lab's ingress routes by `Host` (`<app>-qa.localhost`), so without the header
    the request never reaches the app.
  - If the app can't set a `Host` header, `kubectl -n <app>-qa port-forward svc/<api> <fixed-port>:<svc-port>`
    and use `10.0.2.2:<fixed-port>` (Android) / `127.0.0.1:<fixed-port>` (iOS).
  - The release build's network security config (Android) / ATS exception (iOS) must allow cleartext
    to exactly that host, and only in the e2e build variant.
- Seed data through the app's seed command/job and the product API, never through UI steps in every
  test.
- Never point a device-tier test at a shared or production backend.

## 8. Flakiness policy

- Maestro and Detox auto-wait. Adding `sleep`/fixed waits is an anti-pattern. Use
  `extendedWaitUntil` (Maestro) or `waitFor(...).withTimeout()` (Detox) on a specific element.
- A test that passes only on retry is FLAKY. Report it as such with the retry count. Never report it
  as PASS, and never add retries to hide it. A flaky count above 0 in the sidecar fails the gate:
  fix the cause, or quarantine with an issue and an expiry (`test-results-sidecar.md`).
- Reset app state per flow (`clearState` / `launchApp({ delete: true })`) so flows are order-independent.

## 9. Evidence the gate expects

Per platform, per device slot: a JUnit XML report, pass/fail counts, and on failure a screenshot, the
device log (`xcrun simctl spawn booted log` / `adb logcat`), and the JS console. The
`mobile_e2e_orchestrator` report (`agent_state/phases/N/reports/mobile_e2e_results.md`) lists each
mobile TC-M* ID with its iOS result and its Android result as separate columns.
