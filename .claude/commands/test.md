---
command: test
description: Run tests standalone — unit, integration, or e2e. Can target a specific phase or run all.
arguments:
  - name: phase
    required: false
    description: "Target phase (e.g. --phase=2). Omit to run all completed phases."
  - name: unit
    required: false
    default: false
    description: "Run unit tests only"
  - name: integration
    required: false
    default: false
    description: "Run integration tests only (Testcontainers; needs a container runtime)"
  - name: e2e
    required: false
    default: false
    description: "Run the e2e tier (this phase's TC-E2E rows + every earlier phase's committed e2e specs) against APP_BASE_URL"
  - name: workflow
    required: false
    description: "Run e2e specs whose title contains this text (e.g. --workflow=TC-E2E-20101); a filtered run is never gate evidence"
  - name: acceptance
    required: false
    default: false
    description: "Run the committed acceptance specs (tests/acceptance/) as each persona"
  - name: persona
    required: false
    description: "Run acceptance for a specific persona (e.g. --persona='Admin User'); a filtered run is never gate evidence"
  - name: performance
    required: false
    default: false
    description: "Run the open-model k6 load test against NFR-PERF targets on the deployed build"
  - name: system
    required: false
    default: false
    description: "Run whole-system checks on the deployed environment: build identity, readiness semantics, rolling restart and DB restart under load, idempotent migrate/seed, exit criteria"
  - name: manual
    required: false
    default: false
    description: "Generate manual test scripts and SRE drill scripts (game day, DR restore, failover) for a human to execute"
  - name: traceability
    required: false
    default: false
    description: "Run the TC-* inventory (tc-inventory.py) — spec IDs vs tests NAMED with them (and, with results, that ran and passed)"
  - name: mobile
    required: false
    default: false
    description: "Run the React Native tiers: Jest+RNTL (via test_runner) and device flows on iOS simulator + Android emulator (via mobile_e2e_orchestrator)"
  - name: platform
    required: false
    description: "With --mobile: restrict device flows to one platform (ios | android). Default: both. A single-platform run can never satisfy a phase gate."
---

# /test — Standalone Test Runner

Runs tests outside of `/develop`. Useful after a hotfix, for running e2e on demand, or for regression
testing before a release.

**Same rules as the pipeline.**
- Commands come only from `agent_state/config/verify-commands.json`, generated from
  IMPLEMENTATION_GUIDELINES §Commands and versions (`skills/core/commands-and-versions.md`).
- Every tier writes runner JUnit and an `sdlc.test-results/v1` sidecar
  (`skills/testing/test-results-sidecar.md`).
- Browser, device, acceptance, performance and system tiers run against the **deployed** build,
  `APP_BASE_URL`.

---

## Flake policy (every tier)

- **No retries to green.** Playwright `retries: 0` + `failOnFlakyTests: true`, Vitest `retry: 0`, no
  `gotestsum --rerun-fails`, no `pytest --reruns`.
- A test that fails and then passes is **FLAKY**. `junit-to-sidecar.py` counts it in `flaky`, and flaky
  > 0 fails the tier, and the gate.
- Fix the cause: shared data, time, ordering, unawaited async, or a real race in the product.
- Quarantine only with an issue link and an `expires` date ≤ 14 days, in the sidecar's
  `quarantined[]`. Never with a silent skip. An expired quarantine fails the gate again.
- Go runs with `-count=1` (no cached results), and with `-race` where cgo allows.

---

## Step 0 — Orient

