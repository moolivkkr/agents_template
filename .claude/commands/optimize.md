---
command: optimize
description: "Standalone code optimization — dead code removal, code reduction, performance improvements. Runs tests + review before AND after, shows comparison. Works on backend + UI in parallel."
arguments:
  - name: phase
    required: false
    description: "Target phase (default: auto-detect latest completed phase). Scopes optimization to files changed in that phase."
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
  - name: aggressive
    required: false
    default: false
    description: "Include MEDIUM-confidence dead code removal and suggested optimizations (default: only CERTAIN/HIGH)"
---

# /optimize — Standalone Code Optimization

Runs the full optimization pipeline outside of `/develop` with before/after comparison. Can run at any time — not limited to phase boundaries.

```
Step 0  Scope & Snapshot      Determine files, tag pre-optimize state
Step 1  BEFORE baseline       Run tests + review + capture metrics
Step 2  Optimize              Dead code removal + code optimization (backend || UI)
Step 3  AFTER measurement     Re-run tests + review + capture metrics
Step 4  Compare               Before/after delta
Step 5  Verdict               CLEAN / PARTIAL / REVERTED + commit or rollback
```

---

## Step 0 — Scope & Snapshot

```bash
if [ -n "$ARG_PHASE" ]; then
  PHASE=$ARG_PHASE
  SCOPE_FILES=$(git diff --name-only agent_state/phases/$((PHASE-1))/gate.passed..agent_state/phases/${PHASE}/gate.passed 2>/dev/null)
else
  LAST_PHASE=$(ls agent_state/phases/*/gate.passed 2>/dev/null | grep -oP 'phases/\K\d+' | sort -n | tail -1)
  if [ -n "$LAST_PHASE" ]; then
    PHASE=$LAST_PHASE
    SCOPE_FILES=$(git diff --name-only agent_state/phases/$((PHASE-1))/gate.passed..HEAD 2>/dev/null)
  else
    SCOPE_FILES=$(git ls-files 'src/' 'internal/' 'pkg/' 'web/src/' 'tests/')
  fi
fi
BACKEND_FILES=$(echo "$SCOPE_FILES" | grep -E '^(src/|internal/|pkg/|tests/)' | grep -v '^(src/ui/|web/)')
UI_FILES=$(echo "$SCOPE_FILES" | grep -E '^(web/src/|src/ui/|src/components/|src/hooks/|src/pages/)')
```

### Pre-optimization snapshot
```bash
git tag "optimize-before-$(date +%Y%m%d-%H%M%S)" HEAD
```

Load: `docs/IMPLEMENTATION_GUIDELINES.md`, `agent_state/agent_registry.json`, `docs/design/phases/${PHASE}/specs/api-contracts.md`

---

## Step 1 — BEFORE Baseline

### 1a — Run full test suite
Capture: backend unit/integration, UI component/e2e results (total/passed/failed).

### 1b — Code review (style pass only)
**Agent:** `code_reviewer_I` — capture dead_code, complexity, style findings counts.

### 1c — Code metrics
Capture: lines of code, function/component count, test coverage, bundle size (UI).

Write baseline: `agent_state/optimize/before.yaml`

---

## Step 2 — Optimize + Test + Fix Loop

**Dry run:** both agents report projected changes, skip to Step 4.

### 2a — Backend Optimization (parallel with 2b)
**Agent:** `code_optimizer` | **Skip if:** `--ui_only` | **Scope:** `$BACKEND_FILES`

### 2b — UI Optimization (parallel with 2a)
**Agent:** `ui_code_optimizer` | **Skip if:** `--backend_only` or no frontend | **Scope:** `$UI_FILES`

### Per-optimization iteration cycle

```
FOR each optimization candidate:
  1. APPLY → commit with descriptive message
  2. TEST → run relevant test suite
  3. If PASS → next optimization
  4. If FAIL → fix cycle (max 3 attempts):
     Attempt 1: Diagnose → targeted fix → re-test
     Attempt 2: Broader fix (check all callers) → full test suite
     Attempt 3: Revert original + try alternative approach
     ALL FAIL: Revert all, log as "skipped", continue to next candidate
```

### Immediate revert triggers (no fix attempt)
- Test coverage drops below threshold
- API contract violation (response shape changed)
- Compilation fails across multiple files
- Security test fails

---

## Step 3 — AFTER Measurement

### 3a — Re-run FULL test suite
Catches distant regressions. Failures → same fix cycle as Step 2 (max 3 attempts per, max 5 total reverts → pause and surface).

### 3b — Re-run code review (style pass)
### 3c — Capture code metrics (same as Step 1c)

Write: `agent_state/optimize/after.yaml`

---

## Step 4 — Compare (Before vs After)

Show delta table: code metrics, test results, review findings, optimization actions. Indicators: improved/unchanged/regressed.

---

## Step 5 — Verdict & Commit

- **CLEAN:** All tests pass, no regressions, metrics improved. One commit per optimization (individually revertible).
- **PARTIAL:** Some optimizations reverted (test regressions). Remaining kept. See `reverted.md`.
- **REVERTED:** All optimizations caused cascading failures. Full rollback to pre-tag.
- **PROJECTED:** Dry run — dead code candidates, optimization opportunities, estimated lines removable.

---

## Output Files

| File | Contents |
|------|----------|
| `agent_state/optimize/before.yaml` | Pre-optimization metrics |
| `agent_state/optimize/after.yaml` | Post-optimization metrics |
| `agent_state/optimize/comparison.md` | Side-by-side comparison |
| `agent_state/optimize/backend_report.md` | Backend details |
| `agent_state/optimize/ui_report.md` | UI details |
| `agent_state/optimize/reverted.md` | Reverted optimizations with reasons |

---

## Safety Guarantees

1. **Pre-optimize git tag** — full rollback always possible
2. **One commit per change** — granular revert
3. **Full test suite before AND after** — no silent regressions
4. **Code review before AND after** — proves findings decreased
5. **Auto-revert on test failure** — max 3 cycles then rollback
6. **Dry run mode** — see impact before committing
7. **API contract integrity** — UI optimizer cross-checks against `api-contracts.md`
8. **Scope lock** — only touches files in specified phase/scope
