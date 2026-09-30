# Maestro — black-box device E2E for React Native (default device-tier tool)

YAML flows that drive the installed app on an iOS simulator or Android emulator. One flow file
covers both platforms. Maestro does not instrument the app, so it works with any RN version and with
Expo. Strategy: `mobile-testing-strategy.md`.

> **Verified 2026-09-29:** Maestro CLI 2.11.0. Supported platforms: Android emulators and devices,
> and **iOS simulators only** (no official real-iPhone support; use Appium for that). Requires Java
> 17+. Maestro Studio is now a desktop app. Step names below are standard Maestro commands; confirm
> any unusual step against docs.maestro.dev before relying on it.

## Install and run

```bash
curl -fsSL "https://get.maestro.mobile.dev" | bash      # installs to ~/.maestro/bin
maestro --version
maestro test .maestro/                                  # all flows in the folder
maestro test .maestro/login.yaml                        # one flow
maestro test --device <udid-or-emulator-id> .maestro/   # pick a target when several are booted
# Backend = APP_BASE_URL (the Wave 3.5 deploy). Android: host → 10.0.2.2, same port, original host in a Host header
maestro test -e API_URL="$API_URL_ANDROID" -e API_HOST="$API_HOST" .maestro/
maestro test --format junit --output agent_state/phases/$PHASE/junit/mobile-ios-latest.xml .maestro/   # machine-readable results
maestro test --include-tags smoke .maestro/             # tag-filtered subset
```

The app must already be installed on the target: build it first (see §Builds).

## Flow anatomy

```yaml
# .maestro/TC-ME2E-20101-login.yaml
# TC-ME2E-20101: user signs in with valid credentials and lands on Orders
appId: com.example.app            # iOS bundle id == Android applicationId keeps one flow for both
name: "TC-ME2E-20101 user signs in and lands on Orders"   # JUnit testcase name — must start with the TC ID
tags: [smoke, auth]
# EMAIL / PASSWORD come from `maestro test -e EMAIL=… -e PASSWORD=…` (the run's environment) — never committed here
---
- launchApp:
    clearState: true              # order-independent flows
- tapOn:
    id: "login.email"             # RN testID
- inputText: ${EMAIL}
- tapOn:
    id: "login.password"
- inputText: ${PASSWORD}
- hideKeyboard
- tapOn:
    id: "login.submit"
- extendedWaitUntil:
    visible:
      id: "orders.list"
    timeout: 15000
- assertVisible:
    id: "orders.list"
- takeScreenshot: login-success   # evidence; diffing is done outside Maestro
```

If the iOS bundle id differs from the Android applicationId, keep one flow per platform or pass the
id via `-e APP_ID=...` and use `appId: ${APP_ID}`.

## Reuse and structure

```yaml
# .maestro/subflows/sign-in.yaml — reused by every authenticated flow
appId: ${APP_ID}
---
- tapOn: { id: "login.email" }
- inputText: ${EMAIL}
- tapOn: { id: "login.password" }
- inputText: ${PASSWORD}
- tapOn: { id: "login.submit" }
```
```yaml
- runFlow: subflows/sign-in.yaml
- runFlow:
    when:
      platform: Android
    commands:
      - back                       # Android hardware back
```

Layout: `.maestro/<TC-ID>-<workflow>.yaml` per FR-* workflow, `.maestro/platform/<TC-ID>-<behaviour>.yaml`
for TC-MPLT-*, and `.maestro/subflows/` for shared steps. **The flow file name starts with its TC
ID** (`.maestro/TC-ME2E-20101-login.yaml`), **and so does the flow config's `name:`**
(`name: "TC-ME2E-20101 login"`). Maestro's JUnit report sets each testcase's `id`, `name` and
`classname` to the flow's `name`, so that is how the ID reaches the results sidecar. The file name is
what `tc-inventory.py` reads from source. A comment line alone doesn't count
(`test-case-traceability.md`).

## Platform behaviour recipes (TC-MPLT-*)

| Behaviour | Maestro steps |
|---|---|
| Deep link | `- openLink: myapp://orders/o1` then assert the target screen. Run cold (after `stopApp`) and warm |
| Kill and relaunch (persistence) | `- stopApp` → `- launchApp` (no `clearState`) → assert still signed in |
| Permission denied | `- launchApp: { permissions: { camera: deny } }` → exercise the feature → assert the explain + Settings path |
| Permission granted | `- launchApp: { permissions: { all: allow } }` |
| Android back | `- back` then assert where you land (not app exit, unless intended) |
| Scroll to element | `- scrollUntilVisible: { element: { id: "orders.row.o50" } }` |
| Location | `- setLocation: { latitude: 52.37, longitude: 4.89 }` |
| Offline | Toggle network from the host: Android `adb shell svc wifi disable && adb shell svc data disable`. The iOS simulator has no per-sim network toggle, so test offline iOS in the component tier with MSW network errors, and record that gap |

## Builds for the device tier

| Workflow | iOS simulator build | Android emulator build |
|---|---|---|
| Expo (EAS) | `eas build --profile e2e --platform ios` with `"ios": { "simulator": true }` in eas.json, or `npx expo run:ios --configuration Release` locally | `eas build --profile e2e --platform android` with `"android": { "buildType": "apk" }`, or `npx expo run:android --variant release` |
| Bare RN | `xcodebuild -workspace ios/App.xcworkspace -scheme App -configuration Release -sdk iphonesimulator -derivedDataPath build` → `xcrun simctl install booted build/Build/Products/Release-iphonesimulator/App.app` | `cd android && ./gradlew assembleRelease` → `adb install -r app/build/outputs/apk/release/app-release.apk` |

Test a **Release** build (JS bundled, no Metro, no dev menu). A Debug build hides bundling and
minification bugs and shows LogBox overlays that block taps.

## CI

- **iOS** needs a macOS runner (GitHub `macos-26` is GA with Xcode 26.x and iOS 26 simulators, as of
  2026-02). Boot with `xcrun simctl boot "<device>"`.
- **Android**: `ReactiveCircus/android-emulator-runner` on a Linux runner with KVM, parameterised by
  `api-level` for the min/latest matrix slots.
- **Expo**: EAS Workflows has a built-in `type: maestro` job that runs flows against an EAS build.
- Upload JUnit XML, screenshots and `~/.maestro/tests/<run>/` logs as artifacts on every run, not
  only on failure: the gate needs the evidence.

## Anti-patterns

- `- waitForAnimationToEnd` or fixed sleeps as the default: wait for a specific element instead.
- Selecting by text (`tapOn: "Sign in"`): breaks on copy changes and locales. Use `id:`.
- One mega-flow covering five workflows: one failure hides the other four. One workflow per file.
- Testing only on iOS because the Mac is handy: every workflow runs on both platforms.
