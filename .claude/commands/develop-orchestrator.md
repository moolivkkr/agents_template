---
command: develop-orchestrator
description: "Wave-by-wave orchestration for /develop. The PARENT session follows this script, spawning separate agents per wave. This prevents the single-agent problem where reviews get dropped."
arguments:
  - name: phase
    required: false
    description: "Phase number. Omit to auto-detect."
---

# /develop Orchestrator — Wave-by-Wave Execution

**⛔ THIS command is executed by the PARENT session directly — NOT delegated to a subagent.**

The parent reads this script and executes each wave as a separate Agent tool call, verifying outputs between waves. This is the structural enforcement that prevents review/acceptance steps from being dropped.

---

## Auto-Checkpoint Protocol (inspired by agentmemory hook patterns)

Between EVERY wave boundary, the parent session automatically captures a lightweight checkpoint. This eliminates the need for explicit `/pause` — if context resets mid-pipeline, `/resume` can reconstruct state from the last checkpoint.

**Checkpoint format:** `agent_state/phases/${PHASE}/checkpoints/wave-${N}.json`

```json
{
  "ts": "<ISO timestamp>",
  "phase": N,
  "wave_completed": N,
  "wave_next": N+1,
  "git_sha": "<short SHA>",
  "artifacts_produced": ["<paths written this wave>"],
  "findings_summary": "<1-2 lines from wave output>",
  "tests_passing": true|false|null,
  "blocking_issues": []
}
```

**Write checkpoint AFTER each wave verification passes:**
```bash
mkdir -p "agent_state/phases/${PHASE}/checkpoints"
cat > "agent_state/phases/${PHASE}/checkpoints/wave-${WAVE_NUM}.json" << EOF
{
  "ts": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "phase": ${PHASE},
  "wave_completed": ${WAVE_NUM},
  "wave_next": $((WAVE_NUM + 1)),
  "git_sha": "$(git rev-parse --short HEAD)",
  "artifacts_produced": [<list files created this wave>],
  "findings_summary": "<extract from agent result>",
  "tests_passing": null,
  "blocking_issues": []
}
EOF
```

**On `/resume` detection:** If `checkpoints/wave-N.json` exists but `wave-$((N+1)).json` does not, resume from Wave N+1 without re-running earlier waves.

**Key difference from agentmemory:** These are deterministic structural checkpoints (known paths, known schema), not semantic observations. No retrieval search needed — the resume logic reads the latest checkpoint file directly.

---

## Context Pressure Check — MANDATORY Between Every Wave

**⛔ After writing each wave checkpoint, BEFORE starting the next wave, assess context pressure.**

Performance degrades sharply at ~80% context utilization. The 75% threshold gives a 5% safety margin.

### How to detect 75% context pressure

Claude Code does NOT expose a `context_percentage` variable. Use these **concrete proxy signals** to self-assess:

