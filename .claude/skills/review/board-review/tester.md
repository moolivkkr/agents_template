---
skill: board-hat-tester
description: Board review hat — tester / test architect. Can the gate see a failure, is coverage proven rather than counted, is evidence fresh and from the right environment, flake policy, oracles from the spec
version: "1.0"
tags:
  - review
  - board-review
  - testing
---

# Hat: tester (QA lead / test architect)

Follow `protocol.md` in this directory (format, severity, evidence, report-everything). Prefix: `TEST`.

**Your question:** if the work these agents produce were broken, would the pipeline notice? A
check that can't fail isn't a check.

## Read

- every target agent
- `.claude/hooks/verify-gate.sh`, `tc-inventory.py`, `debate-status.py`, `acceptance-map.py` (as relevant)
- `skills/testing/*` used by the targets
- the orchestrator's test waves

## Checklist

1. **The gate sees failures.** For every result a target produces, find the code that reads it.
   - **Simulate it:** build a fixture where the result is a failure (failed tests, a FAIL verdict, a
     pending decision) and run the real gate on it. A gate that passes is a CRITICAL finding.
   - **Show your work:** put the fixture and the command in `evidence`.
2. **Proven, not counted.** Coverage must count only tests that ran and passed, named with the ID.
   Look for counting that accepts an ID in a comment, a skipped test, a range, or another phase's
   test.
3. **Fresh evidence.** Results must describe the code being gated (commit sha, clean tree). Look
   for evidence produced before the last fix and still accepted.
4. **The right environment.** Tests must target the build the gate certifies (the deployed URL,
   qa), not a dev server or localhost the agent started itself.
5. **Flakes.** A pass on retry is a failure. Quarantine needs an issue link and an expiry. Silent
   retries are findings.
6. **Oracles.** Expected values must come from the spec or requirement, not from the
   implementation. Tests "written to the code" can't catch what the code gets wrong.
7. **Tests that can fail.** Check for red-first on bug fixes, mutation or other evidence that tests
   kill wrong code, and negative, abuse and failure-mode cases next to the happy path.
8. **Independent re-run.** Someone other than the writer re-runs the suite at the gated commit.
   Self-graded results are a finding.
9. **Measurable judgment.** For agents that judge (reviewers, arbitrators, selectors), check
   whether an eval task can show that a change to them helped or hurt.

## Defect classes the 2026-09-30 run found (check they're still fixed)

- the gate passed a phase whose e2e and acceptance reports said FAIL
- TC coverage counted by ID string
- test results from before the Wave 4/5 fixes
- web E2E before the deploy
- "FLAKY" routed to "re-run only the failures"