```bash
# Phases to test: the argument, or every phase with a passed gate
if [ -n "$ARG_PHASE" ]; then
  PHASES="$ARG_PHASE"
else
  PHASES=$(ls agent_state/phases/*/gate.passed 2>/dev/null | sed -E 's#.*/phases/([0-9]+)/gate\.passed#\1#' | sort -n)
fi

# Tiers: the flags given, or all tiers when none is given
ANY="$ARG_UNIT$ARG_INTEGRATION$ARG_E2E$ARG_ACCEPTANCE$ARG_PERFORMANCE$ARG_SYSTEM$ARG_MANUAL$ARG_TRACEABILITY$ARG_MOBILE"
flag() { [ "${1}" = true ] || [ -z "$ANY" ]; }
flag "$ARG_UNIT" && RUN_UNIT=true
flag "$ARG_INTEGRATION" && RUN_INTEGRATION=true
flag "$ARG_E2E" && RUN_E2E=true
flag "$ARG_ACCEPTANCE" && RUN_ACCEPTANCE=true
[ "$ARG_PERFORMANCE" = true ] && RUN_PERFORMANCE=true      # explicit only: a load test is never implied
[ "$ARG_SYSTEM" = true ] && RUN_SYSTEM=true                # explicit only: it injects faults into qa
[ "$ARG_MANUAL" = true ] && RUN_MANUAL=true
flag "$ARG_TRACEABILITY" && RUN_TRACEABILITY=true
# Mobile runs when asked, or by default when the project has a React Native app and no tier flag was given
MOBILE_ENABLED=$(jq -r '.tech_profile.mobile.enabled // false' agent_state/agent_registry.json 2>/dev/null)
{ [ "$ARG_MOBILE" = true ] || { [ -z "$ANY" ] && [ "$MOBILE_ENABLED" = true ]; }; } && RUN_MOBILE=true
PLATFORMS="${ARG_PLATFORM:-ios android}"

# Commands: generated from IMPLEMENTATION_GUIDELINES; nobody guesses
python3 .claude/hooks/commands-table.py docs/IMPLEMENTATION_GUIDELINES.md --out agent_state/config/verify-commands.json \
  || echo "⛔ BLOCKED: IMPLEMENTATION_GUIDELINES has no usable '## Commands and versions' table"
```

**Where the deployed build is.** The browser, device, acceptance, performance and system tiers need
`APP_BASE_URL`:
- **Lab cluster** (`deploy/k8s/app.env`): `APP_BASE_URL=http://${APP}-qa.localhost:${INGRESS_PORT}`.
  qa must be HEALTHY and carry the current code; run `/deploy` (dev → qa) first if it doesn't.
- **Compose:** `docker compose up -d --build`, then `APP_BASE_URL=http://localhost:${APP_PORT}`
  from IMPLEMENTATION_GUIDELINES.

Pass the literal URL in every spawn prompt below (`BASE URL: <url>`). Subagents don't inherit this
shell's environment.

---

## Step 1 — Unit + Step 2 — Integration + UI component + RN Jest

**Agent:** `test_runner` (`subagent_type: test_runner`). It RUNS existing tests and never writes or
edits one. The generated writers (`unit_test_agent`, `integration_test_agent`, `ui_test_agent`,
`mobile_test_agent`) are used only when `--traceability` shows missing TC IDs and you choose to
fill them.

Prompt: "BASE URL: <url or n/a>. Phase <N>. Run the tiers <unit|integration|ui|mobile> with ONLY
agent_state/config/verify-commands.json, per your procedure. Refresh each tier sidecar and write
reports/test_results.md + test_results.json."

Results: `agent_state/phases/N/reports/test_results.md` + `.json`, and the refreshed tier sidecars.

---

## Step 3 — E2E

**Agent:** `e2e_orchestrator` (`subagent_type: e2e_orchestrator`). The generated `ui_test_agent`
writes the web browser specs. For CLI, library and pipeline products, `e2e_orchestrator` writes them.
**When:** `RUN_E2E = true`.

Scope: this phase's `Tier: e2e` inventory rows, plus the full committed e2e suite as regression.
The agent preflights `GET <BASE URL>/healthz` and the deployed code sha, and reports BLOCKED if
either is wrong. It runs once with retries 0, and keeps traces and screenshots for failures.
`--workflow=<text>` passes a title filter; a filtered run is diagnosis only, never gate evidence.

