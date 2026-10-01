<!-- Part of /develop (~/.claude/commands/startup/develop.md). Read when executing this step. -->

## Step 7 — Report

```text
✅ Phase N complete

  Implemented:
    Backend: N services, N repositories, N API routes
    UI:      N screens (or: not a UI phase)
    DB:      N migrations applied

  Tests:
    Unit:        X/X passed
    Integration: X/X passed
    E2E:         X/X passed (or: not run this phase)

  Reconciliation:
    Spec ↔ Impl:   PASS (or: N missing, N unspecced flagged)
    Spec ↔ Tests:  PASS (or: N untested HIGH behaviors)

  Optimization:
    Dead code removed: N items (-X lines)
    Optimizations applied: N (code reduction: X, performance: Y, structural: Z)
    Flagged for review: N items

  Acceptance:
    Use cases:   X/X passed  (FR-001, FR-002, FR-003)
    Personas:    [Admin User, End User]
    Seed data:   agent_state/phases/N/test-data/generated-seed.yaml

  Reviews:
    Code style:    PASS (or: N known issues logged)
    Architecture:  PASS
    Security:      PASS

  Gate: agent_state/phases/N/gate.passed ✅
  Manifest: agent_state/phases/N/manifest.json ✅

  ▶ Next: /plan --phase=N+1
  ▶ After all phases: /accept (global acceptance across full product)
```

### Execution Summary

Read `agent_state/phases/${PHASE}/execution.jsonl` and render:

```text
Phase ${PHASE} Execution (total: Xm Ys)
  <agent_name>        Xm Ys  ✅|⚠|❌  <findings summary>
  ...

Slowest agent: <name> (Xm Ys)
Total agents: N run, N failed, N retried
```

Write the pipeline_complete entry to the execution log:
```bash
echo "{\"ts\":\"$(date -u +%Y-%m-%dT%H:%M:%SZ)\",\"event\":\"pipeline_complete\",\"phase\":${PHASE},\"status\":\"<gate_passed|gate_failed|gate_forced>\",\"total_duration_s\":<N>,\"agents_run\":<N>,\"agents_failed\":<N>}" >> "agent_state/phases/${PHASE}/execution.jsonl"
```

---

> Config blocks checked 2026-09-30 (`bash tests/archetype-compile/config-packs/run.sh --live`): 1 bash block: bash -n (macOS bash 3.2.57) + shellcheck 0.11.0.
