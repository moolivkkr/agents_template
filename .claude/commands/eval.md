---
command: eval
description: "Run the internal eval suite to measure the framework's own output quality. Scores each task on OUTCOME (right artifacts) and TRAJECTORY (right agent/wave path), then compares against a baseline to say whether the last framework change improved, regressed, or washed."
arguments:
  - name: baseline
    required: false
    default: false
    description: "Run the full suite and snapshot the results as a new baseline (agent_state/eval/baselines/<date>-<sha>.json). Does not compare."
  - name: compare
    required: false
    default: false
    description: "Run the full suite and diff against the latest baseline. Emits an improve/regress/wash verdict. This is the before/after workhorse."
  - name: task
    required: false
    description: "Run a SINGLE task by id (e.g. T-001-crud-endpoint) for debugging. NEVER used to declare a verdict — a subset can't detect regression blindness."
---

# /eval — Framework Self-Evaluation

Runs a fixed suite of small, representative tasks through the framework and measures the quality
of what the framework produces — so a prompt/skill/wave change can be proven to help, wash, or
hurt instead of being changed blind.

**Read `.claude/skills/core/eval-harness.md` first** — it defines the suite format, the two
scoring modes (OUTCOME + TRAJECTORY), the metrics, and the before/after protocol this command
executes.

**Use when:** before/after editing an agent prompt, a skill, or a wave; to catch a silent
regression a change introduced elsewhere; to snapshot a known-good baseline before a risky edit.

---

## Step 0 — Ground truth + suite load

1. Read `docs/PROJECT_FACTS.md` (if present) as ground truth. Any rubric that contradicts
   PROJECT_FACTS is stale — PROJECT_FACTS wins; flag the task, don't score against a false rubric.
2. Load the suite from `agent_state/eval/suite/`. If it's empty, the harness has never been
   seeded — print the starter-task guidance and stop:

```bash
mkdir -p agent_state/eval/suite agent_state/eval/baselines agent_state/eval/runs
SUITE_TASKS=$(ls -d agent_state/eval/suite/*/ 2>/dev/null)
if [ -z "$SUITE_TASKS" ]; then
  echo "No eval tasks found. Seed agent_state/eval/suite/<task-id>/ using the starter"
  echo "format in .claude/skills/core/eval-harness.md (task.md + rubric.json +"
  echo "expected_artifacts.json + expected_trajectory.json), then re-run /eval."
  exit 0
fi
GIT_SHA=$(git rev-parse --short HEAD)
DATE=$(date +%Y-%m-%d)
```

3. Resolve scope:
   - `--task <id>` → run ONLY that task (debug mode, no verdict).
   - `--baseline` or `--compare` or no flag → run the **FULL** suite. Never a subset for a verdict
     (regression blindness — see the skill). If `--task` is combined with `--baseline`/`--compare`,
     refuse and explain that a verdict requires the full suite.

---

## Step 1 — Run each task