Results: `agent_state/phases/N/reports/e2e_results.md` + `e2e_results.json` (a copy of the markdown goes
to `agent_state/e2e/results.md`). App failures are listed for the owning developer; the agent fixes
tests only.

---

## Step 3-M — Mobile (React Native, iOS + Android) — when `RUN_MOBILE = true`

1. **Node tiers** (Jest + RNTL component/integration, `commands."x:mobile-jest"`): `test_runner`, as
   in Step 1. No device needed.
2. **Device tiers** (TC-ME2E / TC-MPLT / TC-MVIS / TC-MPERF): spawn `mobile_e2e_orchestrator`
   (`subagent_type: mobile_e2e_orchestrator`) with `PLATFORMS=${PLATFORMS}` and `BACKEND: <APP_BASE_URL>`.
   - It builds release binaries and boots the device matrix from IMPLEMENTATION_GUIDELINES §Mobile.
   - It runs every flow from every completed phase's `mobile_test_agent` manifest, with
     `commands."test:mobile"`.
   - It writes `agent_state/phases/N/reports/mobile_e2e_results.md` + `.json` (platform-tagged cases).
   - Backend: the iOS simulator uses `APP_BASE_URL` as is. The Android emulator reaches the Mac's
     loopback as `10.0.2.2`, with the same port and the original host in a `Host` header.
3. iOS needs a macOS host with Xcode. On any other host the iOS cases are `UNTESTED`, with the platform
   `BLOCKED — requires macOS`. That is reported, not skipped silently.

With `--platform=ios|android` only that platform runs. The report header says so, and the result
can't be used as gate evidence, which needs both platforms.

---

## Step 3b — Acceptance

**Agent:** `acceptance_test_agent` (`subagent_type: acceptance_test_agent`)
**When:** `RUN_ACCEPTANCE = true` (explicit `--acceptance` flag, or no tier flags = run all)

- Runs the **committed** acceptance specs (`tests/acceptance/`, tests named `TC-ACC-…`) against
  `BASE URL`, with `commands."x:acceptance"`. It first writes any missing ones for in-scope FR criteria.
- Seeds reference data only through the app's seed command/job, and persona data through the product
  API with run-unique identifiers. Credentials come from the environment.

Results: `agent_state/phases/N/reports/acceptance_report.md` + `acceptance_report.json` (one case per
TC-ACC, `use_cases[]`). `--persona` filters the run; a filtered run is never gate evidence.

---

## Step 3c — Performance (when --performance flag)

**Agent:** `performance_agent` (`subagent_type: performance_agent`)

Runs an **open-model** k6 test (`constant-arrival-rate`) against `BASE URL` for every in-scope
NFR-PERF target:
- at the NFR's rate, with thresholds = the NFR's limits, plus `dropped_iterations == 0`;
- after a warm-up, for at least 5 minutes.

It doesn't "recommend" a load test.

Results: `agent_state/phases/N/reports/performance_results.md` + `performance_results.json` (one HIGH
case per NFR-PERF).

---

## Step 3d — System Tests (when --system flag)

**Agent:** `system_test_agent` (`subagent_type: system_test_agent`)

Whole-system checks on the deployed environment, covering what no other tier owns:
- build identity across every service;
- readiness semantics: a hard dependency down → not ready; a soft one → still ready; liveness never
  checks the DB;
- a rolling restart and an API pod kill under light constant load, with zero errors;
- a DB restart → 503 within the deadline, then recovery without restarting the API;
- idempotent migrate and seed re-runs;
- every PHASE_PLAN exit criterion traced to a passing case.

It restores every fault it injects. On the lab cluster it only ever touches `<app>-qa`. CLI and
library products report `not applicable`.

Results: `agent_state/phases/N/reports/system_test_results.md` + `system_test_results.json`. The
committed script lives in `tests/system/`.

