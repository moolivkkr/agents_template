---
skill: eval-harness
description: Measure the framework's own output quality — score tasks on outcome and trajectory, compare against a baseline to detect improvement/regression
version: "1.0"
tags:
  - eval
  - quality
  - benchmark
  - trajectory
  - core
---

# Eval Harness Protocol — Measure the Framework's Own Output Quality

The framework changes waves, prompts, and skills to improve output — but it currently changes
them **blind**. 2026 research ("the harness matters more than the model") shows that
harness/prompt changes swing coding-agent success by roughly ±13 points. A change that feels
better can silently regress. This protocol gives the framework a way to measure its OWN output
quality so a prompt/skill/wave edit can be proven to help, wash, or hurt — before it ships.

Adapted from three ideas: SWE-bench Pro / Terminal-Bench task realism (not the near-saturated
SWE-bench Verified), Google ADK's **trajectory evaluation** (grade the tool/agent-call PATH, not
just the answer), and this repo's own `gate-verification.md` graded truth-score.

Used by: `/eval`. Complementary to `gate-verification.md` (which grades a single phase's output);
`/eval` grades the framework's behavior across a fixed suite of tasks.

---

## Ground truth first

Before running any task, the harness reads `docs/PROJECT_FACTS.md` (if present) as ground truth —
retired/renamed components, hard constraints, environment gotchas. A task rubric must never
contradict PROJECT_FACTS; if it does, PROJECT_FACTS wins and the task is flagged stale. This is
the same "facts supersede assumptions" discipline used by `/remember`.

---

## What the suite is

A **fixed, versioned set of small representative tasks**. Each task is a mini requirement/spec,
a graded rubric, and a set of expected artifacts + expected trajectory. Tasks are small enough to
run many quickly, but representative of real pipeline work (a real endpoint, a real UI form, a
real bug fix), so a score movement means something.

Suite lives under `agent_state/eval/suite/<task-id>/`:

```
agent_state/eval/suite/
  T-001-crud-endpoint/
    task.md              # the mini requirement/spec fed to the framework
    rubric.json          # graded outcome checks (weighted)
    expected_artifacts.json   # files/tests that must exist + assertions on them
    expected_trajectory.json  # the agent/wave/spec call path that SHOULD happen
```

The suite is **checked into `agent_state/eval/`** and versioned by git SHA so a baseline can be
tied to the exact suite it ran against.

### Choosing tasks (SWE-bench Pro / Terminal-Bench style)

- **Model on SWE-bench Pro / Terminal-Bench, NOT SWE-bench Verified.** Verified is
  near-saturated and contaminated in modern training data — a task everything already passes
  measures nothing. Prefer tasks with real multi-file, multi-step structure and a non-obvious
  correct path.
- **Small but end-to-end.** One task should exercise a real slice: spec → implement → test →
  review. A task that only touches one file can't catch a wave regression.
- **Deterministic rubric.** Every check must be machine-verifiable (a grep, a test run, a file
  assertion) — never "looks good." Ambiguous rubrics make the eval un-reproducible.
- **Spread across pipeline surfaces.** Cover at least: a backend endpoint, a UI form, a bug
  fix (`/hotfix`/`/diagnose` path), and a multi-phase gate. Each surface catches a different
  class of regression.
- **Keep 8–15 tasks.** Enough to catch regression blindness (below), few enough to run the FULL
  suite every time.

---

## Two scoring modes

### Mode A — OUTCOME (did it produce the right artifacts?)

Grade the produced artifacts/tests against the task's `rubric.json`. Each rubric item is a
weighted, machine-verifiable check. This is the same evidence discipline as `gate-verification.md`
Layer 1 — every check resolves to a file:line / command-output, never a self-report.

```json
{
  "rubric": [
    { "id": "R1", "weight": 0.30, "check": "artifact_exists",
      "path": "internal/handler/user_handler.go", "desc": "handler implemented" },
    { "id": "R2", "weight": 0.25, "check": "command_passes",
      "cmd": "go test ./internal/handler/...", "desc": "handler tests green" },
    { "id": "R3", "weight": 0.20, "check": "grep_present",
      "pattern": "tenantID", "path": "internal/handler/user_handler.go",
      "desc": "tenant scoping present (not IDOR)" },
    { "id": "R4", "weight": 0.15, "check": "grep_absent",
      "pattern": "(TODO|t\\.Skip|@ts-ignore)", "path": "internal/handler/",
      "desc": "no stubs/suppression introduced" },
    { "id": "R5", "weight": 0.10, "check": "tc_ids_annotated",
      "ids": ["TC-U-001","TC-I-001"], "desc": "spec TC-* IDs traced into tests" }
  ]
}
```

```
outcome_score = Σ (rubric_item_passed ? weight : 0)      # ∈ [0,1]
```

### Mode B — TRAJECTORY (did it take the right PATH?)

Borrowed from ADK trajectory eval: an agent can reach the right artifact by the **wrong process**
(skipped the reviewer, never wrote a spec, gate passed with zero acceptance tests). Outcome alone
misses this. Grade the actual agent/wave/spec call sequence against `expected_trajectory.json`.

```json
{
  "expected_trajectory": [
    { "step": "spec_writer",       "must": true,  "produces": "specs/user.md" },
    { "step": "backend_developer", "must": true },
    { "step": "unit_test_agent",   "must": true },
    { "step": "integration_test_agent", "must": true },
    { "step": "code_reviewer_I",   "must": true },
    { "step": "security_reviewer", "must": true },
    { "step": "gate_verification", "must": true, "order_after": "security_reviewer" }
  ],
  "forbidden": [
    { "pattern": "gate.passed written before security_reviewer ran",
      "desc": "gate must not pass ahead of review" }
  ]
}
```

Scoring (two components, ADK-style):
- **in_order match** — longest common subsequence of actual vs expected `must:true` steps.
- **precision/recall** — required steps that ran (recall) and extra/forbidden steps (precision).

```
trajectory_score = 0.6 * (matched_required / total_required)      # recall of required steps
                 + 0.4 * (in_order_required / total_required)      # correct ordering
                 − forbidden_hits * 0.25                           # each forbidden step penalized
trajectory_score = clamp(trajectory_score, 0, 1)
```

A task can score **outcome 1.0 / trajectory 0.4** — right answer, wrong process. That gap is the
signal a raw pass/fail eval throws away.

Trajectory is reconstructed from the run's own artifacts: `agent_state/phases/*/execution_log`,
manifest `produced_by` fields, and the ordering of report files' git timestamps — no new infra.

---

## Metrics tracked per run

| Metric | Meaning | Source |
|--------|---------|--------|
| `outcome_score` | rubric pass fraction, per task and suite-mean | Mode A |
| `trajectory_score` | path-match fraction, per task and suite-mean | Mode B |
| `pass@1` | fraction of tasks where outcome_score = 1.0 on the first attempt | Mode A |
| `regression_rate` | tasks that scored LOWER than the baseline ÷ total tasks | vs baseline |
| `gate_score` | the phase gate_score the task's run produced | `gate-verification.md` |
| `cost_proxy` | wall-clock seconds + agent/subagent count for the run | execution log |

`cost_proxy` is a **proxy, not a bill** — it exists so a change that improves scores by burning 3×
the agents is visible as a trade-off, not a free win.

---

## BEFORE / AFTER protocol (the whole point)

```
1. BASELINE   — run the FULL suite on the current framework, snapshot results.
                → agent_state/eval/baselines/<date>-<git-sha>.json
2. CHANGE     — make ONE framework change (edit a prompt / skill / wave).
3. RE-RUN     — run the FULL suite again on the changed framework.
4. DIFF       — compare against the latest baseline, per task and per metric.
5. VERDICT    — improved / regressed / wash (see thresholds below).
```

Baseline snapshot shape (`agent_state/eval/baselines/<date>-<git-sha>.json`):

```json
{
  "date": "2026-07-06",
  "git_sha": "4d0ae36",
  "suite_sha": "4d0ae36",
  "suite_size": 12,
  "tasks": [
    { "id": "T-001-crud-endpoint",
      "outcome_score": 0.90, "trajectory_score": 1.00,
      "pass_at_1": true, "gate_score": 0.93, "cost_proxy": {"wall_s": 210, "agents": 9} }
  ],
  "suite": { "outcome_mean": 0.88, "trajectory_mean": 0.94,
             "pass_at_1_rate": 0.75, "cost_proxy_total": {"wall_s": 2400, "agents": 96} }
}
```

### ⚠ Regression blindness — the failure mode to fear

A framework change can **help one task and silently hurt another**. If you eyeball only the task
you were tuning for, you will ship a net regression. Defenses, mandatory:

1. **Always run the FULL suite. Never a subset for a verdict.** `--task <id>` exists only for
   debugging a single task and must NOT be used to declare improve/regress/wash.
2. **Report per-task deltas, not just the suite mean.** A +0.10 mean can hide a −0.30 on one task.
3. **`regression_rate > 0` blocks a "clean improvement" verdict** even if the mean rose. Any task
   that went down is called out by name.
4. **Non-determinism guard.** LLM runs vary. Treat a per-task delta within ±0.05 as noise (wash),
   not signal. For a borderline verdict, re-run the affected tasks up to 2× and use the median.

### Verdict thresholds

```
IMPROVED  : suite outcome_mean Δ ≥ +0.05  AND regression_rate == 0
            (mean rose meaningfully AND nothing individually regressed)
REGRESSED : suite outcome_mean Δ ≤ −0.05  OR  regression_rate ≥ 0.20
            (mean dropped, OR ≥1/5 of tasks got worse)
WASH      : otherwise — within noise, or improvements offset by regressions
```

A borderline WASH with a real per-task regression is reported as **"MIXED — investigate"**, never
laundered into IMPROVED. Trajectory regressions are surfaced the same way as outcome regressions —
a change that keeps scores but corrupts the process (skips review) is a REGRESSION.

---

## Run record

Each run writes `agent_state/eval/runs/<date>-<git-sha>-<mode>.json` (same shape as a baseline,
plus a `baseline_compared` field when run with compare). Baselines are just runs promoted to
`agent_state/eval/baselines/`. Everything is file-based JSON + markdown — no vector DB, no service.

---

## Starter task format (copy this to add your own)

`agent_state/eval/suite/T-001-crud-endpoint/task.md`:

```markdown
# T-001 — CRUD endpoint (backend slice)
Surface: backend endpoint | Est. cost: ~9 agents

## Requirement
Implement a tenant-scoped `GET /api/v1/widgets/:id` endpoint returning a single widget owned by
the caller's tenant. 404 if not found OR not owned (no existence oracle). Emit unit + integration
tests. TC IDs: TC-U-001 (owned widget returned), TC-I-001 (cross-tenant → 404).

## Definition of done
- Handler + service + repository, tenantID threaded end-to-end.
- Cross-tenant read returns 404, not 403 and not the row.
- Tests annotate TC-U-001 / TC-I-001 and pass.
- No TODO/stub/suppression introduced.
```

Its `rubric.json` and `expected_trajectory.json` follow the shapes shown in Modes A and B above,
and `expected_artifacts.json` lists the files with per-file assertions:

```json
{
  "artifacts": [
    { "path": "internal/handler/widget_handler.go",
      "assert": ["grep:tenantID", "grep_absent:TODO"] },
    { "path": "internal/handler/widget_handler_test.go",
      "assert": ["grep:TC-U-001", "cmd_passes:go test ./internal/handler/..."] }
  ]
}
```

---

## Rules

- Grade artifacts by re-verifying them yourself (grep / re-run), never by trusting a report — same
  distrust discipline as `gate-verification.md`.
- One framework change per before/after cycle. Two changes at once make the diff uninterpretable.
- The suite is versioned with the repo; record `suite_sha` in every baseline so old baselines
  aren't compared against a different suite.
- Add tasks over time as new regression classes are found — a task that once caught a real bug
  earns its place permanently. Never delete a task to make a verdict look better.
- `/eval` measures the framework, not a user's project — run it in this repo against the fixed
  suite, not against downstream project code.