1. **Wave count heuristic** — if you have completed **3+ waves** with subagent spawns, you are likely near or past 75%. Each wave with a subagent adds ~15-25K tokens (prompt + result).
2. **System compression warnings** — if the system has already compressed prior messages (you'll see "[earlier messages compressed]" or similar), you are past 75%.
3. **Conversation length** — if this orchestrator session has made **15+ tool calls** (reads, writes, agent spawns combined), trigger compaction proactively.
4. **Cumulative token estimate** — track approximate tokens consumed:
   - Each subagent spawn + result: ~20K tokens
   - Each file read: ~2-5K tokens
   - Each checkpoint write: ~1K tokens
   - **Trigger at estimated 150K tokens consumed** (75% of 200K window)

**Rule: when in doubt, compact.** The cost of an unnecessary compaction is ~5 seconds. The cost of degraded output quality at 80%+ is wrong code, missed reviews, and dropped steps.

### Protocol — what to do when context pressure is detected

**At every wave boundary (after checkpoint, before next wave):**

1. **Assess** — apply the heuristics above. If any signal triggers:

2. **Write compact context summary** — this file is the post-compact bootstrap. It must be **self-contained** — after `/compact`, the orchestrator reads ONLY this file + `phase_context.md` to know what happened and what's next:
   ```bash
   mkdir -p "agent_state/phases/${PHASE}/checkpoints"
   cat > "agent_state/phases/${PHASE}/checkpoints/compact-context.md" << EOF
   # Compact Context — Phase ${PHASE} (post-Wave ${WAVE_NUM})
   Generated: $(date -u +%Y-%m-%dT%H:%M:%SZ)
   Reason: context pressure detected — compacted before Wave $((WAVE_NUM + 1))

   ## RESUME INSTRUCTIONS
   After /compact, read THIS file + docs/design/phases/${PHASE}/phase_context.md.
   Then continue directly to Wave $((WAVE_NUM + 1)) of the develop-orchestrator.
   Do NOT re-run Waves 1-${WAVE_NUM}. Do NOT re-read files already summarized below.

   ## Phase Goal
   <1 line from phase_context.md>

   ## Completed Waves
   - Wave 1 (Orient + Audit): <summary> — artifacts: [agent_state/phases/${PHASE}/audit_report.md]
   - Wave 2 (Implement): <summary> — artifacts: [<list source files>]
   ...repeat for each completed wave, pulling from checkpoint JSONs...

   ## Key Decisions Made This Session
   - <architectural decisions, pattern choices, deviations from spec>
   - <e.g., "Used repository pattern with interface DI per IMPL_GUIDELINES">

   ## Blocking Issues
   - <none, or list with severity>

   ## Current State
   - Git SHA: $(git rev-parse --short HEAD)
   - Tests: <passing/failing/not-yet-run>
   - Files modified this session: $(git diff --name-only HEAD~${WAVE_NUM} HEAD 2>/dev/null | wc -l | tr -d ' ') files

   ## Next Steps
   - Wave $((WAVE_NUM + 1)): <what this wave does — copy from orchestrator>
   - Remaining waves after that: <list>
   EOF
   ```

3. **Update checkpoint with compaction marker:**
   ```bash
   # Read existing checkpoint, add compaction flag
   python3 -c "
   import json, sys
   with open('agent_state/phases/${PHASE}/checkpoints/wave-${WAVE_NUM}.json') as f:
       data = json.load(f)
   data['compacted_before_next'] = True
   data['compact_context_path'] = 'agent_state/phases/${PHASE}/checkpoints/compact-context.md'
   with open('agent_state/phases/${PHASE}/checkpoints/wave-${WAVE_NUM}.json', 'w') as f:
       json.dump(data, f, indent=2)
   " 2>/dev/null || true
   ```

4. **Announce and compact:**
   ```
   ⚡ Context pressure detected after Wave ${WAVE_NUM} — compacting before Wave $((WAVE_NUM + 1)).
      State saved: agent_state/phases/${PHASE}/checkpoints/compact-context.md
      Resuming inline after compaction.
   ```
   Then run `/compact`.

5. **Post-compact bootstrap** — immediately after `/compact` completes:
   - Read `agent_state/phases/${PHASE}/checkpoints/compact-context.md` (the RESUME INSTRUCTIONS section tells you exactly what to do)
   - Read `docs/design/phases/${PHASE}/phase_context.md` (tech stack, conventions, acceptance criteria)
   - Continue to Wave $((WAVE_NUM + 1)) — do NOT restart earlier waves

### Key rules
- **Never compact mid-wave** — only at wave boundaries after the checkpoint is written
- **When in doubt, compact** — false positive costs 5 seconds; false negative costs quality
- **Compact inline, don't break the session** — compaction is a mid-session refresh, not a reason to stop and `/resume`
- **compact-context.md is the source of truth post-compact** — it replaces conversation scrollback. That's why it includes RESUME INSTRUCTIONS at the top.
- **If compaction happens, say so:** `"⚡ Context pressure detected — compacting before Wave N. Resuming inline."`

---

## Wave 1: ORIENT + AUDIT

Spawn a single agent:

```
Agent prompt: "You are running Wave 1 (Orient + Audit) for Phase ${PHASE}.
WORKING DIRECTORY: ${PROJECT_DIR}
Read: docs/design/phases/${PHASE}/phase_context.md, IMPLEMENTATION_GUIDELINES.md
Produce: agent_state/phases/${PHASE}/audit_report.md
Identify gaps, existing code, what needs to be built."
```

**Verify before proceeding:**
```bash
test -f agent_state/phases/${PHASE}/audit_report.md || echo "⛔ BLOCKED: audit_report.md missing"
```

**Auto-checkpoint:** Write `checkpoints/wave-1.json` with `artifacts_produced: ["audit_report.md"]`.

---

## Wave 2: IMPLEMENT

Spawn implementation agent(s):

```
Agent prompt: "You are running Wave 2 (Implementation) for Phase ${PHASE}.
Read: phase specs in docs/design/phases/${PHASE}/specs/
Read: IMPLEMENTATION_GUIDELINES.md for coding conventions
HARDENING RULES: interfaces not concrete types, repository pattern, wired metrics,
literal Unicode, table-driven Go tests, document spec deviations.
Implement all components. Commit after each logical unit."
```

**Verify before proceeding:**
```bash
# New source files exist
git diff --name-only HEAD~1 | grep -E '\.(ts|tsx|go)$' | head -5
```

**Auto-checkpoint:** Write `checkpoints/wave-2.json` with `artifacts_produced: [<new source files>]`.

---

## Wave 3: TEST (SEPARATE AGENTS PER TIER)

**CRITICAL: Spawn SEPARATE agents for each test tier.** A single agent cannot reliably write unit + integration + E2E tests — it exhausts context on the first tier and silently drops the rest. This was proven in dlp_composer where a single test agent produced unit tests but ZERO integration, ZERO E2E, ZERO component tests.

### Wave 3a — Unit Tests

```
Agent prompt: "You are running Wave 3a (Unit Tests) for Phase ${PHASE}.
Read docs/design/phases/${PHASE}/phase_context.md for context.
Read docs/design/phases/${PHASE}/specs/ for TC-* IDs assigned to tier: unit.
Write unit tests for ALL business logic. Annotate each test with its TC-* ID.
Coverage target: 80% per package. Table-driven tests mandatory.
Self-check: verify all responsible TC-* IDs are covered before completing.
Produce: agent_state/phases/${PHASE}/reports/unit_tests.md"
```

### Wave 3b — Integration Tests

```
Agent prompt: "You are running Wave 3b (Integration Tests) for Phase ${PHASE}.
Read docs/design/phases/${PHASE}/phase_context.md for context.
Read docs/design/phases/${PHASE}/specs/ for TC-* IDs assigned to tier: integration.
Write integration tests against REAL database and cache.
Test: repository CRUD, cache behavior, API contract shapes, cross-tenant IDOR.
Self-check: verify all responsible TC-* IDs are covered before completing.
Produce: agent_state/phases/${PHASE}/reports/integration_tests.md"
```

### Wave 3c — E2E Tests (project-type-aware)

Determine E2E strategy from `docs/IMPLEMENTATION_GUIDELINES.md`:

**If project has a web UI (frontend.enabled = true):**
```
Agent prompt: "You are running Wave 3c (E2E Tests — Browser) for Phase ${PHASE}.
Read docs/design/phases/${PHASE}/phase_context.md for context.
Read docs/design/phases/${PHASE}/specs/ for TC-* IDs assigned to tier: e2e or tier: component.
Write Playwright E2E tests for all in-scope user workflows.
Write component tests for all implemented UI screens (4-state: loading/error/empty/data).
Mock API responses must match data-contracts.md shapes exactly.
Self-check: verify all responsible TC-* IDs are covered before completing.
Produce: agent_state/phases/${PHASE}/reports/e2e_results.md
         agent_state/phases/${PHASE}/reports/ui_test_results.md"
```

**If project is a CLI tool, library, or non-web application:**
```
Agent prompt: "You are running Wave 3c (E2E Tests — Pipeline/CLI) for Phase ${PHASE}.
Read docs/design/phases/${PHASE}/phase_context.md for context.
Read docs/design/phases/${PHASE}/specs/ for TC-* IDs assigned to tier: e2e.
Write end-to-end pipeline tests that exercise the FULL product flow:
  - CLI invocation with real inputs → processing → output verification
  - Multi-step pipelines (e.g., compile → validate → deploy)
  - Error scenarios (malformed input → graceful error message)
  - WASM parity tests if applicable (same config, same output across runtimes)
These are NOT browser tests — they are process-level integration tests.
Self-check: verify all responsible TC-* IDs are covered before completing.
Produce: agent_state/phases/${PHASE}/reports/e2e_results.md"
```

**Spawn all 3 agents in PARALLEL** (they are independent):

```
Wave 3 (parallel):
  ├─ Agent: unit_test_agent     → reports/unit_tests.md
  ├─ Agent: integration_test_agent → reports/integration_tests.md
  └─ Agent: ui_test_agent / e2e  → reports/e2e_results.md (+ ui_test_results.md if web)
```

### Wave 3 Verification (ALL THREE must pass)

```bash
# All three report files must exist
test -f agent_state/phases/${PHASE}/reports/unit_tests.md || echo "⛔ BLOCKED: unit tests missing"
test -f agent_state/phases/${PHASE}/reports/integration_tests.md || echo "⛔ BLOCKED: integration tests missing"
test -f agent_state/phases/${PHASE}/reports/e2e_results.md || echo "⛔ BLOCKED: e2e tests missing"

# Content validation — reports must contain actual test results, not just headers
for REPORT in unit_tests.md integration_tests.md e2e_results.md; do
  FILE="agent_state/phases/${PHASE}/reports/${REPORT}"
  if [ -f "$FILE" ]; then
    # Check for test count indicators (passed, failed, total, PASS, FAIL)
    if ! grep -qiP '(pass|fail|total|test.*\d+|\d+\s*(pass|fail|test))' "$FILE"; then
      echo "⛔ BLOCKED: ${REPORT} exists but contains no test results — likely a stub"
    fi
    # Check for zero-test reports
    if grep -qiP '(total.*:\s*0|0\s+tests?\s+run|no tests|SKIPPED|not applicable)' "$FILE"; then
      echo "⚠ WARNING: ${REPORT} reports zero tests — verify this is correct for the project type"
    fi
  fi
done
```

**Auto-checkpoint:** Write `checkpoints/wave-3.json` with `tests_passing: true|false`, `artifacts_produced: ["reports/unit_tests.md", "reports/integration_tests.md", "reports/e2e_results.md"]`.

### Test Failure Recovery Guardrails

When tests fail and the test agent or a subsequent fix agent attempts auto-remediation, these guardrails are **absolute constraints** — they cannot be overridden by any agent:

**NEVER do these to make tests pass:**
- Delete, `.skip`, or comment out an existing test assertion or test function
- Reduce test coverage threshold to pass a gate
- Downgrade a dependency version to fix a build (may reintroduce CVEs)
- Modify test expectations to match buggy behavior instead of fixing the bug
- Remove a test file to reduce failure count
- Add `// @ts-ignore`, `//nolint`, or equivalent to suppress test-adjacent type errors

**Confidence-based escalation:**
- If root cause is clear (missing import, typo, wrong return type, obvious logic error) → auto-fix
- If root cause is unclear after reading the full failure output → escalate to user: "Test failure in [component] — root cause unclear. Options: [A] [B] [C]"
- Maximum 3 auto-fix attempts per failing test → then escalate (do NOT loop indefinitely)

**CI log sanitization (before feeding test output to any agent):**
Strip these patterns from test/build output before including in any agent prompt:
- Environment variables (`KEY=value`, `export VAR=`)
- Connection strings (`postgres://`, `redis://`, `mongodb://`, `mysql://`)
- Token-like strings (`sk-*`, `ghp_*`, `gho_*`, `Bearer *`, `token=*`)
- File paths containing `/secrets/`, `/.env`, `/credentials`, `/private/`
- Stack traces that include home directory paths (`/Users/`, `/home/`)

---

## Wave 3.5: LOCAL DEPLOY + HEALTH CHECK

**CRITICAL: Acceptance tests run against a LIVE app. This wave ensures the app is actually built, deployed locally, and healthy before Wave 4 tests against it.**

Without this step, acceptance tests either fail silently (nothing listening) or test against a stale build from a previous session. This was a gap in the original pipeline — acceptance tests claimed to validate "live behavior" but never ensured the app was running.

### Determine project type

Read `docs/IMPLEMENTATION_GUIDELINES.md` to determine the deployment strategy:

| Project Type | Deploy Strategy | Health Check |
|---|---|---|
| Web API + UI | `docker compose up -d --build` | `curl -sf http://localhost:PORT/health` |
| CLI tool | `go build ./cmd/...` or `npm run build` | Binary exists + `./bin/app --version` exits 0 |
| Library/SDK | `go build ./...` or `npm run build` | Build succeeds (no runtime to health check) |
| WASM module | Build native + WASM targets | Both binaries exist |

### Execute local deploy

```bash
echo "Wave 3.5: Local Deploy + Health Check"

# Read deploy/build commands from IMPLEMENTATION_GUIDELINES
# These are EXAMPLES — adapt to the project's actual stack

# For containerized projects:
if [ -f "docker-compose.yml" ] || [ -f "compose.yml" ]; then
  echo "  Building and deploying containers..."
  docker compose build --no-cache 2>&1 | tail -5
  docker compose up -d 2>&1

  # Run pending migrations
  # Migration command from IMPLEMENTATION_GUIDELINES
  echo "  Running migrations..."
  # e.g., docker compose exec api goose up
  # e.g., docker compose exec api npx prisma migrate deploy

  # Health check with retry (up to 60s)
  echo "  Health checking..."
  HEALTH_URL="http://localhost:${APP_PORT:-8080}/health"
  HEALTHY=false
  for i in $(seq 1 12); do
    if curl -sf "$HEALTH_URL" > /dev/null 2>&1; then
      HEALTHY=true
      break
    fi
    sleep 5
  done

  if [ "$HEALTHY" = true ]; then
    echo "  App healthy at $HEALTH_URL"
  else
    echo "  UNHEALTHY after 60s — checking logs..."
    docker compose logs --tail 30 2>&1
    echo "  Attempting restart..."
    docker compose restart 2>&1
    sleep 10
    curl -sf "$HEALTH_URL" > /dev/null 2>&1 || echo "  STILL UNHEALTHY after restart"
  fi

# For CLI/library projects:
elif [ -f "go.mod" ]; then
  echo "  Building Go binary..."
  go build ./cmd/... 2>&1 || echo "  Build failed"

elif [ -f "package.json" ]; then
  echo "  Building Node project..."
  npm run build 2>&1 || echo "  Build failed"

elif [ -f "Cargo.toml" ]; then
  echo "  Building Rust project..."
  cargo build 2>&1 || echo "  Build failed"
fi
```

### Verification gate

```bash
# For web apps: health endpoint must respond
if [ -f "docker-compose.yml" ] || [ -f "compose.yml" ]; then
  if [ "$HEALTHY" != true ]; then
    echo "BLOCKED: App not healthy — acceptance tests will fail against a dead service"
    echo "  Fix the deployment before proceeding to Wave 4"
    # In --auto mode: attempt auto-fix (check logs, restart, max 2 cycles)
    # After 2 cycles: force-proceed with WARNING logged to manifest
  fi
fi

# For CLI projects: binary must exist
if [ -f "go.mod" ] && [ ! -f "$(ls bin/* cmd/*/main.go 2>/dev/null | head -1)" ]; then
  echo "BLOCKED: CLI binary not built — E2E/acceptance tests need a working binary"
fi
```

**Auto-checkpoint:** Write `checkpoints/wave-3.5.json` with `deploy_status: healthy|unhealthy|not_applicable`, `deploy_type: docker|cli|library`.

---

## Wave 4: REVIEW + ACCEPTANCE (parallel)

Spawn TWO agents in parallel:

**Agent A — Code Quality Review:**
```
Agent prompt: "You are running Wave 4 Track A (Code Quality Review) for Phase ${PHASE}.
Review ALL source code against IMPLEMENTATION_GUIDELINES.
Check: style, architecture, security, quality gates, spec reconciliation.
Produce: agent_state/phases/${PHASE}/reports/code_quality_review.md"
```

**Agent B — Acceptance Tests:**
```
Agent prompt: "You are running Wave 4 Track B (Acceptance Tests) for Phase ${PHASE}.
PREREQUISITE: Wave 3.5 deployed the app locally. Verify it is running before testing:
  - For web apps: curl -sf http://localhost:PORT/health must return 200
  - For CLI tools: the built binary must exist and respond to --version or --help
If the app is NOT running, report BLOCKED immediately — do NOT write fake PASS results.

Test against the LIVE running app. Validate every FR-* acceptance criterion.
Test per persona. Verify OTEL traces, API contracts, accessibility.
Produce: agent_state/phases/${PHASE}/reports/acceptance_report.md"
```

**Verify BOTH before proceeding:**
```bash
test -f agent_state/phases/${PHASE}/reports/code_quality_review.md || echo "⛔ BLOCKED: review missing"
test -f agent_state/phases/${PHASE}/reports/acceptance_report.md || echo "⛔ BLOCKED: acceptance missing"
```

**⛔ DO NOT PROCEED TO WAVE 5 WITHOUT BOTH FILES.**

---

## Wave 5: COLLECTIVE FEEDBACK + ITERATE

The PARENT session (not an agent) reads all Wave 3+4 reports and builds the feedback document:

1. Read `unit_tests.md` — any failures?
2. Read `integration_tests.md` — any failures?
3. Read `e2e_results.md` — any failures?
4. Read `code_quality_review.md` — any HIGH/CRITICAL findings?
5. Read `acceptance_report.md` — any FAIL/PARTIAL?

Build: `agent_state/phases/${PHASE}/reports/collective_feedback.md`

If fixes needed, spawn fix agent:
```
Agent prompt: "Fix these items from collective feedback: [list items].
After fixing, re-run ALL test tiers — not just the failing tier.
A code fix that passes unit tests may break E2E tests.
Run: unit tests, integration tests, E2E tests.
If acceptance tests failed, re-run acceptance after code fixes.
Verify all tiers pass before reporting completion."
```

### Re-run Protocol (CRITICAL — prevents "fix unit, break E2E")

After ANY code fix in Wave 5:
1. Re-run unit tests → must pass
2. Re-run integration tests → must pass
3. Re-run E2E tests → must pass
4. If acceptance failed in Wave 4 → re-run acceptance → must pass

**Do NOT re-run only the tier that failed.** Code changes ripple across tiers. A fix to a service method (caught by unit test) may change an API response shape (caught by E2E) or break a user workflow (caught by acceptance).

Max 3 iteration cycles. If architectural issue → invoke debate_moderator.

**Verify:**
```bash
test -f agent_state/phases/${PHASE}/reports/collective_feedback.md || echo "⛔ BLOCKED"

# Verify feedback document records which tiers were re-run
if ! grep -qiP '(re-run|rerun|re.ran).*(unit|integration|e2e|acceptance)' \
    agent_state/phases/${PHASE}/reports/collective_feedback.md 2>/dev/null; then
  if grep -qiP '(fix|fixed|resolved)' \
      agent_state/phases/${PHASE}/reports/collective_feedback.md 2>/dev/null; then
    echo "⚠ WARNING: Feedback shows fixes were applied but no test tier re-runs recorded"
  fi
fi
```

---

## Wave 6: GATE

The PARENT session runs the gate check:

1. Verify ALL required files exist AND contain actual test results:
   - audit_report.md ✓
   - unit_tests.md ✓ (must contain non-zero test count)
   - integration_tests.md ✓ (must contain non-zero test count)
   - e2e_results.md ✓ (must contain non-zero test count)
   - code_quality_review.md ✓
   - acceptance_report.md ✓ (must contain non-zero use case count)
   - collective_feedback.md ✓

   **Content validation (not just file existence):**
   ```bash
   for REPORT in unit_tests.md integration_tests.md e2e_results.md acceptance_report.md; do
     FILE="agent_state/phases/${PHASE}/reports/${REPORT}"
     if [ -f "$FILE" ]; then
       if grep -qiP '(total.*:\s*0\b|0\s+tests?\s+run|no tests (run|found|written)|SKIPPED.*all)' "$FILE"; then
         echo "⛔ GATE BLOCKED: ${REPORT} reports ZERO tests — a test tier was skipped"
         echo "   This is NOT acceptable. Every tier must produce at least 1 test."
       fi
     else
       echo "⛔ GATE BLOCKED: ${REPORT} missing"
     fi
   done
   ```

2. Run FULL regression test suite (all phases, not just current):
   ```bash
   cd frontend && npx vitest run && npx playwright test
   cd backend && go test ./...
   ```

3. If all pass → write gate.passed + manifest.json + git tag

4. If any fail → DO NOT write gate.passed. Route failures back to Wave 5.

**Auto-checkpoint:** Write `checkpoints/wave-6.json` with `tests_passing: true`, `artifacts_produced: ["gate.passed", "manifest.json"]`.

---

## Post-Gate: CONSOLIDATE + LEARN (inspired by agentmemory's consolidation pipeline)

**Runs ONLY after gate.passed is written.** This step extracts reusable knowledge from the phase execution for future phases. It's the equivalent of agentmemory's `consolidate` → `crystallize` → `lessons` pipeline, but deterministic and structural.

The PARENT session (inline, no subagent) reads all phase artifacts and writes `agent_state/phases/${PHASE}/lessons.md`:

### 1. Extract Lessons

Read:
- `reports/collective_feedback.md` — what bugs were found and how they were fixed
- `reports/code_quality_review.md` — what patterns were flagged
- `execution.jsonl` — which agents failed/retried and why
- `checkpoints/` — how long each wave took

Write `agent_state/phases/${PHASE}/lessons.md`:

```markdown
# Phase ${PHASE} Lessons Learned
Generated: <timestamp>

## Patterns That Worked
- <pattern observed that should be repeated>
- <e.g., "Repository pattern with interface DI eliminated all mocking issues">

## Issues Encountered
- <issue>: <root cause> → <fix applied>
- <e.g., "E2E tests flaky on CI: race condition in DB seeding → added transaction isolation">

## Agent Performance
- Slowest agent: <name> (<duration>s) — reason: <why>
- Failed agents: <name> (attempt <N>) — root cause: <why>
- Retried: <count> total retries across all agents

## Recommendations for Phase ${PHASE+1}
- <actionable recommendation based on this phase's experience>
- <e.g., "Add DB seeding helper to test setup — 3 test agents re-implemented the same pattern">

## Patterns to Avoid
- <anti-pattern observed> — <why it's bad> — <what to do instead>
```

### 2. Update Cross-Phase Patterns (append-only)

If `agent_state/patterns.md` exists, append new patterns. If not, create it.

```markdown
# Accumulated Patterns (auto-updated after each phase gate)

## Phase 1 (2026-MM-DD)
- <patterns extracted>

## Phase 2 (2026-MM-DD)
- <patterns extracted>
```

This file is read by `project_planner` when planning Phase N+1 — it provides historical context about what works and what doesn't for THIS specific project.

### 3. Confidence Metadata for Codebase Knowledge

If `agent_state/codebase/` exists, update `.last-mapped` with a confidence indicator:

```bash
# After gate passes, codebase knowledge confidence increases
# (the mapping was validated by successful implementation + tests)
echo "sha:$(git rev-parse --short HEAD)" > agent_state/codebase/.last-mapped
echo "confidence:high" >> agent_state/codebase/.last-mapped
echo "validated_by:phase-${PHASE}-gate" >> agent_state/codebase/.last-mapped
echo "ts:$(date -u +%Y-%m-%dT%H:%M:%SZ)" >> agent_state/codebase/.last-mapped
```

If the gate FAILS, confidence degrades:
```bash
echo "confidence:degraded" >> agent_state/codebase/.last-mapped
echo "reason:phase-${PHASE}-gate-failed" >> agent_state/codebase/.last-mapped
```

**Key insight from agentmemory:** Memory isn't just stored — it has a lifecycle. Knowledge that was validated by a passing gate is HIGH confidence. Knowledge that predates a failed gate is DEGRADED (the codebase changed in ways the mapping didn't predict). This drives the `/map --incremental` recommendation in `/health`.
