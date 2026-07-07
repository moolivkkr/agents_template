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

## Wave 0: SCALE THE WORKFLOW DEPTH

Before Wave 1, classify phase complexity and scale how many waves run — do not pay full
six-wave ceremony for a typo fix. See `.claude/skills/core/scale-adaptive-depth.md`.

| Class | Signals | Waves to run |
|-------|---------|--------------|
| **trivial** | 1 file, no shared layer, copy/typo | scoped edit + test only (skip audit/TRD/review waves) |
| **small** | ≤2 components, no shared layer | Waves 2, 3, 6 (light) |
| **standard** | multi-component or brownfield | full Waves 1–6 (default) |
| **platform** | shared layer, new subsystem, many FR-* | full 1–6 + architecture/ADR pass |

Complexity also drives model routing (`model-routing.md`); this drives *workflow depth*. Upgrades
allowed mid-run (escalate if a "small" phase turns out to touch a shared layer); never silently
downgrade. Record the chosen class in the Wave-0 checkpoint.

### Wave 0b — Write the Expected Agent Roster (execution guarantee)

**This is the structural fix for "did every agent actually run?"** The parent computes the roster of
agents this phase MUST execute (derived from the scale class + project shape) and writes it to
`agent_state/phases/${PHASE}/roster.json`. Wave 6 (and the `verify-gate.sh` hook) diffs this roster
against what actually completed (`execution.jsonl`) and BLOCKS the gate if any `required` agent has no
`completed` entry. This turns "we hope the reviewers ran" into "we proved they ran."

**⛔ CONTRACT — `roster.required` MUST use the REAL agent names, verbatim, exactly as each agent logs
itself into `execution.jsonl` (the `"agent"` field).** Never use generic slot labels like
`wave1_audit` or `e2e_or_ui_test_agent` — the completeness diff is a straight set-membership check
(`roster.required ⊆ {agents with a completed line}`), and slot labels live in a different namespace
than the logged agent names, so they would false-block or silently pass. The roster schema is a flat
`required` array of names, aligned with `.claude/hooks/verify-gate.sh`:

```json
{"phase": N, "required": ["<agent-name>", ...]}
```

**Derive the roster from the set of agents this phase will actually spawn** (so `required` ⊇ the
gate's required-report set — no drift). Base list for a STANDARD phase, using the real names each
Wave spawns:

```bash
mkdir -p "agent_state/phases/${PHASE}"
# Base STANDARD roster — REAL agent names (must match the "agent" field each writes to execution.jsonl).
# Tailor per scale class + project shape:
#  - trivial/small: keep only the agents whose waves you actually run.
#  - not multi-tenant: DROP tenant_isolation_verifier from the array (record the skip in the manifest).
#  - no web UI: use e2e_test_agent (not ui_test_agent); DROP ui_developer/ui_test_agent/design_quality_reviewer.
#  - web UI: ADD ui_developer, ui_test_agent (and design_quality_reviewer if used) to the array.
#  - has DB migrations: ADD migration_agent AND migration_safety_reviewer (adversarial migration review).
#  - changes a cross-phase contract (API/type/event/column consumed by an earlier phase): ADD breaking_change_reviewer.
#  - platform: also add architecture_orchestrator + adr_agent (see Wave 0 table).
#  - candidate-selection will run this phase (Wave 2 mode N>=2 — PLATFORM / high-complexity /
#    prev-failure / --candidates=N): ADD solution_selector. It is a REQUIRED agent whenever N>=2, so
#    its completed line + candidate_selection.md report are proven by the Wave-6 roster check. When
#    N==1 (single implementation), OMIT it (record candidate_selection:skipped in the manifest).
REQUIRED='["backend_audit_agent","backend_developer","api_developer","unit_test_agent","integration_test_agent","e2e_test_agent","code_reviewer_I","code_reviewer_II","security_reviewer","dependency_scanner","code_quality_verifier","spec_impl_reconciler","spec_test_reconciler","acceptance_test_agent","tenant_isolation_verifier"]'
python3 - "$REQUIRED" "${PHASE}" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" > "agent_state/phases/${PHASE}/roster.json" << 'PY'
import json, sys
required = json.loads(sys.argv[1])
print(json.dumps({"phase": int(sys.argv[2]), "generated": sys.argv[3], "required": required}, indent=2))
PY
```

**Every wave that spawns an agent must append a completion line to the execution log** so Wave 6 (and
`verify-gate.sh`) can verify it. `${AGENT_NAME}` MUST be the same real name that appears in
`roster.required`, and `report` MUST be the relative path to that agent's primary output (or `null`
if it produces none). After each agent returns successfully:
```bash
mkdir -p "agent_state/phases/${PHASE}"
echo "{\"agent\":\"${AGENT_NAME}\",\"phase\":${PHASE},\"status\":\"completed\",\"report\":\"${REPORT_PATH:-null}\",\"ts\":\"$(date -u +%Y-%m-%dT%H:%M:%SZ)\"}" \
  >> "agent_state/phases/${PHASE}/execution.jsonl"
```