---

## Step 3e — Manual and drill scripts (when --manual flag)

**Agent:** `manual_test_agent` (`subagent_type: manual_test_agent`)

Writes human-executable scripts:
- for scenarios that need judgment or external systems;
- SRE drills (game day, DR restore, failover) when the phase added a datastore, queue, service or
  availability NFR.

Every script records the environment, URL and code sha it runs against. None contains a credential.

Output: `docs/testing/manual/phase-N/` (one file per TC ID) + `INDEX.md`. Every script is
`NOT_EXECUTED` until a human records its result.

---

## Step 3f — TC-* ID Traceability Check (when --traceability flag)

**Agent:** `spec_test_reconciler` (inventory mode only)

Runs the TC-* inventory without running any tests. Useful for checking coverage gaps before a full
test run.

```bash
# Deterministic inventory (skills/testing/test-case-traceability.md): an ID counts only when a test NAMED
# with it exists and isn't skipped; with --results, only when that test ran and PASSED.
OUT="agent_state/reconciliation/phase-${PHASE}/test_case_inventory.json"
R="agent_state/phases/${PHASE}/reports"
RESULTS=$(ls "$R"/test_results.json "$R"/mobile_e2e_results.json "$R"/acceptance_report.json \
             "$R"/performance_results.json "$R"/system_test_results.json 2>/dev/null)
BASE="$(cat agent_state/phases/${PHASE}/base_sha 2>/dev/null)"
python3 .claude/hooks/tc-inventory.py --phase "${PHASE}" ${RESULTS:+--results $RESULTS} ${BASE:+--diff-base "$BASE"} --out "$OUT"
jq -r --arg p "${PHASE}" '"TC-* Inventory — Phase \($p) (\(.mode) mode): \(.passed)/\(.total) HIGH+MEDIUM covered",
       "  missing:        \(.missing | join(", "))",
       "  failing:        \(.failing | join(", "))",
       "  skipped-only:   \(.skipped_only | join(", "))",
       "  comment-only:   \(.comment_only | join(", "))   (IDs in comments do not count — put them in test names)",
       "  duplicate IDs:  \(.duplicate_ids | keys | join(", "))",
       "  weakening:      \(.weakening_unacknowledged | map("\(.file) \(.kind)") | join("; "))"' "$OUT"
jq -r '.cases | group_by(.name | capture("TC-(?<c>[A-Z0-9]+)-").c) | .[] |
       "    \(.[0].name | capture("TC-(?<c>[A-Z0-9]+)-").c): \(map(select(.verdict=="PASS")) | length)/\(length)"' "$OUT"
```

Output: `agent_state/reconciliation/phase-${PHASE}/test_case_inventory.md`, written by
`spec_test_reconciler` from the JSON.

---

## Step 4 — Report

Every number below comes from a sidecar (`jq '{verdict,total,passed,failed,flaky}' <file>.json`), never
from an agent's prose.

```
Test Results — Phase(s): N — code <sha> — base URL <APP_BASE_URL or n/a>

  Unit:           verdict · passed/total · flaky        (reports/unit_tests.json)
  Integration:    …                                     (reports/integration_tests.json)
  UI component:   …                                     (reports/ui_test_results.json)
  E2E:            …                                     (reports/e2e_results.json)
  Mobile device:  iOS … · Android …                     (reports/mobile_e2e_results.json)
  Acceptance:     N/N use cases · personas N            (reports/acceptance_report.json)
  Performance:    N/N NFR-PERF targets met              (reports/performance_results.json)
  System:         …                                     (reports/system_test_results.json)
  TC inventory:   N/N HIGH+MEDIUM ran and passed        (reconciliation/phase-N/test_case_inventory.json)

  Failures (if any):
    ❌ <TC ID / test name> — <failure reason>
       Reproduction: <minimal reproduction steps / trace path>

  ▶ After all phases complete: /accept (global full-product acceptance)
```
