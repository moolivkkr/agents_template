---
command: optimize
description: "Standalone code optimization — dead code removal proven by static analysis, plus safe, behaviour-preserving optimizations. Runs tests + review before AND after and shows the comparison. Works on backend + UI in parallel. The only entry point for code_optimizer and ui_code_optimizer; not part of /develop."
arguments:
  - name: phase
    required: false
    description: "Target phase (default: the latest phase with a gate). Scopes optimization to files changed in that phase."
  - name: since
    required: false
    description: "Explicit base commit for the scope (overrides the phase's recorded base_sha). Required for phases that predate base_sha recording and have no phase-N-complete tag."
  - name: backend_only
    required: false
    default: false
    description: "Optimize backend code only — skip UI"
  - name: ui_only
    required: false
    default: false
    description: "Optimize UI code only — skip backend"
  - name: dry_run
    required: false
    default: false
    description: "Report what WOULD be optimized without making changes"
---

# /optimize — Standalone Code Optimization

> **Spawning agents:** follow `~/.claude/skills/core/child-returns.md`. Wait for every agent you spawn before using its result, and act on its first line: `NEEDS_INPUT` (ask the user, or record a default under `--auto`), `NEEDS_DECISION <topic>` (run `debate_moderator`, then relaunch the agent with the decision), or a progress note (re-spawn it, at most twice).

Clean code, no dead code, effective code — without changing behaviour. Runs the optimization agents
outside of `/develop`, with a before/after comparison of tests, review findings and code metrics.

**Where it fits.** `/optimize` is the **only** entry point for `code_optimizer` and `ui_code_optimizer`.
The canonical `/develop` pipeline (`develop-orchestrator`) does not run them, and a phase gate does not
require their reports. Run it after a phase gates, after a hotfix, or periodically for hygiene.

**The three rules every step below enforces:**
1. Tests, test expectations, mocks, fixtures and snapshots are **never edited** by an optimization. A
   failing test after a change means the change altered behaviour: revert the change.
2. Dead code is proven by **static reachability** (Go `deadcode`/`staticcheck -checks U1000`, knip,
   vulture) plus a registration search — never by "the tests still pass after removal".
3. Error handling and security controls are never removed.

---

## How it works

```
Step 0  Scope & rollback point   Base commit → file lists; record pre_sha
Step 1  BEFORE baseline          Run tests + review + capture metrics (must be green)
Step 2  Optimize                 code_optimizer ∥ ui_code_optimizer on disjoint file lists
Step 3  AFTER measurement        Re-run tests + review + metrics; check no test file changed
Step 4  Compare                  Before/after deltas
Step 5  Verdict                  CLEAN / PARTIAL / REVERTED
```

---

## Step 0 — Scope & rollback point

### Determine the base commit (never HEAD~N)
```bash
if [ -n "$ARG_PHASE" ]; then
  PHASE=$ARG_PHASE
else
  # Latest phase that has a gate record (portable: no grep -P)
  PHASE=$(ls -d agent_state/phases/*/ 2>/dev/null | sed -E 's#.*/phases/([0-9]+)/#\1#' | sort -n \
          | while read -r p; do [ -f "agent_state/phases/$p/gate.passed" ] && echo "$p"; done | tail -1)
fi
if [ -n "$ARG_SINCE" ]; then
  BASE="$ARG_SINCE"
elif [ -n "$PHASE" ] && [ -f "agent_state/phases/$PHASE/base_sha" ]; then
  BASE="$(cat "agent_state/phases/$PHASE/base_sha")"          # written by develop-orchestrator Wave 0c
elif [ -n "$PHASE" ] && git rev-parse -q --verify "refs/tags/phase-$((PHASE-1))-complete" >/dev/null; then
  BASE="$(git rev-list -n1 "phase-$((PHASE-1))-complete")"     # older phases: the previous gate's tag
else
  echo "⛔ BLOCKED: no base commit for phase ${PHASE:-?}. Pass --since=<sha> (the commit the work started from)."; exit 1
fi
git merge-base --is-ancestor "$BASE" HEAD || { echo "⛔ BLOCKED: base $BASE is not an ancestor of HEAD"; exit 1; }
# End of the phase: the next phase's base if it exists, else HEAD
END="$(cat "agent_state/phases/$((PHASE+1))/base_sha" 2>/dev/null || git rev-parse HEAD)"
SCOPE_FILES=$(git diff --name-only "$BASE".."$END")
```