If you deliberately skip an agent (e.g. not multi-tenant, trivial phase), **omit it from
`roster.required`** and record the skip + reason in the phase manifest (`skipped_agents[]`) — an
explicit, documented omission is auditable; leaving it `required` and never running it is the exact
bug this roster exists to catch.

---

## ⛔ MANDATORY — Ground-Truth Injection on EVERY spawn

Every `Agent prompt:` in this orchestrator MUST begin with the ground-truth injection line so
Tier 0 facts reach every subagent (subagents do not inherit the conversation). Prepend verbatim:

```
GROUND TRUTH: First read docs/PROJECT_FACTS.md (Tier 0 facts) AND docs/DECISIONS.md (Tier 0.5
settled decisions). They list retired/renamed components, hard constraints, environment facts, and
prior decisions with rationale, and they OVERRIDE any conflicting assumption in this prompt or your
training. If this task touches anything marked RETIRED/superseded/reversed there, stop and flag it
instead of proceeding. Do not re-litigate an active decision without new evidence.
```

The wave prompts below omit this line only for brevity — you must add it to each. See
`.claude/skills/core/shared-context-protocol.md`.

---

## Wave 1: ORIENT + AUDIT

Spawn a single agent (remember to prepend the GROUND TRUTH line):

```
Agent prompt: "[GROUND TRUTH line] You are running Wave 1 (Orient + Audit) for Phase ${PHASE}.
WORKING DIRECTORY: ${PROJECT_DIR}
Read: docs/PROJECT_FACTS.md (ground truth), docs/design/phases/${PHASE}/phase_context.md, IMPLEMENTATION_GUIDELINES.md
Produce: agent_state/phases/${PHASE}/audit_report.md
Identify gaps, existing code, what needs to be built.
If the audit finds a component that is dead/retired, propose a /remember fact (confidence: reported)."
```

**Verify before proceeding:**
```bash
test -f agent_state/phases/${PHASE}/audit_report.md || echo "⛔ BLOCKED: audit_report.md missing"
```

**Auto-checkpoint:** Write `checkpoints/wave-1.json` with `artifacts_produced: ["audit_report.md"]`.

---

## Wave 2: IMPLEMENT

**Two modes.** Default = a **single** implementation (Wave 2A). Hard/high-value phases run
**candidate-selection** (Wave 2B): N independent implementations + a selector picks the winner. Decide
the mode FIRST, then run exactly one branch below.

### Wave 2 Mode Decision (candidate-selection gate)

Run candidate-selection ONLY when a trigger fires — it costs ≈N× the Wave-2 tokens, so it is OPT-IN,
not the default (see `.claude/skills/core/candidate-selection.md` §When it triggers). Evaluate:

```bash
# N = 1 means "single implementation" (default). N in [2,3] turns on candidate-selection.
N=1; TRIGGER=""
CLASS=$(python3 -c "import json;print(json.load(open('agent_state/phases/${PHASE}/complexity.json')).get('complexity_class',''))" 2>/dev/null || echo "")
PREV_FB="agent_state/phases/$((PHASE-1))/reports/collective_feedback.md"

if [ -n "${ARG_CANDIDATES:-}" ]; then                     # explicit --candidates=N (clamped 2..3)
  N=$(( ARG_CANDIDATES < 2 ? 1 : (ARG_CANDIDATES > 3 ? 3 : ARG_CANDIDATES) )); TRIGGER="flag"
elif [ "$CLASS" = "platform" ]; then                      # scale-class PLATFORM
  N=2; TRIGGER="platform"
elif [ "${RAW_SCORE:-0}" -gt 60 ]; then                   # high model-routing complexity (>60)
  N=2; TRIGGER="complexity"
elif [ -f "$PREV_FB" ] && grep -qiE "phase ${PHASE}|<this-component>" "$PREV_FB" 2>/dev/null; then
  N=2; TRIGGER="prev-failure"                             # prev-phase failure touched this component
fi
echo "Wave 2 mode: N=${N} ${TRIGGER:+(trigger=$TRIGGER)}"
```

If `N == 1` → run **Wave 2A**. If `N >= 2` → run **Wave 2B** (and add `solution_selector` to the
roster — see below). For TRIVIAL/SMALL/STANDARD classes with no trigger, `N` stays 1 and the manifest
records `candidate_selection: skipped (class=${CLASS}, no trigger)`.

### Wave 2A — Single Implementation (default)

Spawn implementation agent(s):

```
Agent prompt: "You are running Wave 2 (Implementation) for Phase ${PHASE}.
Read: phase specs in docs/design/phases/${PHASE}/specs/
Read: IMPLEMENTATION_GUIDELINES.md for coding conventions
HARDENING RULES: interfaces not concrete types, repository pattern, wired metrics,
literal Unicode, table-driven Go tests, document spec deviations.
Implement all components. Commit after each logical unit."
```

### Wave 2B — Candidate Selection (conditional — hard phases only)

Full protocol: `.claude/skills/core/candidate-selection.md`. This REPLACES Wave 2A's single
implementation for this phase; it does NOT replace Wave 3/4/6 — the winner runs them as usual.

