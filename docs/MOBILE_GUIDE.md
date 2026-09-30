# Mobile Guide — React Native (iOS + Android)

How the framework builds and tests a React Native app alongside (or instead of) a web UI. Every
native screen is implemented once and proven on **both** iOS and Android; a phase that changed
mobile screens cannot pass its gate on one platform.

Source of truth for the details: `.claude/skills/testing/mobile-testing-strategy.md` (strategy,
tool choice, testID contract, device matrix) and `.claude/skills/frameworks/react-native.md`.

---

## 1. Turning mobile on

Mobile is driven by the tech profile, not by a flag on each command.

1. Fill in **IMPLEMENTATION_GUIDELINES §24 Mobile** (template:
   `.claude/skills/core/implementation-guidelines-template.md`): app directory, Expo or bare
   workflow, RN / Expo SDK version, bundle ids, minimum OS, device E2E tool, testID convention,
   device matrix, simulator/emulator build commands, CI runners, permissions, deep links, secure
   storage. Write `Mobile: not applicable` when there is no native app.
2. Run `/startup:init` (or `/startup:init --update_agents` on an existing project). `agent_factory`
   reads §24 into the `mobile:` block of the tech profile (`mobile.enabled = true`) and:
   - generates `mobile_developer` and `mobile_test_agent` from their templates;
   - activates the core agents `mobile_e2e_orchestrator` and `mobile_platform_auditor`.
3. `ci_cd_agent` adds a `mobile.yml` pipeline when §24 is present (see §6 below).

## 2. The mobile agents

