# Framework Eval Suite

This is the fixed, versioned suite `/eval` runs to measure the framework's OWN output quality —
so a prompt/skill/wave change can be proven to help, wash, or hurt instead of being changed blind.

**Read `.claude/skills/core/eval-harness.md` first** — it defines the two scoring modes
(OUTCOME + TRAJECTORY), the metrics, the before/after protocol, and the verdict thresholds. This
README only covers the layout and how to add a task.

## Layout

```
agent_state/eval/
  suite/<task-id>/
    task.md                   # the mini requirement/spec fed to the framework (human-readable)
    rubric.json               # OUTCOME checks — weighted, machine-verifiable (Σ weights = 1.0)
    expected_artifacts.json   # files that must exist + per-file assertions
    expected_trajectory.json  # TRAJECTORY — the agent/wave call path that SHOULD happen + forbidden
  baselines/<date>-<sha>.json # a run promoted to a baseline (compare target)
  runs/<date>-<sha>-<mode>.json  # every run's record (run | baseline | compare)
  README.md                   # this file
```

## The seeded tasks

| Task | Surface | Framework path exercised | Regression class it guards |
|------|---------|--------------------------|----------------------------|
| `T-001-crud-endpoint` | backend endpoint | `/develop` slice | IDOR / missing-tenant-scope; endpoint without integration tests |
| `T-002-ui-form` | UI form | `/plan` UI spec → `/develop` UI wave | UI without ux_designer spec / a11y check; spec-vs-component validation drift |
| `T-003-hotfix-idor` | bug fix | `/hotfix` | fast-track fix that skips the red-first reproduction test or the security review |
| `T-004-gate-blocks-missing-review` | multi-phase gate (NEGATIVE) | `verify-gate.sh` Wave-6 gate | the linchpin: gate silently passing an incomplete roster / gate.passed without evidence |
| `T-005-reconcile-drift` | reconciliation | `/recon` bare then `--fix=docs` | bare recon mutating files; `--fix=docs` erasing as-built behavior |
| `T-006-plan-small-phase` | planning | `/plan --phase=N` | spec that under-enumerates TC-* IDs (root cause of traceability-gate failures) |

Tasks are chosen SWE-bench-Pro / Terminal-Bench style: small but end-to-end, deterministic rubric,
spread across pipeline surfaces. `T-004` is a **negative-path** task — success means the gate
correctly REFUSES to pass; it is the mechanized proof that enforcement is code, not prose.

## Rubric check vocabulary

`rubric.json` and `expected_artifacts.json` use these machine-verifiable check kinds (the `/eval`
driver re-verifies each one itself — never trusts a report):

| check | meaning |
|-------|---------|
| `artifact_exists` | `path` exists |
| `grep_present` | `pattern` (ERE) matches somewhere under `path` |
| `grep_absent` | `pattern` matches NOWHERE under `path` |
| `count_at_least` | `pattern` occurs `>= min` times under `path` |
| `command_passes` | `cmd` exits 0 |
| `command_fails` | `cmd` exits non-zero (used by negative-path tasks) |
| `command_output_contains` | `cmd`'s output contains `pattern` |
| `manifest_gate_not_passed` | the manifest at `path` does NOT have `.gate.passed == true` |
| `no_source_change_on_bare_run` | `git status` shows no spec/source file modified by a read-only run |

`${EVAL_PHASE}` in a check is substituted by the driver with the scratch phase number the task ran
in, so tasks stay isolated and don't collide with real project phases.

## How to add a task

1. `mkdir agent_state/eval/suite/T-00N-<slug>/`.
2. Write **`task.md`** — a real, self-contained mini requirement with an explicit Definition of Done
   and a "why this task exists" note naming the regression class it guards. No placeholders.
3. Write **`rubric.json`** — OUTCOME checks whose weights sum to 1.0, each machine-verifiable
   (grep / command / file assertion — never "looks good").
4. Write **`expected_artifacts.json`** — the files that must exist with per-file assertions.
5. Write **`expected_trajectory.json`** — the required agent/wave steps (`must:true`) in order, plus
   a `forbidden` list (e.g. "gate.passed before security_reviewer ran").
6. Run `/eval --task T-00N-<slug>` to debug it, then `/eval --baseline` to fold it into the suite.

## Rules (from eval-harness.md — do not violate)

- A verdict ALWAYS runs the FULL suite. `--task` is debug-only (regression blindness).
- One framework change per before/after cycle — otherwise the diff is uninterpretable.
- Record `suite_sha` on every run; never silently compare across a changed suite.
- **Never delete a task to make a verdict look better.** A task that once caught a real regression
  stays permanently.
- `/eval` measures THIS framework repo against this fixed suite — not a downstream project's code.

## Baseline

`baselines/2026-07-07-seed.json` is the committed seed baseline recorded when this suite was first
created. `outcome_score`/`trajectory_score` are `null` there (the suite has not yet been executed by
`/eval` — the first `/eval --baseline` run replaces it with measured scores). It exists so
`/eval --compare` has a target and so the suite's shape is version-pinned from day one.