**1. Create N isolated worktrees (one per candidate) off the current HEAD:**
```bash
BASE="$(git rev-parse --short HEAD)"
WT_ROOT="agent_state/phases/${PHASE}/candidates"; mkdir -p "$WT_ROOT"
for i in $(seq 1 "${N}"); do
  git worktree add -b "cand/phase-${PHASE}/c${i}" "${WT_ROOT}/c${i}" "$BASE"
done
git worktree list
```

**2. Spawn N candidate implementers IN PARALLEL**, each in its OWN worktree with a DISTINCT starting
strategy for diversity (round-robin: c1=interface-first, c2=test-first, c3=data-model-first). Each MUST
write its own tests. Prepend the GROUND TRUTH line to each:
```
Agent prompt: "[GROUND TRUTH] You are candidate implementer c${i} for Phase ${PHASE}.
WORKING DIRECTORY: ${PROJECT_DIR}/agent_state/phases/${PHASE}/candidates/c${i}  (your OWN git worktree — commit ONLY here)
STARTING STRATEGY: ${STRATEGY}  (interface-first | test-first | data-model-first)
Read the SAME specs as Wave 2A: docs/design/phases/${PHASE}/specs/ + IMPLEMENTATION_GUIDELINES.md.
Implement ALL in-scope components AND write your own tests (unit + this surface's TC-* IDs).
HARDENING RULES apply. Do NOT read/merge from sibling candidate worktrees. Commit in THIS worktree only.
Return: files created + one line on how your strategy shaped the design."
```

**3. Model-test voting (Signal A) — build the cross-test matrix** before the selector runs. Run each
candidate's own suite, and cross-run comparable suites (same public interface / same TC-* IDs) against
the sibling implementations. Write `agent_state/phases/${PHASE}/candidates/cross_test_matrix.md` (own
pass + cross pass rate per candidate; mark non-comparable pairs `N/A` — never fake a PASS).

**4. Spawn `solution_selector` (Signal B + combine):**
```
Agent prompt: "[GROUND TRUTH] You are solution_selector for Phase ${PHASE}.
Read .claude/skills/core/candidate-selection.md, docs/design/phases/${PHASE}/specs/,
and agent_state/phases/${PHASE}/candidates/cross_test_matrix.md.
Score EACH candidate on the fixed rubric (R1 coverage, R2 test, R3 quality, R4 arch, R5 risk).
Combine 0.5*cross_test + 0.5*rubric. Disqualify any candidate that fails its own tests or uses a
RETIRED component. Execution overrides preference. Produce a winner + rationale + a specific graft list.
Write agent_state/phases/${PHASE}/reports/candidate_selection.md and log a completed line to execution.jsonl."
```

**5. Rejoin — merge the winner, graft, discard losers** (per skill §How the winner rejoins):
```bash
WINNER=$(grep -oE 'WINNER: c[0-9]+' "agent_state/phases/${PHASE}/reports/candidate_selection.md" | grep -oE 'c[0-9]+' | head -1)
git merge --no-ff "cand/phase-${PHASE}/${WINNER}" -m "phase ${PHASE}: adopt candidate ${WINNER} (selected — see candidate_selection.md)"
# Apply grafts named in candidate_selection.md (cherry-pick specific files — NEVER blind-merge a loser), then:
for i in $(seq 1 "${N}"); do
  C="c${i}"
  git worktree remove --force "agent_state/phases/${PHASE}/candidates/${C}" 2>/dev/null || true
  [ "$C" = "$WINNER" ] || git branch -D "cand/phase-${PHASE}/${C}" 2>/dev/null || true
done
git worktree prune
```

**6. Log the decision** to `execution.jsonl`:
```bash
echo "{\"ts\":\"$(date -u +%Y-%m-%dT%H:%M:%SZ)\",\"event\":\"candidate_selection\",\"phase\":${PHASE},\"n\":${N},\"trigger\":\"${TRIGGER}\",\"winner\":\"${WINNER}\",\"report\":\"agent_state/phases/${PHASE}/reports/candidate_selection.md\"}" >> "agent_state/phases/${PHASE}/execution.jsonl"
```

After rejoin, **continue to Wave 3 on the winner** (merged working tree). The gate is unchanged.

**Verify before proceeding:**
```bash
# New source files exist (Wave 2A: on HEAD; Wave 2B: after the winner merge)
git diff --name-only HEAD~1 | grep -E '\.(ts|tsx|go)$' | head -5
# If Wave 2B ran: the selector report must exist and name a winner, and no dangling candidate worktrees remain.
if [ "${N:-1}" -ge 2 ]; then
  test -f "agent_state/phases/${PHASE}/reports/candidate_selection.md" || echo "⛔ BLOCKED: candidate_selection.md missing — solution_selector did not complete"
  git worktree list | grep -q "phases/${PHASE}/candidates/" && echo "⚠ dangling candidate worktree — run git worktree prune"
fi
```

**Auto-checkpoint:** Write `checkpoints/wave-2.json` with `artifacts_produced: [<new source files>]` and, if Wave 2B ran, `candidate_selection: {n: N, trigger: "<trigger>", winner: "cN"}`.

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

## Wave 4: REVIEW + RECONCILE + ACCEPTANCE (parallel tracks)

