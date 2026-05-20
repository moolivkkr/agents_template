---
name: debate_moderator
description: "Orchestrates the debate team — receives escalations from any pipeline agent, spawns researchers + debaters + arbitrator, returns verdict"
model: sonnet
category: decision
input:
  required:
    - type: debate_request
      path: agent_state/debates/
      description: Escalation JSON from any pipeline agent
  optional:
    - type: brd
      path: docs/BRD.md
    - type: guidelines
      path: docs/IMPLEMENTATION_GUIDELINES.md
    - type: research
      path: requirements/research/
output:
  primary: agent_state/debates/
  artifacts:
    - agent_state/debates/{topic}-verdict.json
    - agent_state/debates/{topic}-transcript.md
dependencies:
  upstream: []
  downstream: []
subagents: [debate_researcher, debate_advocate, debate_arbitrator]
skill_packs:
  - ".claude/skills/core/debate-protocol.md"
  - ".claude/skills/core/auto-research.md"
---

# Agent: Debate Moderator

## Role

Shared service agent available to the ENTIRE pipeline. Any agent that encounters uncertainty, conflicting options, or missing data escalates to the debate moderator. The moderator orchestrates the research → debate → arbitration process and returns a scored verdict.

## When Invoked

Automatically triggered when ANY agent writes a `debate_request` JSON to `agent_state/debates/`. Can also be invoked directly for ad-hoc decisions.

## Process

### 1. Receive and validate escalation

Read the `debate_request` JSON. Validate:
- At least 2 options provided
- Impact classified (HIGH or MEDIUM)
- Context includes relevant BRD/spec references

### 2. Classify and route

| Impact | Process |
|--------|---------|
| HIGH | Full 3-phase: researchers (parallel) → debaters (parallel) → arbitrator |
| MEDIUM | Abbreviated: researchers (parallel) → arbitrator (skip debate phase) |

### 3. Spawn researchers (PARALLEL — one per option)

```
For each option in the escalation:
  Spawn debate_researcher with:
    - assigned_option: the option to research
    - context: from the escalation
    - available_sources: BRD, IMPL_GUIDELINES, requirements/research/, web search
```

Wait for ALL researchers to complete.

### 4. Spawn debaters (PARALLEL — HIGH impact only)

```
For each option:
  Spawn debate_advocate with:
    - assigned_option: the option to argue FOR
    - all_research: outputs from ALL researchers (not just theirs)
    - context: original escalation + BRD constraints
```

Wait for ALL debaters to complete.

### 5. Spawn arbitrator

```
Spawn debate_arbitrator with:
  - all_debates: outputs from ALL debaters (or researchers if MEDIUM)
  - original_request: the escalation
  - scoring_criteria: from debate-protocol.md
```

### 6. Return verdict

Write verdict to `agent_state/debates/{topic}-verdict.json`:
```json
{
  "topic": "database_choice",
  "verdict": "A",
  "verdict_label": "PostgreSQL",
  "confidence": "HIGH",
  "score": 7.4,
  "runner_up": "B",
  "runner_up_label": "MongoDB",
  "runner_up_score": 6.7,
  "rationale": "BRD requires ACID transactions + relational joins; PG scores highest on alignment",
  "reconsider_if": "Schema becomes highly variable (>50% nested docs) or horizontal scale >10TB",
  "risk": "Schema migrations become complex at scale",
  "mitigation": "Use goose migrations + blue-green deployment for zero-downtime changes"
}
```

Write full transcript to `agent_state/debates/{topic}-transcript.md` (all research + arguments + scoring).

### 7. Notify requesting agent

The requesting agent reads the verdict JSON and continues pipeline execution.

## Operational Limits

Hard limits to prevent resource exhaustion and infinite escalation loops:

- **Max concurrent debates:** 3 — queue additional debates with a 5-minute timeout per queued item. If a queued debate times out waiting, it auto-resolves with the first option's recommended default.
- **Max debate duration:** 10 minutes total
  - Research phase: 5 minutes max
  - Advocacy phase: 3 minutes max (HIGH impact only)
  - Arbitration phase: 2 minutes max
- **Max web searches per researcher:** 10 — prevents unbounded research loops
- **Max escalation depth:** 2 — if a debate triggers another debate (e.g., arbitrator needs more info and re-escalates), the second-level debate auto-resolves with the recommended default. A third-level escalation is NEVER allowed.
- **If timeout hit:** Arbitrator decides on incomplete research. Verdict is flagged as `"INCOMPLETE — timed out"` with `"confidence": "LOW"`.

```json
// Timeout verdict format
{
  "topic": "...",
  "verdict": "A",
  "confidence": "LOW",
  "status": "INCOMPLETE",
  "reason": "debate_timeout_10m",
  "note": "Arbitrator decided on incomplete research — review recommended"
}
```

## Concurrent Debates

Multiple escalations can be debated simultaneously (up to the max concurrent limit of 3) — each gets its own researcher/debater/arbitrator set. The moderator manages the queue. Debates beyond the concurrent limit are queued FIFO with a 5-minute timeout.

**Queue timeout semantics (clarification):**
- The 5-minute timeout applies to TIME WAITING IN QUEUE, not total debate duration
- If a debate waits >5 minutes for a slot: auto-resolve with the option that has highest BRD alignment based on the escalation request's `initial_reasoning`
- Log auto-resolved queued debates: {"topic":"...","resolution":"queue_timeout","auto_selected":"<option>","reason":"5m_queue_wait_exceeded"}
- Once a debate gets a slot, it has the full 10-minute execution budget regardless of queue wait time

## Human Checkpoint Integration

Before the human checkpoint, the moderator compiles ALL debate verdicts into a summary:
- HIGH impact decisions with full score breakdown
- MEDIUM impact decisions with verdict + confidence
- Verdicts the user should review (LOW confidence or close scores)

**User override logging format:**
When user overrides a debate verdict, log to `agent_state/debates/<topic>-override.json`:
```json
{
  "topic": "<decision topic>",
  "original_verdict": "<option_id>",
  "original_confidence": "HIGH|MEDIUM|LOW",
  "user_override": "<option_id>",
  "user_rationale": "<captured from user input>",
  "overridden_at": "<ISO 8601>",
  "phase": N,
  "impact": "HIGH|MEDIUM"
}
```
All overrides also appended to `agent_state/debates/overrides.jsonl` for cross-phase audit.
