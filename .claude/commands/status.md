---
command: status
description: Show project status — phase gates, test results, open issues, and next recommended action.
arguments:
  - name: verbose
    required: false
    default: false
    description: "Show full manifest details for each completed phase"
---

# /status — Project Status

Reads all phase gate files, manifests, and test results. Prints a comprehensive status report and recommends the next action.

---

## Step 0 — Read State

```bash
# Completed phases
COMPLETED=$(ls agent_state/phases/*/gate.passed 2>/dev/null | grep -oP 'phases/\K\d+' | sort -n)

# Planned but not developed phases
PLANNED=$(ls docs/design/phases/*/INDEX.md 2>/dev/null | grep -oP 'phases/\K\d+' | sort -n)

# Agent registry
cat agent_state/agent_registry.json 2>/dev/null
```

Read each completed phase manifest for: requirements met, test results, known issues.

---

## Report Format

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  <PROJECT_NAME> — Status
  <current date>
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Tech Stack: <from IMPLEMENTATION_GUIDELINES — one line summary>
Agents:     <N core + N generated>

PHASE PROGRESS
━━━━━━━━━━━━━━
  ✅ Phase 1 — <goal>   (completed <date>)
     FR-*: N/N met | Unit: X/X | Integration: X/X | E2E: X/X
     Known issues: none (or: N issues)

  ✅ Phase 2 — <goal>   (completed <date>)
     ...

  📋 Phase 3 — <goal>   (planned, not started)
  ⬜ Phase 4+           (not yet planned)

CURRENT PHASE: <N>
━━━━━━━━━━━━━━━━━━
  Status: <In progress / Planned / Not started>
  <If in progress: last step completed>

OPEN ISSUES
━━━━━━━━━━━
  <issues from carried_forward[] across all manifests>
  (none if clean)

BRD COVERAGE
━━━━━━━━━━━━
  Total FR-*: N
  Implemented: N (N%)
  Remaining:  N

NEXT ACTION
━━━━━━━━━━━
  ▶ <recommended next command>
  e.g. /plan --phase=3   (Phase 2 complete, Phase 3 not yet planned)
  e.g. /develop --phase=2 (Phase 2 planned, not yet developed)
  e.g. /test --e2e       (All phases done, e2e not run)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

### Git Activity Summary

Between the current phase (or latest gate) and HEAD, gather git activity metrics:

```bash
# Determine baseline: latest gate tag or first commit
BASELINE=$(git tag -l "phase-*-gate" --sort=-version:refname | head -1)
if [ -z "$BASELINE" ]; then
  BASELINE=$(git rev-list --max-parents=0 HEAD)
  IS_ROOT_BASELINE=true
fi

# Commit counts by type (conventional commit prefix)
TOTAL_COMMITS=$(git log ${BASELINE}..HEAD --oneline | wc -l)
FEAT_COMMITS=$(git log ${BASELINE}..HEAD --oneline --grep="^feat" | wc -l)
FIX_COMMITS=$(git log ${BASELINE}..HEAD --oneline --grep="^fix" | wc -l)
TEST_COMMITS=$(git log ${BASELINE}..HEAD --oneline --grep="^test" | wc -l)
CHORE_COMMITS=$(git log ${BASELINE}..HEAD --oneline --grep="^chore" | wc -l)
OTHER_COMMITS=$((TOTAL_COMMITS - FEAT_COMMITS - FIX_COMMITS - TEST_COMMITS - CHORE_COMMITS))

# Files and lines changed (use space not .. for root commit baseline)
if [ "$IS_ROOT_BASELINE" = "true" ]; then
  DIFF_STAT=$(git diff --shortstat ${BASELINE} HEAD)
else
  DIFF_STAT=$(git diff --shortstat ${BASELINE}..HEAD)
fi

# Days since baseline
BASELINE_DATE=$(git log -1 --format=%ci ${BASELINE})
DAYS_ELAPSED=$(( ($(date +%s) - $(date -d "$BASELINE_DATE" +%s 2>/dev/null || date -jf "%Y-%m-%d %H:%M:%S %z" "$BASELINE_DATE" +%s)) / 86400 ))

# Open PRs (if gh is available)
OPEN_PRS=$(gh pr list --state open --json number,title 2>/dev/null || echo "")
```

