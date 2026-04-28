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

With `--verbose`: include full manifest JSON for each completed phase.
