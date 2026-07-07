# Reproduction-Test-First Self-Repair Loop

## Purpose

The highest-leverage bug-fixing technique from the SWE-bench literature: **before you touch the
production code, write a test that FAILS because of the bug.** Then loop edit → run → repeat until
that test flips fail→pass, while the pre-existing suite stays green.

Agentless reported this single change moving resolved issues from 77→96 / 300 — the difference
between "I think I fixed it" and "I have a fail→pass transition proving I fixed it."

Applies to `/hotfix` (MANDATORY) and `/diagnose --fix` (invoked after root cause is found).

---

## Why fix-then-hope fails

Without a reproducing test, "the fix" is a hypothesis. You cannot distinguish:
- a real fix from a coincidental change,
- a fix from a test that never exercised the bug in the first place,
- "green" from "green because the assertion is wrong."

A failing repro test forces you to demonstrate you actually understand the bug — and gives you a
deterministic signal that flips exactly when the bug is gone.

---

## The Protocol

### Step 1 — Reproduce (write the FAIL-to-pass test)

Write the **minimal** test that fails, demonstrating the bug. Drive it from the symptom / diagnosis:
- Use the reproduction command or root-cause detail (`/diagnose` writes these into its report).
- Exercise the smallest path that triggers the wrong behavior — one input, one assertion.
- Run it. **It MUST fail.**

> If you cannot make the test fail, you have not understood the bug. STOP and investigate —
> do not proceed to a fix. A fix without a red test is not allowed.

### Step 2 — Confirm it fails for the RIGHT reason

A red test is not enough — it must be red *because of the bug*, not because of an unrelated error.

- Read the failure output. The assertion must fire on the **actual symptom** (wrong status code,
  wrong response shape, thrown exception, corrupted value), not on a typo, missing import, unbound
  fixture, compile error, or wrong route.
- If it fails for the wrong reason, repair the test until it fails for the *right* reason, then re-run.
- Record the exact expected-vs-actual so the fail→pass transition is unambiguous later.

### Step 3 — Fix loop (edit → re-run → repeat)

Now edit the production code (never the test):

1. Apply the minimal fix.
2. Re-run the repro test.
3. Still red? Read the failure, refine the fix, go to 1.

**MAX 3 attempts** (aligns with `test_retry_max: 3` in `sdlc-config.json`). After 3 failed attempts,
STOP and escalate to the user — the root cause is likely wrong or wider than the scoped component.
Do not keep grinding.

### Step 4 — Gate (fail→pass + pass-to-pass)

Accept the fix **only** when BOTH hold:

1. **Fail→pass:** the repro test that was RED in Step 1/2 is now GREEN.
2. **Pass-to-pass (no regressions):** the pre-existing suite that was green stays green. Nothing
   that passed before is now failing.

Record the transition as evidence:

```
Repro test:   <test id / path>::<case>   TC-<CAT>-<NNN>
  Before fix: FAIL — <actual symptom>
  After fix:  PASS
Regression:   <N>/<N> pre-existing tests still pass (pass-to-pass)
```

If either condition is unmet, the gate does **not** pass — the fix is not done.

---

## Guardrails (reuse the framework's existing ones)

These are the same absolutes as `/develop` and `/hotfix` test recovery — never relaxed to force green:

- **NEVER** delete, skip, `.only`/`x`/`@Disabled`, or comment out a test to get a green run.
- **NEVER** weaken an assertion or change an expectation to match buggy behavior.
- **NEVER** add `//nolint`, `@ts-ignore`, `# type: ignore`, `eslint-disable`, or `#[allow(...)]`
  to silence the signal instead of fixing the cause.
- **NEVER** downgrade a dependency to make the build pass.
- **Fix the bug, not the test.** In the fix loop, the repro test is read-only except in Step 2 (to
  correct its *reason* for failing) — its intent and assertion on the symptom stay fixed.
- Strip secrets/tokens/connection strings from test output before analysis.
- If the root cause is unclear after reading the failure → STOP and escalate.

---

## The repro test is PERMANENT

The reproducing test is not scratch — it stays in the suite forever as a **regression test**:

- Annotate it with a **TC-* ID** per `.claude/skills/testing/test-case-traceability.md` (use the
  category matching the bug: `TC-API-*`, `TC-AUTH-*`, `TC-DB-*`, etc.; append the next free number).
- It joins the pass-to-pass set for all future runs — this exact bug can never silently return.
- Reference it in the fix's commit message and (for `/hotfix`) the manifest hotfix record.

---

## Quick reference

```
1. RED    — write minimal test, run, confirm it FAILS
2. REASON — confirm it fails on the real symptom, not noise
3. LOOP   — edit code → re-run → repeat (max 3, then escalate)
4. GATE   — repro flips fail→pass AND suite stays green (pass-to-pass)
   → keep the repro test forever, tagged TC-*
```