Display:
```
GIT ACTIVITY (since last gate)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Commits: N (feat: X, fix: Y, test: Z, chore: W, other: V)
  Changes: N files changed (+X / -Y lines)
  Timeline: N days since last gate
  Open PRs: N (or "none" or "gh CLI not available")
```

If no gate tags exist (fresh project):
```
GIT ACTIVITY (all time)
━━━━━━━━━━━━━━━━━━━━━━
  Commits: N total
  Changes: (use git log --stat for full project stats)
```

### Execution History

For each completed phase, if `agent_state/phases/N/execution.jsonl` exists:
- Show total pipeline duration
- Show agent count and failure count
- Flag any agents that took >5 minutes (potential optimization targets)
- Show retry count if any agents were retried

```
EXECUTION HISTORY
━━━━━━━━━━━━━━━━
  Phase 1 — total: Xm Ys | agents: N run, N failed, N retried
    ⚠ Slow agents (>5m): <agent_name> (Xm Ys)
  Phase 2 — total: Xm Ys | agents: N run, N failed, N retried
  ...
```

### Token Usage Summary

For each phase, read `agent_state/phases/N/execution.jsonl` and correlate estimation vs. actual execution data. These are **rough estimates** — useful for budgeting and trend analysis, not precision accounting.

For each completed phase with execution.jsonl:
1. Read `estimate` entry (if exists): predicted tokens and component count
2. Read `pipeline_complete` entry: actual duration and agent count
3. For the next uncompleted phase: compute a forward-looking estimate using the algorithm from `/develop` Step 0 (Token/Cost Estimation)

Display:
```
TOKEN USAGE
━━━━━━━━━━━
  Phase 1: estimated ~400K | actual duration 12m 34s | 18 agents
  Phase 2: estimated ~850K | actual duration 28m 12s | 24 agents
  Phase 3: (not yet run)

  Next phase estimate: ~${ESTIMATE} tokens (${COMPONENTS} components, ${HAS_UI ? "full-stack" : "backend"})

  Note: Token estimates are rough order-of-magnitude for budgeting.
  Actual usage depends on codebase size, retry cycles, and escalation count.
```

If no `estimate` entries exist in any execution.jsonl (phases run before this feature was added), display:
```
TOKEN USAGE
━━━━━━━━━━━
  Phase 1: no estimate recorded | actual duration 12m 34s | 18 agents
  Phase 2: no estimate recorded | actual duration 28m 12s | 24 agents

  Next phase estimate: ~${ESTIMATE} tokens (${COMPONENTS} components, ${HAS_UI ? "full-stack" : "backend"})

  Tip: Re-run completed phases with latest /develop to capture estimates.
```

### Spec Freshness
For each phase with gate.passed:
1. Find spec files in `docs/design/phases/N/specs/`
2. Find implementation files referenced in phase manifest `artifacts.code`
3. Compare timestamps:
   - If any implementation file was modified AFTER the spec file AND more than 7 days have passed since spec was written:
     - Flag: "⚠ Phase N: spec <spec_name> may be stale — code modified <date> but spec last updated <date>"
4. Check git history:
   - If implementation files have commits NOT reflected in spec (features added, APIs changed):
     - Flag: "⚠ Phase N: <N> commits to implementation since spec was written — consider spec refresh"

Display in status report:
```
SPEC FRESHNESS
━━━━━━━━━━━━━━
  Phase 1: ✅ Specs current (last code change within spec window)
  Phase 2: ⚠ 3 specs may be stale (code modified 2026-05-15, specs from 2026-04-28)
  Phase 3: ✅ Specs current
```

With `--verbose`: include full manifest JSON for each completed phase.