### Split the scope
Derive the backend and UI directories from IMPLEMENTATION_GUIDELINES §1 Project Structure and
`agent_state/agent_registry.json` (for example Go `internal/ cmd/ pkg/`, `services/api/`, a web app in
`web/` or `apps/web/`). Never hard-code `src/`. Then remove everything an optimizer must not edit:
```bash
NOT_EDITABLE='(_test\.go$|\.test\.[jt]sx?$|\.spec\.[jt]sx?$|(^|/)test_[^/]*\.py$|(^|/)(tests?|__tests__|__mocks__|__snapshots__|mocks|fixtures|testdata|e2e)/|\.stories\.|(^|/)migrations/|(^|/)agent_state/|(^|/)docs/)'
BACKEND_FILES=$(printf '%s\n' "$SCOPE_FILES" | grep -E "^(${BACKEND_DIRS})" | grep -vE "$NOT_EDITABLE")
UI_FILES=$(printf '%s\n' "$SCOPE_FILES" | grep -E "^(${UI_DIRS})" | grep -vE "$NOT_EDITABLE")
echo "Scope: phase ${PHASE} ${BASE}..${END}"
echo "  Backend files: $(printf '%s\n' "$BACKEND_FILES" | grep -c .)"
echo "  UI files:      $(printf '%s\n' "$UI_FILES" | grep -c .)"
```

### Rollback point
```bash
mkdir -p agent_state/optimize
git rev-parse HEAD > agent_state/optimize/pre_sha      # the agents verify this before changing anything
PRE_SHA="$(cat agent_state/optimize/pre_sha)"
```
Every optimization is its own commit, so each can be reverted with `git revert`.
Nothing in this command uses `git reset --hard`.

### Load context
- `docs/IMPLEMENTATION_GUIDELINES.md` — tech stack, §Commands and versions
- `agent_state/config/verify-commands.json` — the commands every step runs (regenerate with
  `python3 .claude/hooks/commands-table.py docs/IMPLEMENTATION_GUIDELINES.md --out agent_state/config/verify-commands.json` if missing)
- `docs/design/phases/${PHASE}/specs/api-contracts.md` and `agent_state/phases/${PHASE}/ui_developer/manifest.json` — UI safety checks

---

## Step 1 — BEFORE Baseline

Capture the current state **before** any optimization. This is the baseline for comparison.

### 1a — Run the test suites
Use the commands in `agent_state/config/verify-commands.json` (`commands["test:unit"]`,
`commands["test:integration"]`, `commands["test:ui"]` when present), run with `bash -o pipefail` so
the exit code is the test runner's. Record each command, exit code and counts:
```yaml
before:
  tests:
    backend_unit: { command: "...", exit: 0, total: N, passed: N, failed: 0 }
    backend_integration: { command: "...", exit: 0, total: N, passed: N, failed: 0 }
    ui_component: { command: "...", exit: 0, total: N, passed: N, failed: 0 }
```
**The baseline must be green.** If any suite fails, stop: `⛔ BLOCKED — optimize needs a green
baseline; fix the failures first (/diagnose)`.

### 1b — Code review (style pass only)
```
Agent prompt (subagent_type: code_reviewer_I): "[GROUND TRUTH] Style/idioms/dead-code pass only (skip architecture and security) over these files: ${BACKEND_FILES} ${UI_FILES}. Write agent_state/optimize/review_before.md ending with BLOCKING:N WARNING:N INFO:N, and list dead-code findings separately."
```

