# Auto-Research Protocol — Self-Answering Questions Without Human Input

## When This Applies

Any agent in `--auto` mode that encounters a question it would normally ask the user.

## 5-Level Research Ladder

### Level 1: CHECK DOCUMENTS (HIGH confidence)
Search `requirements/`, `docs/BRD.md`, `docs/IMPLEMENTATION_GUIDELINES.md` for explicit statements.

### Level 2: INFER FROM CONTEXT (MEDIUM-HIGH)
Derive from related requirements, tech stack, or documented constraints.

### Level 3: WEB RESEARCH (MEDIUM)
Search web for best practices given project's tech stack and domain. Cite source URLs.

### Level 4: SENSIBLE DEFAULT (LOW-MEDIUM)
Apply industry standard defaults when research yields no clear winner.

### Level 5: DOCUMENT AS OPEN (LOW)
Best guess, flagged prominently for human review.

## Output Format

Every auto-researched answer produces an entry in `agent_state/autonomous/decisions.md`:

```markdown
## Q: [Question]
- **Research level:** [1-5] — [level name]
- **Answer:** [decision]
- **Confidence:** [HIGH | MEDIUM-HIGH | MEDIUM | LOW-MEDIUM | LOW]
- **Evidence:** [sources]
- **Risk if wrong:** [impact]
- **Review needed:** [NO | YES — reason]
```

## Pre-Checkpoint Summary

```markdown
# Decision Review
- Total: 24 | HIGH: 15 (62%) | MEDIUM: 6 (25%) | LOW: 3 (13%)
## LOW Confidence (review required) — table with question, answer, risk, phase
## MEDIUM Confidence (quick review) — table
## HIGH Confidence (auto-approved unless objected) — collapsed table
```

## Rules

- Never invent requirements — research or default, don't fabricate
- Never skip a question — every gap gets an answer at SOME level
- Always document evidence chain; always flag LOW prominently
- If sources contradict: document both, pick project-aligned one, flag for review
