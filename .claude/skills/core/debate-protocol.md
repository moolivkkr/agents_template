# Debate Protocol — Research, Debate, Collaborate, Decide

## When to Escalate

**MUST escalate:** Conflicting options with meaningful tradeoffs, missing data, ambiguous requirements, high-impact choices (architecture/security/data model), auto-research Level 4-5 low confidence.

**Do NOT escalate:** Answer in docs (Level 1-2), trivially reversible, reasonable default with no tradeoffs.

## Escalation Format

Write to `agent_state/debates/<step>-<topic>.json`:

```json
{
  "type": "debate_request",
  "from_agent": "<agent>", "from_step": "<step>",
  "decision": "<one sentence>",
  "options": [{ "id": "A", "label": "<name>", "initial_reasoning": "<why>" }],
  "context": "<BRD refs, constraints>",
  "impact": "HIGH | MEDIUM",
  "blocking": true
}
```

## 3-Phase Process

### Phase 1: Research (PARALLEL — one per option)

Each researcher gathers evidence FOR their option: search docs, web, competitors, skill packs. Output: evidence with citations, known weaknesses, quantitative data.

### Phase 2: Debate (PARALLEL — one per option, reads ALL research)

Each debater argues FOR their position: strengths, why others are worse for THIS project, acknowledged weaknesses + mitigations.

**Scoring criteria:** BRD alignment (30%), Technical feasibility (25%), Team/constraint fit (20%), Scalability (15%), Ecosystem (10%)

### Phase 3: Arbitration (single agent)

Reads all debates, produces independent scoring, declares verdict with confidence, rejection reasons, reconsider conditions, risk mitigation.

## Decision Classification

| Impact | Process | Time |
|--------|---------|------|
| HIGH (arch, security, data) | Full 3-phase | 3-5 min |
| MEDIUM (library, pattern) | Research + arbitrator only | 1-2 min |
| LOW | Agent decides with auto-research | 0 min |

## Pipeline Integration

1. Agent detects uncertainty → 2. Writes debate_request → 3. debate_moderator picks up → 4. Team runs → 5. Verdict written → 6. Agent continues

Human checkpoint presents all debated decisions with scores. User can override (logged as USER_OVERRIDE).

## Anti-Patterns

- Don't escalate trivial decisions; debaters MUST argue FOR their assigned option
- Don't skip weakness acknowledgment; arbitrator must reference specific points
- Every user override documented with rationale
