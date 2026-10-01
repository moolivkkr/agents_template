# Appium — WebDriver device E2E (real iOS devices, device farms, hybrid apps)

> Code samples compile-checked: capabilities and locators: tsc (TypeScript 7.0.2, strict + noUncheckedIndexedAccess) against WebdriverIO 9.32 types only; no Appium server or device (`tests/archetype-compile/ui-packs/run.sh`, 2026-09-30).

Use Appium when Maestro or Detox can't do the job:
- the test must run on **real iPhones** (Maestro and Detox support iOS simulators only);
- the tests run on a **device farm** (BrowserStack, Sauce Labs, AWS Device Farm), which speak WebDriver;
- the app mixes RN screens with fully native screens or SDK UIs (payments, auth web views).

Otherwise prefer Maestro (`maestro.md`). Strategy: `mobile-testing-strategy.md` §3.

> **Verified 2026-09-29:** Appium 3.8.0 requires Node `^20.19 || ^22.12 || >=24`. Drivers are
> installed separately: `xcuitest` (iOS) and `uiautomator2` (Android). The driver/Appium major-version
> compatibility (e.g. XCUITest driver ≥10 needing Appium 3) comes from a third-party summary. Check
> `appium driver list --installed` and each driver's changelog before pinning.

## Install

```bash
npm i -D appium webdriverio @wdio/cli
npx appium driver install xcuitest
npx appium driver install uiautomator2
npx appium driver doctor xcuitest       # checks Xcode, WebDriverAgent and signing prerequisites
npx appium driver doctor uiautomator2   # checks ANDROID_HOME, adb and build-tools
npx appium --port 4723
```

## Capabilities

```ts
// Typed by WebdriverIO, so a misspelled capability fails to compile
// iOS simulator
export const iosSimulator = { platformName: 'iOS', 'appium:automationName': 'XCUITest', 'appium:deviceName': 'iPhone 16',
  'appium:platformVersion': '26.0', 'appium:app': '/abs/path/App.app', 'appium:noReset': false } satisfies WebdriverIO.Capabilities;
// Real iPhone — needs a signed .ipa, and WebDriverAgent signing (xcodeOrgId / xcodeSigningId, or a prebuilt WDA)
export const iosDevice = { platformName: 'iOS', 'appium:automationName': 'XCUITest', 'appium:udid': '<device-udid>',
  'appium:app': '/abs/path/App.ipa' } satisfies WebdriverIO.Capabilities;
// Android emulator
export const androidEmulator = { platformName: 'Android', 'appium:automationName': 'UiAutomator2', 'appium:avd': 'Pixel_8_API_36',
  'appium:app': '/abs/path/app-release.apk', 'appium:autoGrantPermissions': false } satisfies WebdriverIO.Capabilities;
```

## Locators

- **iOS**: RN `testID` → `accessibilityIdentifier` → `$('~login.email')` (accessibility id).
- **Android**: whether `testID` shows up as `resource-id` or content-desc depends on RN version and
  view type. **Confirm in Appium Inspector** before writing Android locators, then use
  `$('id=login.email')` or `$('~login.email')` accordingly.
- Avoid XPath: it is slow on iOS and breaks with every layout change.

```ts
// inside it('TC-ME2E-20101 signs in and shows orders', …) — the ID goes in the test title
await $('~login.email').setValue(process.env.E2E_BUYER_EMAIL!);   // set by the seed step; never a literal
await $('~login.submit').click();
await $('~orders.list').waitForDisplayed({ timeout: 15000 });
```

## Platform behaviour (TC-MPLT-*)

| Behaviour | Appium |
|---|---|
| Deep link | `driver.execute('mobile: deepLink', { url, package })` (Android) / `driver.url('myapp://...')` (iOS) |
| Background | `driver.execute('mobile: backgroundApp', { seconds: 5 })` |
| Kill / relaunch | `driver.terminateApp(bundleId)` → `driver.activateApp(bundleId)` |
| Android back | `driver.back()` |
| Permissions | iOS: `mobile: setPermission`. Android: `autoGrantPermissions: false`, then accept or deny the system dialog by locator |
| iOS accessibility audit | XCUITest's `performAccessibilityAudit()` (iOS 17+) is an XCTest API, so run it from a native XCUITest target rather than from Appium |

## Anti-patterns

- Appium for a plain RN app on simulators only: Maestro does it with less setup and less flakiness.
- Implicit waits set globally to 30s: use explicit `waitForDisplayed` on specific elements.
- Running the full suite on a paid device farm per commit: run smoke there, and the full suite on
  simulators and emulators.

> Config blocks checked 2026-09-30 (`bash tests/archetype-compile/config-packs/run.sh --live`): 1 bash block: bash -n (macOS bash 3.2.57) + shellcheck 0.11.0.