| Agent | Kind | Role | Runs in |
|-------|------|------|---------|
| `mobile_developer` | generated (template) | Builds the React Native screens from the screen specs, with the spec's testIDs and a typed client generated from `data-contracts.md`; builds both platforms; writes `mobile_developer/manifest.json` (screens, testIDs, deep links, permissions) | `/develop` Wave 2A.6 |
| `mobile_test_agent` | generated (template) | Writes Jest + RNTL component tests (4 states per screen), MSW-mocked integration tests, and device flows for every unlocked workflow and platform behaviour; runs the Node tiers | `/develop` Wave 3d |
| `mobile_e2e_orchestrator` | core | Builds release binaries for the iOS simulator and Android emulator, boots the device matrix, runs every flow on both platforms (plus earlier phases' flows as regression) with screenshots, device logs and JUnit evidence | `/develop` Wave 3d, `/test --mobile` |
| `mobile_platform_auditor` | core | Audits what tests can't assert: VoiceOver/TalkBack labels, touch targets, text scaling, contrast, permission declarations and denial paths, deep-link/App Link config, secure storage, cleartext/ATS networking, iOS/Android parity. Cites file:line or device evidence | `/develop` Wave 4 |

`ui_standards_auditor` also covers React Native pages (design standards + Stitch baseline), and
`acceptance_test_agent` runs persona flows for mobile-delivered FR-* on both platforms.

## 3. Where mobile sits in `/develop`

When the phase touches mobile screens, Wave 0b adds `mobile_developer`, `mobile_test_agent`,
`mobile_e2e_orchestrator` and `mobile_platform_auditor` to `roster.json` — all four are required.

```
Wave 2A.4  api_developer → specs/api-contracts.md
Wave 2A.6  mobile_developer            (needs 2A.4; may run in parallel with 2A.5 ui_developer)
Wave 3d    mobile_test_agent → mobile_e2e_orchestrator
Wave 3v    test_runner re-runs the React Native Jest suite (not device flows) and cross-checks counts
Wave 3.5   mobile: build binaries, install, cold-launch to the first screen, first API call reaches the backend
Wave 4     mobile_platform_auditor (+ ui_standards_auditor, acceptance on both platforms)
Wave 6     gate
```

The device run needs the backend up. The iOS simulator reaches it at `http://localhost:<port>`;
the Android emulator at `http://10.0.2.2:<port>`. Cleartext to those hosts is allowed in the E2E
build only, never in release config.

**Gate rule:** the Wave 3 verification requires `mobile_e2e_results.json` to show each of `ios` and
`android` not blocked and with at least one executed flow. A platform that could not run is
reported BLOCKED with a reason, never PASS.

## 4. Test tiers and TC-* categories

| Tier | TC category | Tool | Runs on | Written by → run by |
|------|-------------|------|---------|---------------------|
| Component (renders, 4 states, interactions) | `TC-MCMP-*` | Jest + RNTL | Node | `mobile_test_agent` |
| Integration (screen + mocked API from contracts) | `TC-MINT-*` | Jest + RNTL + MSW v2 | Node | `mobile_test_agent` |
| Device E2E (real app binary, both platforms) | `TC-ME2E-*` | Maestro (default) / Detox / Appium | simulator + emulator | `mobile_test_agent` → `mobile_e2e_orchestrator` |
| Platform behaviour (permissions, deep links, lifecycle, offline, push) | `TC-MPLT-*` | device E2E tool | simulator + emulator | same |
| Accessibility (labels, roles, touch targets, text scaling) | `TC-MA11Y-*` | RNTL queries + device audit | Node + device | `mobile_test_agent` + `mobile_platform_auditor` |
| Visual (screenshot per screen × device class) | `TC-MVIS-*` | E2E tool screenshots + diff | device | `mobile_e2e_orchestrator` |
| Performance (cold start, list scroll, render count) | `TC-MPERF-*` | reassure, Flashlight (Android), launch timing | Node + device | `mobile_e2e_orchestrator` |

`ux_designer` writes the mobile TC inventory (Tier 4M) and lists every interactive element's testID
in the screen spec. The TC-ID scanners match `TC-[A-Z0-9]+-NNN` and search `tests/ src/ test/ e2e/
apps/ mobile/`, including Maestro YAML, so digit-bearing categories like `TC-ME2E-*` and
`TC-MA11Y-*` are counted.

### testID contract

Every interactive element and assertion target gets `testID="<screen>.<element>"` (for example
`login.email`, `orders.row.<id>`). The same id is used by RNTL, Maestro (`id:`), Detox (`by.id`) and
Appium (accessibility id). `mobile_test_agent` fails a TC it cannot address instead of inventing a
selector. Never select by displayed text alone on the device tier.

## 5. Choosing the device tool

| Situation | Choose |
|-----------|--------|
| Default for a new RN / Expo app | **Maestro** — black-box YAML flows, one flow for both platforms, not tied to an RN version window |
| RN version inside Detox's supported window and you need gray-box synchronisation | **Detox** |
| Real iOS devices, a device farm, or an app mixing RN and fully native screens | **Appium** (XCUITest + UiAutomator2) |

Record the choice and reason in `docs/DECISIONS.md`. Skill packs: `testing/maestro.md`,
`testing/detox.md`, `testing/appium-mobile.md`, `testing/react-native-testing-library.md`,
`frameworks/react-native-app-patterns.md`.

**Version facts (verified 2026-09-29 in the skill packs; re-check against the project's
`package.json` before relying on them):**
- React Native 0.87 is current and runs only on the New Architecture (Legacy was removed in 0.82).
  Minimums for 0.87: iOS 15.1, Android minSdk 24.
- Detox 20.51.x officially supports RN **0.77–0.84**. Choosing Detox for a newer RN is a BLOCKING
  risk unless a decision records a spike that proves it works.
- MSW 3.0.0 removed `msw/native`. **Pin `msw@^2`** for React Native.

## 6. CI (`mobile.yml`)

Generated by `ci_cd_agent` only when §24 is present:
- `mobile-unit` — Jest + RNTL on ubuntu, every PR.
- `mobile-e2e-android` — ubuntu + KVM emulator matrix (Latest and Minimum API levels), release APK,
  device flows (Maestro: `maestro test --format junit`).
- `mobile-e2e-ios` — macOS runner, `xcodebuild` simulator release build, Latest and Minimum
  simulators, same flows.
- Expo projects may use EAS Build + an EAS Workflows `maestro` job instead of the two e2e jobs.
- JUnit XML, screenshots and device logs are uploaded as artifacts on every run.

## 7. Running mobile tests standalone

```
/startup:test --mobile                    # Jest + RNTL via test_runner, then device flows on both platforms
/startup:test --mobile --platform=ios     # device flows on one platform (diagnostic only —
/startup:test --mobile --platform=android #   a single-platform run never satisfies a phase gate)
```

## 8. Reports

Under `agent_state/phases/N/reports/`:

| Report | From |
|--------|------|
| `mobile_test_results.md` + `mobile_test_agent/manifest.json` | `mobile_test_agent` |
| `mobile_e2e_results.md` + `.json` (per-platform passed/failed/blocked) | `mobile_e2e_orchestrator` |
| `test_results.md` + `.json` (writer-vs-independent counts) | `test_runner` (Wave 3v) |
| `mobile_platform_audit.md` + `.json` | `mobile_platform_auditor` |
| `ui_standards_audit.md` + `.json` | `ui_standards_auditor` |

Mobile screen design (Stitch `deviceType: MOBILE`, phone-frame wireframes) is covered in
[STITCH_DESIGN_GUIDE.md](STITCH_DESIGN_GUIDE.md).
