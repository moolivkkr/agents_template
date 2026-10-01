<!-- Part of /develop (~/.claude/commands/startup/develop.md). Read when executing this step. -->

## Step 3g — Post-Optimization Test Re-run (CONDITIONAL SAFETY GATE)

**Runs after:** Step 3f optimization completes
**Purpose:** Verify that NO optimization introduced a regression
**Skip if:** Both optimizers report zero changes (no dead code removed, no optimizations applied). Log: "Step 3g skipped — zero optimization changes."

If ANY optimization was applied:

### Execution

Re-run ALL test tiers that passed in Step 3a-3c:

```
Re-run 3g.1: Unit tests           → must still pass
Re-run 3g.2: Integration tests    → must still pass
Re-run 3g.3: E2E tests            → must still pass (if they ran in 3c)
```

### On failure

If ANY test fails after optimization:

1. **Identify which optimization caused the failure** — check `git log "${PRE_SHA}..HEAD"` (PRE_SHA is
   recorded before Step 3f starts; no tags)
2. **Diagnose and fix first** (don't blindly revert):
   - Read test failure output → identify root cause (missing import, broken caller, type mismatch)
   - Apply targeted fix → commit as `fix: resolve <issue> after <optimization>`
   - Re-run failing test → if passes, continue
3. **If fix doesn't work** — try broader fix (check all callers of changed code, fix all affected)
4. **If still failing after 2 fix attempts** — revert the specific optimization commit + fix attempts:
   ```bash
   git revert --no-edit "<commit-hash>"   # <commit-hash>: the optimization commit from step 1
   ```
5. **Max 3 revert cycles** — if tests still fail after 3 optimization reverts:
   - Return to the pre-optimization state by reverting, never resetting (a reset discards everyone's
     uncommitted work): `git revert --no-edit "${PRE_SHA}..HEAD"`
   - Log in report: "⚠ All optimizations reverted — optimization introduced non-recoverable regression"
   - Pipeline continues (optimization failure is NOT a pipeline blocker, but IS logged in gate)
6. **Update the optimization report** with fixed and reverted items

### Output

Updates `agent_state/phases/${PHASE}/reports/code_optimization.md` with:
```markdown
## Post-Optimization Test Re-run
- Unit tests: PASS (X/X)
- Integration tests: PASS (X/X)
- E2E tests: PASS (X/X) | not run
- Reverted optimizations: N (or: none)
- Status: CLEAN | PARTIAL (N optimizations reverted) | REVERTED (all rolled back)
```

### Gate impact

The Phase Gate (Step 6) checks the post-optimization test status:
- `CLEAN` → no issues, all optimizations kept
- `PARTIAL` → some optimizations reverted, remaining tests pass → acceptable
- `REVERTED` → all rolled back, code is at pre-optimization state → acceptable (logged as known issue)
- Tests still failing → **BLOCKER** (should not happen if revert protocol followed)

---

> Config blocks checked 2026-09-30 (`bash tests/archetype-compile/config-packs/run.sh --live`): 1 bash block: bash -n (macOS bash 3.2.57) + shellcheck 0.11.0.
