<!-- Part of /develop (~/.claude/commands/startup/develop.md). Read when executing this step. -->

## Step 3f — Code Optimization (MANDATORY)

**Runs after:** All tests pass (Step 3a-3c) AND reconciliation complete (Step 3d-3e)
**Runs before:** Code review (Step 4) — reviewers see clean, optimized code
**Mandatory:** Yes — runs every phase. Produces a report even if zero changes made.

### Why mandatory

Dead code and redundant patterns accumulate across phases. Each agent generates code independently — backend_developer, api_developer, and ui_developer don't coordinate on shared utilities or know what the other has deprecated. Without cleanup at every phase, technical debt compounds and review cycles get longer.

### Scope Lock (CRITICAL SAFETY RULE)

Optimization ONLY touches files that were created or modified in THIS phase. Never modify code from previous phases — it has already passed its own gate.

```bash
# Scope = only files changed since last phase gate
SCOPE_FILES=$(git diff --name-only agent_state/phases/$((PHASE-1))/gate.passed..HEAD 2>/dev/null || git diff --name-only HEAD~50..HEAD)
```

### Pre-optimization snapshot

Before any optimization starts, capture the current state:

```bash
# Tag the pre-optimization state for safe rollback
git tag "phase-${PHASE}-pre-optimize" HEAD
```

If ALL optimizations need to be reverted:
```bash
git reset --hard "phase-${PHASE}-pre-optimize"
```

### Execution — parallel backend + UI tracks

```
Step 3f (parallel):
  ├─ code_optimizer         → backend/API dead code removal + optimization
  │                           Scope: src/domain/, src/services/, src/repositories/, src/api/, src/errors/
  │
  └─ ui_code_optimizer      → UI dead code removal + optimization (if frontend.enabled = true)
                              Scope: src/ui/, src/components/, src/hooks/, src/pages/, src/styles/
```

**Agent:** `code_optimizer` — always runs
**Agent:** `ui_code_optimizer` — runs only if `frontend.enabled = true`

Both agents follow the same safety protocol:
1. **Pass 1 — Dead code removal** (safe — removing unused code can't change behavior)
2. **Pass 2 — Code optimization** (risky — changes code paths)
3. Each change committed individually for granular revert
4. Each change must include the files affected and what was changed

**Outputs:**
- `agent_state/phases/${PHASE}/reports/code_optimization.md` — backend/API optimization report
- `agent_state/phases/${PHASE}/reports/ui_code_optimization.md` — UI optimization report (if frontend)

---