**⛔ CRITICAL — do NOT collapse review into one agent.** A single "code quality review" agent
exhausts context on the first dimension and silently drops the rest — this is the *exact*
single-agent failure mode Wave 3 rails against for tests, and it is how security review, both
reconcilers, and the dependency scan get dropped from a run. Spawn each reviewer/reconciler as a
SEPARATE, NAMED agent. Every agent below maps 1:1 to an entry in the Wave-0 roster and every one
must produce its named report; Wave 6 blocks if any is missing.

Spawn Track A (reviewers, parallel), Track C (reconcilers, parallel with A), and Track B
(acceptance) — all concurrently where independent.

### Track A — Code Review (SEPARATE agents per dimension, parallel)

```
Wave 4 Track A (parallel):
  ├─ Agent: code_reviewer_I          → reports/code_review_I.md        (style, idioms, naming)
  ├─ Agent: code_reviewer_II         → reports/code_review_II.md       (architecture, layer boundaries)
  ├─ Agent: security_reviewer        → reports/security_review.md      (OWASP + project constraints)
  ├─ Agent: tenant_isolation_verifier → reports/tenant_isolation.md    (only if multi-tenant; see IMPL_GUIDELINES)
  ├─ Agent: dependency_scanner       → reports/dependency_scan.md      (CVEs, licenses, outdated)
  └─ Agent: code_quality_verifier    → reports/quality_gate.md         (TODOs, stubs, secrets, dead code)
```

Each spawn prompt (prepend the GROUND TRUTH line):
```
Agent prompt: "[GROUND TRUTH] You are <agent_name> running Wave 4 Track A for Phase ${PHASE}.
Review ALL source changed/added in this phase against IMPLEMENTATION_GUIDELINES and the phase specs.
Use the Unified Severity Model (.claude/skills/core/code-quality.md): BLOCKING | WARNING | INFO.
Every finding MUST cite file:line. Produce your named report at the exact path above.
Definition of Done: report written, every BLOCKING finding has file:line + a fix recommendation,
and the report ends with a one-line COUNT summary: 'BLOCKING:N WARNING:N INFO:N'."
```

> `tenant_isolation_verifier` runs only when the project is multi-tenant (SaaS tenancy model in
> IMPLEMENTATION_GUIDELINES). If not applicable, record it as `skipped:not_applicable` in the roster
> — that is an explicit skip, not a silent drop.

### Track C — Reconciliation (SEPARATE agents, parallel with Track A)

These were previously omitted from the orchestrator entirely (they lived only in develop.md and so
never ran under wave execution). They are now mandatory Wave-4 agents.

```
Wave 4 Track C (parallel):
  ├─ Agent: spec_impl_reconciler  → reports/specs_vs_impl.md      (spec ↔ code: MISSING / EXTRA / DRIFT)
  └─ Agent: spec_test_reconciler  → reports/spec_test_coverage.md (spec ↔ tests: TC-* coverage %, deferred IDs)
```

Each spawn prompt (prepend GROUND TRUTH):
```
Agent prompt: "[GROUND TRUTH] You are <reconciler> running Wave 4 Track C for Phase ${PHASE}.
Perform bidirectional reconciliation. Report every MISSING (spec item with no code/test) and every
EXTRA (code/test with no spec). Classify each: BLOCKING (in-scope FR-* unbuilt/untested) vs
DEFERRED (explicitly out-of-scope, list the ID). Produce your named report.
Definition of Done: coverage % computed, BLOCKING list explicit, deferred IDs enumerated."
```

### Track B — Acceptance Tests

```
Agent prompt: "[GROUND TRUTH] You are running Wave 4 Track B (Acceptance Tests) for Phase ${PHASE}.
PREREQUISITE: Wave 3.5 deployed the app locally. Verify it is running before testing:
  - For web apps: curl -sf http://localhost:PORT/health must return 200
  - For CLI tools: the built binary must exist and respond to --version or --help
If the app is NOT running, report BLOCKED immediately — do NOT write fake PASS results.

Test against the LIVE running app. Validate every FR-* acceptance criterion.
Test per persona. Verify OTEL traces, API contracts, accessibility.
Produce: agent_state/phases/${PHASE}/reports/acceptance_report.md"
```

### Wave 4 Verification — every named report must exist AND carry a verdict

```bash
WAVE4_BLOCKED=false
# Reviewers + reconcilers + acceptance. Skip tenant_isolation if roster marked it not_applicable.
REQUIRED_W4="code_review_I.md code_review_II.md security_review.md dependency_scan.md \
             quality_gate.md specs_vs_impl.md spec_test_coverage.md acceptance_report.md"
if grep -q '"tenant_isolation_verifier"[^}]*"status": *"required"' \
     "agent_state/phases/${PHASE}/roster.json" 2>/dev/null; then
  REQUIRED_W4="$REQUIRED_W4 tenant_isolation.md"
fi
for R in $REQUIRED_W4; do
  F="agent_state/phases/${PHASE}/reports/${R}"
  if [ ! -f "$F" ]; then
    echo "⛔ BLOCKED: Wave 4 report ${R} missing — its agent was not spawned or did not complete"
    WAVE4_BLOCKED=true
  elif [ ! -s "$F" ] || [ "$(wc -l < "$F")" -lt 3 ]; then
    echo "⛔ BLOCKED: ${R} is empty/stub — the review did not actually run"
    WAVE4_BLOCKED=true
  fi
done
[ "$WAVE4_BLOCKED" = true ] && echo "⛔ DO NOT PROCEED — re-spawn the missing Wave-4 agents."
```

