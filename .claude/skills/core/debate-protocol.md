# Debate Protocol — Research, Debate, Collaborate, Decide

## Purpose

Any agent in the SDLC pipeline that encounters uncertainty, incomplete data, or multiple valid options escalates to the Debate Team. The team researches, argues positions, and produces a scored decision — so the pipeline continues with a well-reasoned answer instead of a guess.

## When to Escalate

An agent MUST escalate when:

1. **Conflicting options** — two or more valid approaches with meaningful tradeoffs
2. **Missing data** — a decision requires information not in requirements, BRD, or specs
3. **Ambiguous requirement** — the BRD or spec can be interpreted multiple ways
4. **High-impact choice** — the decision affects architecture, security, or data model (hard to change later)
5. **Low confidence** — the auto-research protocol (Level 4-5) couldn't find a confident answer

An agent should NOT escalate when:
- The answer is clearly in the docs (Level 1-2 of auto-research)
- The decision is trivially reversible (variable naming, file organization)
- A reasonable default exists with no meaningful tradeoffs

## Escalation Format

Any agent raises a flag by writing:

```json
{
  "type": "debate_request",
  "from_agent": "<agent name>",
  "from_step": "<pipeline step>",
  "decision": "<what needs deciding — one sentence>",
  "options": [
    { "id": "A", "label": "<option name>", "initial_reasoning": "<why this might be right>" },
    { "id": "B", "label": "<option name>", "initial_reasoning": "<why this might be right>" },
    { "id": "C", "label": "<option name>", "initial_reasoning": "<optional third option>" }
  ],
  "context": "<what the agent knows so far — relevant BRD refs, spec refs, constraints>",
  "impact": "HIGH | MEDIUM",
  "blocking": true,
  "deadline": "<when the pipeline needs this answer>"
}
```

Write to: `agent_state/debates/<step>-<topic>.json`

## The Debate Process (3 Phases)

### Phase 1: Research (PARALLEL — one researcher per option)

Each researcher agent gathers evidence FOR their assigned option:

```
Researcher A (assigned Option A):
  1. Search requirements/ and docs/ for supporting evidence
  2. Search web for best practices, case studies, benchmarks
  3. Search competitor analysis (if /research was run)
  4. Check skill packs for relevant patterns
  5. Check if this decision was made differently in similar projects

Output:
  - Evidence FOR this option (with citations)
  - Known weaknesses (honest — not adversarial yet)
  - Quantitative data if available (benchmarks, costs, adoption rates)
```

All researchers run in parallel — one per option.

### Phase 2: Debate (PARALLEL — one debater per option, reading ALL research)

Each debater reads ALL researchers' outputs, then argues FOR their assigned position:

```
Debater A (advocates Option A, has read all research):

## Argument for: [Option A]

### Strengths (from research)
1. [Evidence point — cited source]
2. [Evidence point — cited source]
3. [Evidence point — cited source]

### Why Option B is worse for THIS project
- [Specific counterargument based on BRD/constraints]
- [Evidence that B's strength doesn't apply here]

### Why Option C is worse for THIS project
- [Specific counterargument]

### Weaknesses I acknowledge
- [Honest weakness 1 — and why it's manageable]
- [Honest weakness 2 — and mitigation strategy]

### Score (self-assessed, will be validated by arbitrator)
| Criterion | Weight | Score (1-10) | Reasoning |
|-----------|--------|-------------|-----------|
| BRD alignment | 30% | 8 | [why] |
| Technical feasibility | 25% | 7 | [why] |
| Team/constraint fit | 20% | 9 | [why] |
| Long-term scalability | 15% | 6 | [why] |
| Ecosystem/community | 10% | 8 | [why] |
| **Weighted total** | | **7.6** | |
```

### Phase 3: Arbitration (single agent — reads all debates)

The arbitrator reads ALL debate arguments and produces the final verdict:

```
## Decision: [Topic]

### Verdict: Option [X] — [Name]
Confidence: [HIGH | MEDIUM | LOW]

### Scoring (arbitrator's independent assessment)
| Criterion | Weight | Option A | Option B | Option C |
|-----------|--------|----------|----------|----------|
| BRD alignment | 30% | 7 | 8 | 6 |
| Technical feasibility | 25% | 8 | 6 | 7 |
| Team/constraint fit | 20% | 9 | 5 | 7 |
| Long-term scalability | 15% | 6 | 8 | 7 |
| Ecosystem/community | 10% | 8 | 7 | 6 |
| **Weighted total** | | **7.4** | **6.7** | **6.6** |

### Why [X] wins
[2-3 sentences — the decisive factors]

### Why [Y] was rejected
[1-2 sentences — what specific factor lost it]

### Conditions to reconsider
- Reconsider [Y] if: [specific condition that would change the decision]
- Reconsider [Z] if: [specific condition]

### Risk mitigation
- Primary risk of chosen option: [what could go wrong]
- Mitigation: [how to protect against it]
```

## Decision Classification

| Impact | Options | Process | Time Budget |
|--------|---------|---------|-------------|
| **HIGH** (architecture, security, data model) | 2-4 options | Full 3-phase debate | 3-5 min |
| **MEDIUM** (library choice, pattern selection) | 2-3 options | Research + arbitrator (skip debate) | 1-2 min |
| **LOW** (should not escalate) | N/A | Agent decides with auto-research | 0 min |

## Integration with Pipeline

### How agents escalate
```
1. Agent detects uncertainty
2. Agent writes debate_request JSON to agent_state/debates/
3. debate_moderator picks it up
4. Debate team runs (research → debate → arbitrate)
5. Verdict written to agent_state/debates/<topic>-verdict.json
6. Original agent reads verdict and continues
```

### How the human checkpoint uses debates
At the human checkpoint, present:
```markdown
## Debated Decisions (N total)

### HIGH Impact (architecture-level)
| Decision | Options Considered | Verdict | Score | Confidence |
|----------|-------------------|---------|-------|------------|
| Database choice | PG vs Mongo vs hybrid | PostgreSQL | 7.4/10 | HIGH |
| Auth model | JWT vs sessions | JWT + refresh | 8.1/10 | HIGH |

### MEDIUM Impact
| Decision | Verdict | Confidence |
|----------|---------|------------|

[User can override any verdict — override logged as USER_OVERRIDE]
```

## Anti-Patterns

| Don't | Instead |
|-------|---------|
| Escalate trivial decisions | Use auto-research for reversible choices |
| Let debaters agree with each other | Each debater MUST argue FOR their assigned option |
| Skip weakness acknowledgment | Honest weaknesses build trust in the verdict |
| Arbitrate without reading all arguments | Arbitrator must reference specific debater points |
| Override without logging | Every user override documented with rationale |
