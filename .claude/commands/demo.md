---
command: demo
description: "Prepare and dry-run a stakeholder demo of a completed phase: write the demo script, stand up the environment with seeded data, then walk every step and verify it works before anyone watches."
arguments:
  - name: phase
    required: false
    description: "Phase to demo (e.g. --phase=3). Default: the latest phase with gate.passed."
  - name: validate-only
    required: false
    default: false
    description: "Skip writing a new script; re-run setup + validation of the existing docs/demos/phase-N/demo-script.md"
---

# /demo — Stakeholder Demo Preparation

> **Spawning agents:** follow `~/.claude/skills/core/child-returns.md`. Wait for every agent you spawn before using its result, and act on its first line: `NEEDS_INPUT` (ask the user, or record a default under `--auto`), `NEEDS_DECISION <topic>` (run `debate_moderator`, then relaunch the agent with the decision), or a progress note (re-spawn it, at most twice).

Wires the three demo agents into one run. Each agent consumes the previous one's output, so they
run in sequence. A demo that fails in rehearsal is reported here, not discovered in front of
stakeholders.

## Step 0 — Orient

```bash
PHASE="${ARG_PHASE:-$(ls agent_state/phases/*/gate.passed 2>/dev/null | grep -oE 'phases/[0-9]+' | grep -oE '[0-9]+' | sort -n | tail -1)}"
[ -n "$PHASE" ] || { echo "⛔ No phase has passed its gate — nothing to demo yet."; exit 1; }
test -f "agent_state/phases/${PHASE}/gate.passed" || echo "⚠ Phase ${PHASE} has not passed its gate — the demo may show unfinished work."
```

Prepend the GROUND TRUTH line from `develop-orchestrator.md` to every agent prompt below.

## Step 1 — Write the demo script  (`subagent_type: demo_documenter`)

Skip if `--validate-only`.

```
Agent prompt (subagent_type: demo_documenter): "[GROUND TRUTH] You are demo_documenter for Phase ${PHASE}. From docs/BRD.md and
agent_state/phases/${PHASE}/manifest.json, write docs/demos/phase-${PHASE}/demo-script.md and
test-data.md: the persona-driven story, each step's action and expected on-screen/API result, and
the seed data it needs. For a React Native app, name the platform (iOS simulator / Android emulator)
for each step."
```

## Step 2 — Stand up the environment  (`subagent_type: demo_executor`)

```
Agent prompt (subagent_type: demo_executor): "[GROUND TRUTH] You are demo_executor for Phase ${PHASE}. Following
docs/demos/phase-${PHASE}/demo-script.md and IMPLEMENTATION_GUIDELINES, start the services, seed the
test data, and confirm the environment is ready. Write agent_state/demos/phase-${PHASE}/."
```

## Step 3 — Rehearse every step  (`subagent_type: demo_validator`)

```
Agent prompt (subagent_type: demo_validator): "[GROUND TRUTH] You are demo_validator for Phase ${PHASE}. Walk every step of
docs/demos/phase-${PHASE}/demo-script.md against the running environment and verify each produces
its expected result. Write agent_state/demos/phase-${PHASE}/validation_report.md with PASS/FAIL per step."
```

## Step 4 — Report

```bash
R="agent_state/demos/phase-${PHASE}/validation_report.md"
test -f "$R" || echo "⛔ demo_validator produced no report"
grep -qiE '\bFAIL\b' "$R" 2>/dev/null && echo "⛔ Demo has failing steps — fix or cut them before presenting (see $R)"
```

Tell the user: the script path, the environment status, and PASS/FAIL per step. Failing steps are
listed first. Leave the environment running for the demo; say how to stop it.