### 1c — Code metrics
Lines and files in scope, function/component counts, coverage (the project's coverage command), and
the bundle size from `commands.build` for the UI. Write `agent_state/optimize/before.yaml`.

---

## Step 2 — Optimize

### Dry run mode
If `--dry_run`: both agents report what they WOULD change and make zero modifications. Skip to Step 4
with projected numbers.

### 2a — Backend (parallel with 2b) — skip if `--ui_only`
```
Agent prompt (subagent_type: code_optimizer): "[GROUND TRUTH] Optimize phase ${PHASE}. OPTIMIZE_BASE=${BASE}. Rollback point: agent_state/optimize/pre_sha (${PRE_SHA}). Edit ONLY these files: ${BACKEND_FILES}. Tests, mocks, fixtures and snapshots are read-only; a failing test means git revert that change. Dead code only by static reachability + registration search. Never remove error handling or security controls. One commit per change; stage only the files you changed. Write your reports under agent_state/phases/${PHASE}/reports/."
```

### 2b — UI (parallel with 2a) — skip if `--backend_only` or `frontend.enabled = false`
```
Agent prompt (subagent_type: ui_code_optimizer): "[GROUND TRUTH] Optimize phase ${PHASE}. OPTIMIZE_BASE=${BASE}. Rollback point: agent_state/optimize/pre_sha (${PRE_SHA}). Edit ONLY these files: ${UI_FILES}. Tests, MSW mocks, fixtures, snapshots and stories are read-only; a failing test or snapshot mismatch means git revert that change. Never delete anything listed in agent_state/phases/${PHASE}/ui_developer/manifest.json or named in a wireframe. One commit per change; stage only the files you changed. Write your reports under agent_state/phases/${PHASE}/reports/."
```

### Per-change cycle (what both agents do)
```
FOR each candidate:
  1. APPLY one change → commit it alone
  2. RUN build + typecheck + the tests of the touched packages/components
  3. PASS → next candidate
  4. Build/typecheck error in production code caused by the change (a leftover import, a caller of
     removed dead code) → complete the change in production code once, re-run
  5. ANY test failure or snapshot mismatch → git revert --no-edit <commit>; log "reverted: <test>"
```

| Failure | What happens |
|---|---|
| Missing import after a dead-code removal | Finish the removal in production code (same change), re-run |
| Caller still references removed code | The code wasn't dead: revert |
| Any test assertion fails | Revert. The test is the behaviour contract; it is never edited |
| Snapshot or MSW mock mismatch | Revert. Snapshots and mocks are never updated by an optimizer |
| Coverage drops | Revert the batch: something tested was removed, so it wasn't dead |
| API contract shape changed | Revert immediately |
| Security test fails | Revert immediately |

---

## Step 3 — AFTER Measurement

### 3a — Re-run the full suites
The same commands as Step 1a, across everything. If a suite fails:
1. Find the optimization commit that caused it (`git log --format='%h %s' ${PRE_SHA}..HEAD`, then bisect by reverting candidates).
2. `git revert --no-edit <commit>`; re-run the suite.
3. After 5 reverts in this step, stop and revert every optimization commit
   (`git revert --no-edit ${PRE_SHA}..HEAD`), then report REVERTED and recommend `--dry_run`.

### 3b — No test file changed
```bash
CHANGED_TESTS=$(git diff --name-only "${PRE_SHA}"..HEAD | grep -E "$NOT_EDITABLE")
[ -z "$CHANGED_TESTS" ] || echo "⛔ BLOCKER: optimizers changed test/mock/fixture/migration files: $CHANGED_TESTS — revert those commits"
```
The test counts in 3a must equal the baseline counts.

### 3c — Re-run the style review
Same `code_reviewer_I` spawn as Step 1b, writing `agent_state/optimize/review_after.md`.

### 3d — Code metrics (same measurements as Step 1c)
Write `agent_state/optimize/after.yaml`.

---

## Step 4 — Compare (Before vs After)

Read `before.yaml` and `after.yaml`. Compute deltas and write `agent_state/optimize/comparison.md`:

```
CODE METRICS                Before      After       Delta
Backend lines               4,230       3,980       -250 ✅
UI lines                    3,100       2,850       -250 ✅
Bundle size                 420 KB      395 KB      -25 KB ✅

TEST RESULTS                Before      After       Delta
Backend unit tests          124/124     124/124     0    ✅   (count must not change)
UI component tests          36/36       36/36       0    ✅
Coverage                    82%         83%         +1%  ✅
Test files changed          —           0                ✅   (must be 0)

REVIEW FINDINGS             Before      After       Delta
Dead code findings          12          2           -10  ✅

OPTIMIZATION ACTIONS
Dead code removed           10 items (static-tool evidence cited)
Optimizations applied       8 · reverted 1 · suggested (not applied) 6
```
- ✅ improved or unchanged · ❌ regressed (a test failed, coverage dropped, a test count changed, a
  test file changed, the bundle grew).

---

## Step 5 — Verdict

| Verdict | When |
|---|---|
| **CLEAN** | All suites green, test counts unchanged, no test file changed, metrics improved or stable |
| **PARTIAL** | Some changes were reverted; the remaining ones pass everything above. See `agent_state/optimize/reverted.md` |
| **REVERTED** | Cross-cutting failures: every optimization commit was reverted with `git revert` |
| **PROJECTED** | Dry run: candidates and suggestions only |

---

## Output Files

| File | Contents |
|------|----------|
| `agent_state/optimize/pre_sha` | The rollback point |
| `agent_state/optimize/before.yaml` / `after.yaml` | Metrics, test commands, exit codes, counts |
| `agent_state/optimize/comparison.md` | Side-by-side comparison table |
| `agent_state/optimize/review_before.md` / `review_after.md` | Style review before/after |
| `agent_state/phases/${PHASE}/reports/code_optimization.md` (+ `dead_code.md`, `optimizations.md`) | `code_optimizer`'s reports |
| `agent_state/phases/${PHASE}/reports/ui_code_optimization.md` (+ `ui_dead_code.md`, `ui_optimizations.md`) | `ui_code_optimizer`'s reports |
| `agent_state/optimize/reverted.md` | Reverted optimizations with the failing test or error |

---

## Safety Guarantees

1. **Recorded rollback point** (`pre_sha`) and one commit per change — every change reverts on its own with `git revert`.
2. **Green baseline required**, and the full suites re-run afterwards with unchanged test counts.
3. **Tests are the referee, never edited** — Step 3b fails the run if any test, mock, fixture or snapshot file changed.
4. **Static-reachability evidence** for every removal; error handling and security controls are never removed.
5. **Code review before AND after**.
6. **Dry run mode** to see projected impact first.
7. **API contract integrity** — the UI optimizer checks data-fetching code against `api-contracts.md`.
8. **Scope lock** — only the files changed since the phase's recorded base commit, minus test and migration files.

---

## Examples

```bash
# Optimize the latest gated phase
/startup/optimize

# Backend only, phase 2
/startup/optimize --phase=2 --backend_only

# What WOULD change, without changing anything
/startup/optimize --dry_run

# A phase recorded before base_sha existed
/startup/optimize --phase=1 --since=3f2a9c1
```
