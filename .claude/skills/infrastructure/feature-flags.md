---
skill: feature-flags
description: Feature flags — flag types (release/ops/experiment/permission), evaluation, cleanup discipline, kill-switches, config management
version: "1.0"
tags:
  - feature-flags
  - release
  - kill-switch
  - experimentation
  - config
  - infrastructure
---

# Feature flags — decouple deploy from release, and keep the flag set from becoming a swamp.

> Go sample compile-checked (go build + go vet) 2026-09-30 with Go 1.27.1 (tests/archetype-compile/go/run.sh).

A feature flag lets code ship dark and turn on independently of the deploy. That power comes with a debt:
every flag is a branch in production. The discipline is knowing **which kind of flag you have**, because
each type has a different lifetime and cleanup rule.

## Flag types (each has a different lifespan)
| Type | Purpose | Lifespan | Owner |
|------|---------|----------|-------|
| **Release (transient)** | Ship code dark, ramp on (canary → %→ 100%) | Days–weeks; **delete after full rollout** | Feature dev |
| **Ops / kill-switch** | Disable an expensive or fragile subsystem under load/incident | Long-lived, permanent | SRE / on-call |
| **Experiment (A/B)** | Route cohorts to variants, measure a metric | Life of the experiment; delete when decided | Product / data |
| **Permission / entitlement** | Gate features by plan, tenant, or role | Permanent (it's a business rule, not a toggle) | Product |

The mistake is treating all four the same. A **release flag that lives forever** is dead debt; a
**permission flag you try to "clean up"** breaks billing. Tag every flag with its type at creation.

## Evaluation
- Evaluation is a **pure function of (flag, evaluation context)** → variant. Context = user/tenant id,
  plan, role, region, and a stable bucketing key. Same inputs → same result (deterministic).
- Bucketing for % rollouts uses a **hash of a stable id** (e.g. `hash(tenant_id + flag_key) % 100 < pct`),
  not a random draw — so a tenant doesn't flicker between variants on every request.
- **Default to OFF / control.** If the flag service is unreachable, evaluate to the safe fallback, never
  fail the request. Cache the last-known ruleset locally and serve it during an outage.
```go
// Evaluation is deterministic and fails safe.
func (f *Flags) Enabled(key string, ctx EvalContext) bool {
    rule, ok := f.snapshot.Get(key)     // local cached snapshot — no network on the hot path
    if !ok {
        return false                    // unknown flag → OFF (fail safe)
    }
    if rule.KillSwitch { return false } // ops override wins over everything
    return bucket(ctx.StableID, key) < rule.RolloutPct || rule.matchesTargeting(ctx)
}
```
- Keep evaluation **out of the request's critical path network-wise**: SDK evaluates against a locally
  cached ruleset that syncs in the background (streaming/poll). Never a synchronous call to a flag API per
  request.
- Log/emit the variant served (as an analytics event) for experiments and for debugging "why did this
  user see X".

## Kill-switches (ops flags)
- Every risky or expensive subsystem (a new integration, a heavy report, a third-party dependency) ships
  behind a kill-switch so on-call can disable it **without a deploy**.
- Kill-switch flips must take effect in seconds (short poll interval / streaming), not on the next release.
- The switch's OFF state must be a **graceful degradation**, not an error — return cached/empty/limited
  results, don't 500. Design the "off" behavior deliberately.
- Kill-switches are permanent infrastructure; document them and their blast radius in the runbook.

## Cleanup discipline (the part everyone skips)
Stale flags are the top source of feature-flag pain — dead code paths, confusing branches, "is this flag
still doing anything?" archaeology.
- **Every release/experiment flag gets an expiry date and an owner at creation.** No expiry = not merged.
- Flip fully on (or off), let it bake, then **delete the flag and the losing code branch** — do not leave
  `if flag { new } else { old }` in the tree. A rolled-out flag that stays is dead debt.
- Run a periodic **stale-flag audit** (a scheduled report / linter): flags past expiry, flags at 100% for
  >N days, flags evaluated but never toggled. Treat overdue flags as a cleanup ticket, not a warning to ignore.
- A linter can fail CI on a hardcoded flag key with no registry entry, or a flag referenced in code but
  absent from the flag config (typo → permanent OFF).

## Config management
- Flag definitions live in a **managed store / flag service** (LaunchDarkly/Flagsmith/Unleash/OpenFeature,
  or a versioned config in your own DB) — the source of truth, audited, with change history and who-flipped-what.
- Flag *keys* are constants in code (a typo'd key silently evaluates OFF); the *values/targeting* live in
  the store. Never scatter magic string keys across the codebase.
- Changing a flag's targeting is a production change — it needs the same audit trail as a deploy (who,
  when, why). Rollout changes are a common incident cause precisely because they bypass code review.
- Keep prod and non-prod flag state separate; don't let a staging experiment leak targeting into prod.

## Rules
- Tag every flag with a type (release/ops/experiment/permission) — the type dictates its lifespan and owner.
- Release and experiment flags carry an expiry + owner at birth; overdue ones are cleanup tickets, not noise.
- Evaluation is deterministic, cached locally, and **fails safe (OFF/control)** on any flag-service outage.
- Kill-switches flip in seconds without a deploy and degrade gracefully — the OFF path is a designed behavior.
- Delete the flag AND the losing branch after full rollout; a permanently-on release flag is dead code.
- Flag definitions live in an audited store; keys are constants in code, targeting lives in config.

## Testing note
Test **both variants of every branch** — a flag guarding new code means the old and new paths each need
coverage (a test suite that only runs the ON path ships an untested OFF fallback). Assert evaluation is
deterministic for a fixed context, fails to the safe default when the flag store is stubbed unreachable,
and that a kill-switch OFF returns the graceful-degradation response (not a 500). For % rollouts, test that
bucketing is stable across repeated evaluations for the same id.