### Track A/C Fix → Re-Review Loop (do NOT defer all fixes to Wave 5)

BLOCKING findings from a reviewer/reconciler must be fixed and **re-verified by re-running only that
same agent** — not merely re-tested. This is the closed loop from `review.md`; without it a reviewer
finding is "addressed" without proof.

```
For each report with BLOCKING findings:
  1. Spawn a scoped fix agent for that report's findings.
  2. Re-spawn ONLY the reviewer/reconciler that raised them.
  3. Repeat max 2 rounds per report. If still BLOCKING after 2 rounds → carry to Wave 5 as a
     classified failure, or escalate to debate_moderator if architectural.
Anti-rationalization: "the fix looks right, no need to re-run" is WRONG — always re-run the agent.
```

**⛔ DO NOT PROCEED TO WAVE 5 until every required Wave-4 report exists and its BLOCKING count is
0 (or the item is explicitly carried forward with a reason).**

---

## Wave 5: COLLECTIVE FEEDBACK + ITERATE (with Adaptive Replanning)

> **Skill references:** `.claude/skills/core/adaptive-replan.md` (failure classification → minimum re-test SCOPE) and `.claude/skills/core/dual-ledger-replan.md` (Task/Progress ledgers → WHEN to replan vs keep iterating vs escalate). They compose: the ledger decides *whether* to keep going; the classification decides *what* to re-run.

**Maintain the dual ledgers across iterations.** The PARENT keeps `agent_state/phases/${PHASE}/ledger.md`:
- **Task Ledger** — `facts[]` (verified only), `assumptions[]` (guesses, kept explicitly separate — never present a guess as a fact), `plan[]`.
- **Progress Ledger** (per iteration) — step, assignee, done?, new-fact-this-cycle?, loop_count.

**Stall rule:** if `loop_count > 2` with no new fact (or the same failing action repeats without progress) → STALL → REPLAN: write the failure mode, evict the falsified assumption, rewrite `plan[]` (usually re-classify), and escalate after the tier's retry cap (`sdlc-config.json`) to `debate_moderator` or the human. A verified, broadly-true assumption may be promoted to a Tier 0 fact via `/remember`.

The PARENT session (not an agent) reads all Wave 3+4 reports and builds the feedback document:

1. Read `unit_tests.md` — any failures?
2. Read `integration_tests.md` — any failures?
3. Read `e2e_results.md` — any failures?
4. Read the review reports — `code_review_I.md`, `code_review_II.md`, `security_review.md`,
   `dependency_scan.md`, `quality_gate.md` — any BLOCKING/HIGH/CRITICAL findings?
5. Read `acceptance_report.md` — any FAIL/PARTIAL?

Build: `agent_state/phases/${PHASE}/reports/collective_feedback.md`

### Adaptive Replanning (failure-aware fix routing)

Before spawning the fix agent, **classify each failure** using the adaptive replan protocol:

| Category | Signal | Re-Test Scope |
|---|---|---|
| LOGIC | Unit assertion failed | unit + integration |
| WIRING | Integration 404/500 | integration + E2E |
| CONTRACT | Shape mismatch, CONTRACT_VIOLATION | E2E + acceptance |
| SCHEMA | Migration/constraint error | ALL tiers |
| UI | Component render failure | UI + E2E |
| CONFIG | Health check fail, connection refused | integration + E2E + acceptance |
| FLAKY | Passes on retry | failing tier only |

If multiple categories → take the UNION of re-test scopes. If any is SCHEMA/CONFIG → ALL tiers.

Spawn fix agent with classification:
```
Agent prompt: "Fix these items from collective feedback:

FAILURE CLASSIFICATION: ${CATEGORY}
ROOT CAUSE: ${ROOT_CAUSE_DESCRIPTION}
AFFECTED FILES: ${FILES_FROM_ERROR_OUTPUT}

Items to fix:
${FAILURE_LIST}

After fixing, re-run these tiers (minimum viable scope per adaptive-replan.md):
  ${REQUIRED_TIERS}

You may SKIP these tiers (not affected by this fix type):
  ${SKIPPABLE_TIERS}

IMPORTANT: After applying your fix, check git diff. If you touched files
outside the predicted scope, EXPAND your re-test to include ALL tiers.

Also check agent_state/patterns.md for known fixes matching this failure category.

Verify all required tiers pass before reporting completion."
```

### Re-run Protocol

The adaptive replan protocol determines which tiers to re-run. The **safety guarantee** remains:

- **Single-category fix:** Re-run classified tiers + one safety tier above
- **Multi-category or SCHEMA/CONFIG:** Re-run ALL tiers (no shortcuts)
- **Git diff expanded beyond predicted scope:** Re-run ALL tiers
- If acceptance failed in Wave 4 → re-run acceptance after code fixes regardless of category

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

