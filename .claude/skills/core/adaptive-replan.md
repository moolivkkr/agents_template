# Adaptive Replanning Protocol

When Wave 5 (Collective Feedback + Iterate) identifies failures, this protocol determines the **minimum viable fix path** instead of blindly re-running all tiers.

Inspired by GOAP (Goal-Oriented Action Planning): analyze the failure, determine root cause location, predict affected tiers, and re-run only what's necessary — plus one tier above for safety.

---

## Failure Classification

When reading Wave 3+4 reports, classify each failure into one of these categories:

| Category | Signal | Root Cause Location | Fix Scope |
|---|---|---|---|
| **LOGIC** | Unit test assertion failed | Service/domain layer | Fix function → re-run unit + integration |
| **WIRING** | Integration test 404/500, wrong response shape | Handler/router/DI | Fix handler → re-run integration + E2E |
| **CONTRACT** | E2E test shape mismatch, acceptance CONTRACT_VIOLATION | API response serialization | Fix serializer → re-run E2E + acceptance |
| **SCHEMA** | Migration error, DB constraint violation | Migration/model | Fix migration → re-run ALL (schema affects everything) |
| **UI** | Component test render failure, Playwright selector miss | UI component | Fix component → re-run UI + E2E (if UI phase) |
| **CONFIG** | Health check fail, connection refused, env var missing | Docker/config/env | Fix config → re-deploy → re-run integration + E2E + acceptance |
| **FLAKY** | Test passes on retry, timing-dependent | Test setup, race condition | Fix test → re-run ONLY that tier |

## Decision Tree

```
Failure detected
  ├─ Can I identify the root cause from the error output?
  │   ├─ YES → Classify (table above) → Apply minimum re-test scope
  │   └─ NO  → Re-run ALL tiers (safe fallback)
  │
  ├─ Is root cause in a shared layer (DB schema, auth middleware, config)?
  │   ├─ YES → Re-run ALL tiers (shared layers affect everything)
  │   └─ NO  → Use tier-specific re-test scope
  │
  └─ After fix, did git diff touch files outside the predicted scope?
      ├─ YES → Expand re-test scope to include affected tiers
      └─ NO  → Keep minimum scope
```

## Minimum Re-Test Scope by Category

| Category | Must Re-Run | Can Skip | Safety Tier (+1) |
|---|---|---|---|
| LOGIC | unit | E2E, acceptance, UI | + integration |
| WIRING | integration | unit (if unchanged) | + E2E |
| CONTRACT | E2E, acceptance | unit (if unchanged) | (already at top) |
| SCHEMA | ALL | nothing | N/A |
| UI | UI component tests | unit, integration (if unchanged) | + E2E |
| CONFIG | integration, E2E, acceptance | unit | (already broad) |
| FLAKY | failing tier only | all others | none |

**Safety tier rule:** Always re-run one tier ABOVE the affected tier. A unit fix that passes unit tests may break integration. An integration fix may break E2E. The +1 tier catches ripple effects without running everything.

## Fix Agent Prompt Construction

When spawning the fix agent in Wave 5, construct the prompt based on classification:

```
Agent prompt: "Fix these items from collective feedback:

FAILURE CLASSIFICATION: ${CATEGORY}
ROOT CAUSE: ${ROOT_CAUSE_DESCRIPTION}
AFFECTED FILES: ${FILES_FROM_ERROR_OUTPUT}

Items to fix:
${FAILURE_LIST}

After fixing, re-run these tiers (minimum viable scope):
  ${REQUIRED_TIERS}

You may SKIP these tiers (not affected by this fix type):
  ${SKIPPABLE_TIERS}

IMPORTANT: After applying your fix, check git diff. If you touched files
outside the predicted scope (${PREDICTED_FILES}), EXPAND your re-test
to include ALL tiers — the fix was broader than expected.

Verify all required tiers pass before reporting completion."
```

## Multiple Failures Across Categories

When Wave 3+4 reports contain failures in MULTIPLE categories:

1. **Merge upward:** Take the UNION of all required tiers
2. **If any failure is SCHEMA or CONFIG:** Re-run ALL (these are global)
3. **Otherwise:** Run the union set, skip only tiers not in any category's required list

Example:
- Failure A: LOGIC (requires unit + integration)
- Failure B: CONTRACT (requires E2E + acceptance)
- Combined scope: unit + integration + E2E + acceptance = ALL tiers

In practice, 2+ categories usually means ALL tiers. The optimization is most valuable for single-category failures.

## Iteration Budget

- **Cycle 1:** Classified fix → minimum re-test scope
- **Cycle 2:** If Cycle 1 fix didn't resolve → re-classify (the fix may have shifted the category). Apply new minimum scope.
- **Cycle 3:** If still failing → fallback to ALL tiers. If STILL failing → escalate (debate_moderator or user).

**Never exceed 3 cycles.** Infinite fix loops waste more tokens than running all tiers once.

## Logging

Every Wave 5 fix cycle must log the classification to `collective_feedback.md`:

```markdown
## Fix Cycle N
Classification: ${CATEGORY}
Root cause: ${DESCRIPTION}
Files changed: ${GIT_DIFF_FILES}
Re-test scope: ${TIERS_RUN} (skipped: ${TIERS_SKIPPED})
Result: PASS / FAIL
Scope expansion: YES (touched ${EXTRA_FILES}) / NO
```

This data feeds into Post-Gate lessons — patterns of which categories appear most often inform future planning.

## Dual-Ledger Integration

This protocol answers **WHAT to re-run** — the failure-classification table maps a failure to
its minimum re-test scope. It does **not** answer **WHEN to stop iterating** and change
strategy, or when to escalate to a human. A fix agent following only this protocol can loop
forever re-classifying and re-running while making zero real progress.

`dual-ledger-replan.md` supplies the missing self-monitoring loop (Magentic-One dual-ledger +
stall detection). They compose along a clean seam:

| Question | Owner |
|---|---|
| **WHEN** replan vs keep iterating vs escalate | `dual-ledger-replan.md` (Progress Ledger stall rule + replan cap) |
| **WHAT** to re-run once we've decided to fix | this skill (classification table → minimum scope) |

Flow in Wave 5: the orchestrator's **Progress Ledger** watches for a stall (`loop_count > 2`
with no new fact, or a repeated action with no progress). Until it stalls, each cycle uses the
classification table above to pick scope — normal adaptive replanning. On a **stall**, the
orchestrator self-reflects, falsifies its lowest-confidence assumption, and **rewrites the
plan** — which typically means **re-classifying** the failure (e.g. LOGIC → WIRING), and that
new class drives the new minimum scope via this table. After the tier-appropriate replan cap
(`sdlc-config.json` retry caps), it escalates.

So classification still owns scope end-to-end; the ledger decides when to trust the current
classification versus tear it up and re-classify. See `dual-ledger-replan.md` for the ledger
formats and the exact stall → replan → escalate rule.
