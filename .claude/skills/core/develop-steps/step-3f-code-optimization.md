<!-- Reference for /optimize (~/.claude/commands/startup/optimize.md). NOT part of /develop. -->

## Step 3f — Code Optimization (/optimize only — NOT part of /develop)

> **Not part of `/develop`.** The optimizers run only through `/optimize`, with a green baseline
> before and after. Their own rules apply: tests and mocks are read-only (a failing test means revert
> the change), dead code is proven by static reachability, error handling is never removed, and scope
> comes from `base_sha`. Board review 2026-09-30 (DEV-01/06/07, TEST-14, ARCH-15/16).

**Runs:** only via `/optimize`, on the diff since the phase's `base_sha` (or `/optimize --since`).

### Why it exists (and why it's opt-in)

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
# Record the pre-optimization commit (no tags, no resets)
PRE_SHA="$(git rev-parse HEAD)"
```

If ALL optimizations need to be reverted:
```bash
git revert --no-edit "${PRE_SHA}..HEAD"   # undo the optimization commits without discarding anyone's work
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
1. **Pass 1 — Dead code removal** (only code a static reachability tool proves unused — knip, deadcode/U1000,
   vulture — after a registration search for DI, reflection, routes and flags; "tests still pass" proves nothing)
2. **Pass 2 — Code optimization** (risky — changes code paths)
3. Each change committed individually for granular revert
4. Each change must include the files affected and what was changed

**Outputs:**
- `agent_state/phases/${PHASE}/reports/code_optimization.md` — backend/API optimization report
- `agent_state/phases/${PHASE}/reports/ui_code_optimization.md` — UI optimization report (if frontend)

---