The PARENT session runs the gate check using the **Gate Verification Protocol**
(`.claude/skills/core/gate-verification.md`) — evidence-based, graded, cross-checked. The
binary "file exists + non-zero count" check below is only Layer 0; it is necessary but NOT
sufficient. The parent MUST also run Layer 1 (independent file:line re-verification — never
trust the subagent's report), Layer 2 (numeric `gate_score ≥ 0.90`), and Layer 3 (cross-model
refutation of high-stakes claims) before writing `gate.passed`.

**Order:** Layer 0 (below) → Layer 0b roster + debate dispatch → Layer 1 re-verification → Layer 2
score → Layer 3 for security/tenant-isolation/"fixed" claims → write `gate_score.md` → only then
`gate.passed`.

0b. **Agent-roster completeness (execution guarantee) — run FIRST, via the shared hook.** The single
    source of truth for this check is `.claude/hooks/verify-gate.sh`. It passes iff (1) every
    `roster.required` name has a `status:"completed"` line, (2) every completed line's non-null
    `report` file exists and is non-stub (no `total: 0` / `SKIPPED` in test reports; no unresolved
    `BLOCKING`), and (3) no `failed` line lacks a later `completed`. Run it and honor its exit code —
    do NOT re-implement a divergent copy here:
    ```bash
    bash .claude/hooks/verify-gate.sh "${PHASE}" || {
      echo "⛔ GATE BLOCKED by verify-gate.sh — see output above."
      echo "   Re-spawn any missing/failed agents (roster.required vs execution.jsonl) before gating."
      exit 1
    }
    ```
    If the hook is somehow unavailable, fall back to this equivalent membership check (the hook is
    authoritative — reconcile back to it if they ever diverge):
    ```bash
    ROSTER="agent_state/phases/${PHASE}/roster.json"
    EXEC="agent_state/phases/${PHASE}/execution.jsonl"
    python3 - "$ROSTER" "$EXEC" << 'PY'
    import json, sys, os
    roster = json.load(open(sys.argv[1]))
    required = roster.get("required", [])
    completed = set()
    if os.path.exists(sys.argv[2]):
        for line in open(sys.argv[2]):
            line = line.strip()
            if not line: continue
            try:
                e = json.loads(line)
                if e.get("status") == "completed": completed.add(e.get("agent"))
            except Exception: pass
    missing = [a for a in required if a not in completed]
    if missing:
        print("⛔ GATE BLOCKED — required agents never completed:", ", ".join(missing))
        print("   Re-spawn them before the gate can pass. (roster.required vs execution.jsonl)")
        sys.exit(1)
    print("✓ Roster complete — every required agent has a completed execution entry.")
    PY
    ```

0c. **Debate dispatcher — no orphaned escalations.** Any escalation request written by a pipeline
    agent must have a verdict before the gate. Force-spawn `debate_moderator` for any request lacking
    a matching verdict; under `--auto`, record auto-resolved debates as `known_issues`.
    ```bash
    for REQ in agent_state/debates/*-request.json; do
      [ -e "$REQ" ] || continue
      VERDICT="${REQ%-request.json}-verdict.json"
      if [ ! -f "$VERDICT" ]; then
        echo "⚠ Pending debate with no verdict: $REQ → spawn debate_moderator now (do not gate without it)"
      fi
    done
    ```