For every task in scope, drive the framework through the task exactly as a real pipeline would
(spec → implement → test → review → gate, per the task's surface), capturing artifacts AND the
agent/wave call sequence. Run tasks in an isolated scratch workspace so the repo isn't mutated;
record the produced artifacts and the execution log for scoring.

Reconstruct the **trajectory** from the run's own evidence — `agent_state/phases/*/execution_log`,
manifest `produced_by` fields, and report-file ordering — not from any agent's self-narration.

---

## Step 2 — Score (OUTCOME + TRAJECTORY)

Per task, apply both modes from the skill. Every check is re-verified here (grep / re-run /
file assertion) — never trust a report's claim.

- **OUTCOME:** evaluate `rubric.json` → `outcome_score ∈ [0,1]`; `pass@1 = (outcome_score == 1.0)`.
- **TRAJECTORY:** compare the reconstructed path against `expected_trajectory.json` (required-step
  recall + in-order + forbidden-step penalty) → `trajectory_score ∈ [0,1]`.
- Also record `gate_score` (from the run's gate-verification output) and `cost_proxy`
  (wall-clock seconds + agent count).

```json
{
  "id": "T-001-crud-endpoint",
  "outcome_score": 0.90, "trajectory_score": 1.00,
  "pass_at_1": true, "gate_score": 0.93,
  "cost_proxy": { "wall_s": 210, "agents": 9 },
  "failed_rubric_items": ["R4"],
  "trajectory_notes": "all required steps in order; no forbidden steps"
}
```

---

## Step 3 — Persist the run

```bash
MODE="run"; [ "$ARG_BASELINE" = "true" ] && MODE="baseline"; [ "$ARG_COMPARE" = "true" ] && MODE="compare"
RUN_FILE="agent_state/eval/runs/${DATE}-${GIT_SHA}-${MODE}.json"
# write the run record (per-task rows + suite aggregates) to $RUN_FILE
```

Suite aggregates: `outcome_mean`, `trajectory_mean`, `pass_at_1_rate`, `cost_proxy_total`, plus
`suite_size` and `suite_sha` (`git rev-parse --short HEAD` of the suite).

---

## Step 4a — `--baseline`: snapshot

Promote this run to a baseline. Does not compare.

```bash
cp "$RUN_FILE" "agent_state/eval/baselines/${DATE}-${GIT_SHA}.json"
```

```
✅ Baseline snapshot saved: agent_state/eval/baselines/<date>-<sha>.json
   Suite: N tasks (suite_sha <sha>)
   outcome_mean <x> | trajectory_mean <x> | pass@1 <x> | cost <wall_s>s / <agents> agents
```

If a baseline already exists for today's SHA, note the overwrite (old timestamp → new).

---

## Step 4b — `--compare`: diff + verdict

Load the **latest** baseline by date:

```bash
BASELINE=$(ls -t agent_state/eval/baselines/*.json 2>/dev/null | head -1)
if [ -z "$BASELINE" ]; then
  echo "⚠ No baseline exists. Run '/eval --baseline' first, then --compare on the next run."
  exit 0
fi
BASE_SUITE_SHA=$(jq -r '.suite_sha' "$BASELINE")
# If BASE_SUITE_SHA != current suite_sha, WARN: the suite itself changed — diff is not apples-to-apples.
```

Diff **every task** and the suite means. Compute `regression_rate` = tasks whose `outcome_score`
dropped more than the 0.05 noise band ÷ total tasks. Apply the verdict thresholds from the skill.

---

## Step 5 — Results table + verdict

```
Eval Results — <date> <sha>  vs baseline <baseline-date> <baseline-sha>
Suite: 12 tasks (suite_sha match)     [⚠ SUITE CHANGED — diff not apples-to-apples, if mismatch]

| Task                     | Outcome | Δ      | Trajectory | Δ      | pass@1 | Verdict     |
|--------------------------|---------|--------|------------|--------|--------|-------------|
| T-001-crud-endpoint      | 0.90    | +0.00  | 1.00       | +0.00  | ✅     | wash        |
| T-002-ui-form            | 0.95    | +0.15  | 0.90       | +0.05  | ✅     | improved    |
| T-003-hotfix-idor        | 0.60    | −0.30  | 0.70       | −0.20  | ❌     | ⚠ REGRESSED |
| T-004-multiphase-gate    | 1.00    | +0.00  | 0.55       | −0.45  | ✅     | ⚠ TRAJECTORY REGRESSED |
| ...                      |         |        |            |        |        |             |
|--------------------------|---------|--------|------------|--------|--------|-------------|
| SUITE MEAN               | 0.86    | +0.06  | 0.88       | −0.09  | 75%    |             |

Cost proxy: 2400s / 96 agents  (baseline 2100s / 84 agents  → +14% wall, +14% agents)

Regressions (called out by name — never hidden by a positive mean):
  ⚠ T-003-hotfix-idor  outcome −0.30  (failed R3: tenant scoping dropped — reintroduced IDOR)
  ⚠ T-004-multiphase-gate  trajectory −0.45 (gate.passed written before security_reviewer ran)

VERDICT: ⚠ MIXED — investigate
  Suite outcome mean rose (+0.06) BUT regression_rate = 0.17 and a forbidden-trajectory step
  appeared. This is NOT a clean improvement. Fix or revert the change before shipping.
```

Verdict is one of: **IMPROVED**, **REGRESSED**, **WASH**, or **MIXED — investigate** (any real
per-task regression, even under a positive mean). Trajectory regressions count as regressions —
a change that keeps outcomes but corrupts the process is not a win.

Write the compare report to `agent_state/eval/runs/${DATE}-${GIT_SHA}-compare.md` alongside the
JSON run record.

---

## Step 6 — `--task <id>`: single-task debug

Runs one task, prints its outcome + trajectory breakdown (which rubric items failed, where the
path diverged from expected), and stops. **No baseline write, no verdict** — a subset cannot
detect regression blindness, so it is never allowed to declare improve/regress/wash.

```
Task T-003-hotfix-idor  (debug)
  Outcome:    0.60   failed: R3 (tenantID absent in service call → IDOR)
  Trajectory: 0.70   diverged: security_reviewer step missing from path
  Artifacts:  agent_state/eval/runs/<date>-<sha>-task-T-003.json
```

---

## Rules

- A verdict ALWAYS runs the FULL suite. `--task` is debug-only. (Regression blindness: a change
  can help one task and silently break another — see `eval-harness.md`.)
- Re-verify every rubric item yourself (grep / re-run / file assertion). Never score off a
  subagent's self-report.
- One framework change per before/after cycle — otherwise the diff is uninterpretable.
- Treat per-task deltas within ±0.05 as noise; for a borderline verdict, re-run affected tasks up
  to 2× and use the median (LLM runs are non-deterministic).
- Never delete a task to make a verdict look better. A task that once caught a real regression
  stays in the suite permanently.
- Record `suite_sha` on every run; refuse to silently compare across a changed suite — warn that
  the diff is not apples-to-apples.
