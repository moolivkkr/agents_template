# Detox — gray-box device E2E for React Native

> Code samples compile-checked: `.detoxrc.js` and the test: tsc (TypeScript 7.0.2, strict + noUncheckedIndexedAccess) against detox 20.51.4's types only; nothing ran on a simulator or emulator (`tests/archetype-compile/ui-packs/run.sh`, 2026-09-30).

Wix's E2E framework. Unlike Maestro, Detox is linked into the app and **synchronises with it**: it
waits for the JS thread, network requests, timers and animations to go idle before each action, so
tests are less flaky on busy apps. The cost is a tight coupling to the RN version.
Strategy and tool choice: `mobile-testing-strategy.md` §3.

> **Version window: check before choosing (verified 2026-09-29).** Detox 20.51.x officially
> supports **RN 0.77–0.84** with the New Architecture. The current RN release is 0.87; newer versions
> "may work" but are unsupported. iOS real devices are **not supported** (simulators only). Expo
> projects need `expo prebuild` plus Expo's Detox config plugin.
> **Rule:** if `rn_version` in `agent_registry.json` is outside the officially supported window,
> do not adopt Detox without a recorded decision (`docs/DECISIONS.md`) backed by a passing spike.
> Otherwise use Maestro.

## Configuration

```js
// .detoxrc.js
/** @type {Detox.DetoxConfig} */
module.exports = {
  testRunner: { args: { $0: 'jest', config: 'e2e/jest.config.js' }, jest: { setupTimeout: 180000 } },
  apps: {
    'ios.release': {
      type: 'ios.app',
      binaryPath: 'ios/build/Build/Products/Release-iphonesimulator/App.app',
      build: 'xcodebuild -workspace ios/App.xcworkspace -scheme App -configuration Release -sdk iphonesimulator -derivedDataPath ios/build',
    },
    'android.release': {
      type: 'android.apk',
      binaryPath: 'android/app/build/outputs/apk/release/app-release.apk',
      testBinaryPath: 'android/app/build/outputs/apk/androidTest/release/app-release-androidTest.apk',
      build: 'cd android && ./gradlew assembleRelease assembleAndroidTest -DtestBuildType=release && cd ..',
    },
  },
  devices: {
    simulator: { type: 'ios.simulator', device: { type: 'iPhone 16' } },
    emulator: { type: 'android.emulator', device: { avdName: 'Pixel_8_API_36' } },
  },
  configurations: {
    'ios.sim.release': { device: 'simulator', app: 'ios.release' },
    'android.emu.release': { device: 'emulator', app: 'android.release' },
  },
};
```

Android also needs the Detox test instrumentation (`DetoxTest.java` under `androidTest`) and the
`network_security_config` that allows cleartext to `10.0.2.2` for the local backend.

## Run

```bash
detox build -c ios.sim.release && detox test -c ios.sim.release
detox build -c android.emu.release && detox test -c android.emu.release
# evidence on failure
detox test -c ios.sim.release --record-logs failing --take-screenshots failing --record-videos failing --artifacts-location artifacts/ios
# CI: headless Android, reuse the booted simulator
detox test -c android.emu.release --headless --cleanup
```

## Test anatomy

```ts
// e2e/login.test.ts — the TC ID goes in the test title, where the JUnit report carries it
describe('Login', () => {
  beforeAll(async () => {
    await device.launchApp({ newInstance: true, delete: true, permissions: { notifications: 'YES' } });
  });

  it('TC-ME2E-20101 signs in and shows orders', async () => {
    await element(by.id('login.email')).typeText('qa@example.com');
    await element(by.id('login.password')).typeText(process.env.E2E_PASSWORD!);
    await element(by.id('login.submit')).tap();
    await waitFor(element(by.id('orders.list'))).toBeVisible().withTimeout(15000);
  });
});
```

## Platform behaviour recipes (TC-MPLT-*)

| Behaviour | Detox API |
|---|---|
| Deep link (cold) | `await device.launchApp({ newInstance: true, url: 'myapp://orders/o1' })` |
| Deep link (warm) | `await device.openURL({ url: 'myapp://orders/o1' })` |
| Background → foreground | `await device.sendToHome(); await device.launchApp({ newInstance: false })` |
| Kill and relaunch | `await device.terminateApp(); await device.launchApp({ newInstance: true })` (no `delete`) |
| Permissions | `device.launchApp({ permissions: { camera: 'NO', location: 'inuse' } })` (iOS). On Android, grant or revoke via `adb shell pm` |
| Android back | `await device.pressBack()` |
| Location | `await device.setLocation(52.37, 4.89)` |
| Skip sync for a polling URL | `await device.setURLBlacklist(['.*/api/v1/stream.*'])`. Without it, a long-poll never lets Detox go idle and every action times out |

## Sync pitfalls (the usual cause of "Detox is flaky")

- Infinite animations (spinners, Lottie loops) or `setInterval` keep the app busy, so Detox waits
  forever. Stop them in E2E builds, or disable sync around the step with
  `device.disableSynchronization()` and re-enable it straight after.
- Long-lived connections (WebSocket, SSE, polling): add them to `setURLBlacklist`.
- Never "fix" a timeout by raising `withTimeout` to 60s. Find what keeps the app busy
  (`--loglevel trace` shows the busy resource).

## Anti-patterns

- Adopting Detox on an RN version outside its support window without a spike and a decision.
- Debug builds in CI: Metro dependency, LogBox overlays, slow JS.
- `by.text()` selectors on the device tier: use the testID contract.
- Sharing state between `it` blocks without `launchApp({ newInstance: true })`: order-dependent tests.

> Config blocks checked 2026-09-30 (`bash tests/archetype-compile/config-packs/run.sh --live`): 1 bash block: bash -n (macOS bash 3.2.57) + shellcheck 0.11.0.