1. Verify ALL required files exist AND contain real content (tests, reviews, reconciliation,
   acceptance). This list is the hard `REQUIRED_REPORTS` set — it now includes the review and
   reconciliation reports that were previously omitted (and therefore skippable):
   - audit_report.md ✓
   - unit_tests.md ✓ (non-zero test count)
   - integration_tests.md ✓ (non-zero test count)
   - e2e_results.md ✓ (non-zero test count)
   - code_review_I.md ✓ · code_review_II.md ✓ · security_review.md ✓
   - dependency_scan.md ✓ · quality_gate.md ✓
   - specs_vs_impl.md ✓ · spec_test_coverage.md ✓  (reconciliation — BLOCKING findings must be 0)
   - tenant_isolation.md ✓ (CONDITIONAL — required only when multi-tenant; else roster omits
     tenant_isolation_verifier and the manifest records the skip)
   - acceptance_report.md ✓ (non-zero use case count)
   - collective_feedback.md ✓

   **Conditional reports (required only when the phase has the relevant surface — otherwise recorded
   `not_applicable` in the manifest, never silently omitted; this matches `/develop` Step 6):**
   - sast_scan.md — when a SAST command is configured in IMPLEMENTATION_GUIDELINES (security-relevant code)
   - migration_safety.md — when the phase adds/changes DB migrations (migration_safety_reviewer)
   - breaking_change_review.md — when the phase changes a contract an earlier phase consumes (breaking_change_reviewer)
   - visual_validation.md — when `*.wireframe.html` files exist for this phase
   - ui_test_results.md / ui_code_optimization.md — when `frontend.enabled = true`
   - candidate_selection.md — when Wave 2 ran candidate-selection (N≥2). `solution_selector` is then
     in `roster.required`, so the roster check (0b) already blocks if it didn't run; this report must
     name a winner and its `BLOCKING` count must be 0 (or carried forward with a reason).

   **Content validation (not just file existence):**
   ```bash
   # Test reports: must not report zero tests.
   for REPORT in unit_tests.md integration_tests.md e2e_results.md acceptance_report.md; do
     FILE="agent_state/phases/${PHASE}/reports/${REPORT}"
     if [ -f "$FILE" ]; then
       if grep -qiP '(total.*:\s*0\b|0\s+tests?\s+run|no tests (run|found|written)|SKIPPED.*all)' "$FILE"; then
         echo "⛔ GATE BLOCKED: ${REPORT} reports ZERO tests — a test tier was skipped"
       fi
     else
       echo "⛔ GATE BLOCKED: ${REPORT} missing"
     fi
   done
   # Review + reconciliation reports: must exist and be non-stub.
   for REPORT in code_review_I.md code_review_II.md security_review.md dependency_scan.md \
                 quality_gate.md specs_vs_impl.md spec_test_coverage.md; do
     FILE="agent_state/phases/${PHASE}/reports/${REPORT}"
     if [ ! -f "$FILE" ]; then
       echo "⛔ GATE BLOCKED: ${REPORT} missing — a review/reconcile agent was skipped"
     elif [ "$(wc -l < "$FILE")" -lt 3 ]; then
       echo "⛔ GATE BLOCKED: ${REPORT} is a stub — the agent did not actually run"
     fi
   done
   # Reconciliation must have no unresolved BLOCKING findings.
   for REPORT in specs_vs_impl.md spec_test_coverage.md; do
     FILE="agent_state/phases/${PHASE}/reports/${REPORT}"
     if [ -f "$FILE" ] && grep -qiP 'BLOCKING' "$FILE"; then
       echo "⛔ GATE BLOCKED: ${REPORT} has BLOCKING reconciliation findings — resolve or carry forward with reason"
     fi
   done
   ```

2. Run regression test suite using **change-impact analysis** (see `.claude/skills/core/change-impact-analysis.md`):

   ```bash
   # Determine regression scope based on what this phase changed
   CHANGED_FILES=$(git diff --name-only $(git log --format=%H -1 -- agent_state/phases/$((PHASE-1))/gate.passed 2>/dev/null || echo HEAD~20) HEAD)
   CHANGED_PACKAGES=$(echo "$CHANGED_FILES" | xargs -I{} dirname {} | sort -u)

   # Check if shared layers changed (schema, auth, middleware, config)
   SHARED_CHANGED=$(echo "$CHANGED_FILES" | grep -E '(migration|schema|middleware|auth|config|docker)' | head -1)

   if [ -n "$SHARED_CHANGED" ] || [ "$PHASE" -eq 1 ]; then
     echo "Shared layer changed or Phase 1 — running FULL regression"
     # Full regression: all tests, all phases
     # Read commands from IMPLEMENTATION_GUIDELINES
   else
     echo "Running change-impact regression (affected packages only)"
     # Targeted regression: only tests in/importing changed packages
     # + always run E2E (catches integration issues)
   fi
   ```

   **Safety rules:** Phase 1, forced gates, and shared-layer changes always trigger full regression. See `change-impact-analysis.md` for the complete algorithm.

3. Run Gate Verification Layers 1–3 (`gate-verification.md`). Write
   `agent_state/phases/${PHASE}/reports/gate_score.md` with the evidence table + numeric score.

4. Gate passes ONLY when: Layer 0 clean AND **roster complete (0b passed)** AND **no pending debate
   without a verdict (0c)** AND **no BLOCKING reconciliation findings** AND Layer 1 has zero unproven
   items AND `gate_score ≥ 0.90` AND no Layer 3 claim was refuted → write gate.passed + manifest.json
   + git tag. Also write the phase decision + worklog rollup (see Post-Gate).

5. If any layer fails → DO NOT write gate.passed. Route failures back to Wave 5 with the specific
   unproven items / low-scoring dimensions named.

**Auto-checkpoint:** Write `checkpoints/wave-6.json` with `tests_passing: true`, `gate_score: <score>`, `artifacts_produced: ["gate.passed", "manifest.json", "reports/gate_score.md"]`.

---

## Post-Gate: CONSOLIDATE + LEARN (inspired by agentmemory's consolidation pipeline)

**Runs ONLY after gate.passed is written.** This step extracts reusable knowledge from the phase execution for future phases. It's the equivalent of agentmemory's `consolidate` → `crystallize` → `lessons` pipeline, but deterministic and structural.

The PARENT session (inline, no subagent) reads all phase artifacts and writes `agent_state/phases/${PHASE}/lessons.md`:

### 1. Extract Lessons

Read:
- `reports/collective_feedback.md` — what bugs were found and how they were fixed
- `reports/quality_gate.md` (+ `code_review_I.md`, `code_review_II.md`) — what patterns were flagged
- `execution.jsonl` — which agents failed/retried and why
- `checkpoints/` — how long each wave took

