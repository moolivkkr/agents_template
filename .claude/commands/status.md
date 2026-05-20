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

Reads all phase gates, manifests, and test results. Prints status report and recommends next action.

---

## Step 0 — Read State

```bash
COMPLETED=$(ls agent_state/phases/*/gate.passed 2>/dev/null | grep -oP 'phases/\K\d+' | sort -n)
PLANNED=$(ls docs/design/phases/*/INDEX.md 2>/dev/null | grep -oP 'phases/\K\d+' | sort -n)
cat agent_state/agent_registry.json 2>/dev/null
```

Read each completed phase manifest for: requirements met, test results, known issues.

---

## Report Format

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  <PROJECT_NAME> — Status (<date>)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Tech Stack: <summary> | Agents: N core + N generated

PHASE PROGRESS
  ✅ Phase 1 — <goal> (completed <date>)
     FR-*: N/N | Unit: X/X | Integration: X/X | E2E: X/X | Issues: N
  📋 Phase 3 — <goal> (planned, not started)
  ⬜ Phase 4+ (not yet planned)

CURRENT PHASE: N — <status> | <last step completed>

OPEN ISSUES: <carried_forward[] across manifests>

BRD COVERAGE: N/N FR-* implemented (N%)

NEXT ACTION: ▶ <recommended command>
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

### Execution History
Per completed phase with `execution.jsonl`: total duration, agent count, failures, retries, slow agents (>5m).

### Token Usage Summary
Per phase: estimated vs actual duration + agent count. Next phase forward estimate using `/develop` Step 0 algorithm. If no estimates recorded, show durations only.

### Spec Freshness
Per gated phase: compare spec timestamps vs implementation file timestamps.
- Implementation modified after spec + >7 days since spec → flag stale
- Commits to implementation not reflected in spec → flag

```
SPEC FRESHNESS
  Phase 1: ✅ current
  Phase 2: ⚠ 3 specs may be stale
```

With `--verbose`: include full manifest JSON per completed phase.