Write `agent_state/phases/${PHASE}/lessons.md` using the **structured lessons format** (see `.claude/skills/core/structured-lessons.md`):

```markdown
# Phase ${PHASE} Lessons Learned
Generated: <timestamp>
Phase goal: <from PHASE_PLAN.md>

## Entries

### L-${PHASE}-001
- **Category:** <testing|implementation|security|performance|infrastructure|agent_performance|planning|ux>
- **Tags:** <language, domain, pattern name — comma-separated>
- **Type:** <pattern_that_worked|issue_encountered|agent_issue|anti_pattern|recommendation>
- **Summary:** <one-line description>
- **Detail:** <2-3 lines with context>
- **Evidence:** <which report/file proves this>
- **Reuse:** <actionable instruction for future phases>

(repeat for each lesson extracted from reports)
```

Each entry is categorized and tagged so downstream agents can query by domain instead of loading the entire file.

**⛔ Then aggregate into the root lessons index — this closes a broken loop.** The retrieval recipes
in `memory-as-tools.md` read `agent_state/lessons.md` (repo root), but lessons are WRITTEN per-phase
to `agent_state/phases/N/lessons.md`. Without this step `memory_search` finds nothing. After writing
the per-phase file, append its entries to the root index so future phases actually see them:

```bash
ROOT="agent_state/lessons.md"
PHASE_LESSONS="agent_state/phases/${PHASE}/lessons.md"
if [ -f "$PHASE_LESSONS" ]; then
  if [ ! -f "$ROOT" ]; then
    printf '# Lessons (cross-phase index — appended after each phase gate)\n\n' > "$ROOT"
  fi
  {
    printf '\n<!-- ==== Phase %s (gated %s) ==== -->\n' "${PHASE}" "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    # Copy the ### L-* entries from the phase file into the root index (skip the phase header).
    awk '/^### L-/{p=1} p{print}' "$PHASE_LESSONS"
  } >> "$ROOT"
fi
```
`/consolidate` later dedups/compresses this root index (off the hot path). Keep the per-phase file as
the source; the root index is the queryable aggregate.

### 2. Update Cross-Phase Patterns (append-only, indexed)

> **Skill reference:** `.claude/skills/core/structured-lessons.md` — full indexed format with confidence levels.

If `agent_state/patterns.md` exists, append new patterns with structured indexing. If not, create it.

```markdown
# Accumulated Patterns (auto-updated after each phase gate)

## Index by Category
- testing: P-001, P-003
- implementation: P-002

## Index by Tag
- go: P-001, P-002
- react: P-003

## Entries

### P-001
- **Source:** Phase ${PHASE}, L-${PHASE}-001
- **Category:** <category>
- **Tags:** <tags>
- **Pattern:** <what to do>
- **Evidence:** <which phases validated this>
- **Confidence:** LOW | MEDIUM | HIGH | DEPRECATED
```

Confidence upgrades automatically: LOW after 1 phase → MEDIUM if no contradictions → HIGH after validation in 2+ phases. Patterns that cause issues get downgraded to DEPRECATED.

This file is read by `project_planner` when planning Phase N+1 — agents query the index by category/tag instead of loading all entries.

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

### 4. Phase Summary + Worklog Rollup (activity consolidation)

Individual reports answer "what did agent X find"; nobody assembles "what happened this phase." Write
a per-phase narrative that rolls up every wave, then regenerate the consolidated project ledger so a
human or a NEW session has one place to read.

**4a. Write `agent_state/phases/${PHASE}/PHASE_SUMMARY.md`** — a wave-by-wave narrative assembled
from the reports each wave already produced (not new analysis, just consolidation):

```markdown
# Phase ${PHASE} Summary — <goal>
Gate: PASSED (score <N>) · <date> · <NN> agents · <duration>

## What was built (Wave 2)
- <components/routes/migrations from manifest.artifacts>

## Tests (Wave 3)
- unit <N> / integration <N> / e2e <N> — all passing; TC-* coverage <N>%

## Review + Reconcile (Wave 4)
- code_review_I/II: <blocking resolved>; security: <findings>; deps: <CVEs>
- spec↔impl: <MISSING/EXTRA resolved>; spec↔test: <coverage>

## Decisions made
- <ADR-NNN / debate verdicts — link to docs/DECISIONS.md D-NNN entries>

## Fixed this phase (Wave 5)
- <bugs found → fixed, with the failure classification>

## Deferred / carried forward
- <known_issues + carried_forward + deferred TC IDs, with severity>
```

**4b. Regenerate the consolidated ledger:** run `/worklog` (it reads manifest + PHASE_SUMMARY +
DECISIONS + execution.jsonl and rewrites `docs/WORKLOG.md`). Commit `docs/WORKLOG.md` and
`docs/DECISIONS.md` with the gate.

**4c. Promote phase decisions:** ensure every decision captured in
`agent_state/phases/${PHASE}/decision-log.md` that has lasting scope has a `D-NNN` entry in
`docs/DECISIONS.md` (debate/ADR agents do this automatically; sweep here for dev/reconciler
deviations that weren't promoted). This is what makes decisions survive into the next session.
