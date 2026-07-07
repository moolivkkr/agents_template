---
skill: auto-research
description: Self-answering protocol — resolve open questions via research (web + code) instead of pausing for human input, with a confidence threshold
version: "1.0"
tags:
  - research
  - autonomy
  - decisions
  - web
  - core
---

# Auto-Research Protocol — Self-Answering Questions Without Human Input

## When This Protocol Applies

Any agent running in `--auto` mode that encounters a question it would normally ask the user. Instead of blocking, the agent researches the answer using this 5-level escalation ladder.

## The 5-Level Research Ladder

### Level 1: CHECK DOCUMENTS (confidence: HIGH)
Search `requirements/`, `docs/BRD.md`, `docs/IMPLEMENTATION_GUIDELINES.md` for explicit statements.

```
Question: "What auth method should we use?"
Search: grep -i "auth\|jwt\|session\|oauth" requirements/*.md docs/*.md
Found: requirements/tech-spec.md:14 — "Use JWT for stateless authentication"
→ Answer: JWT (HIGH confidence, source: requirements/tech-spec.md:L14)
```

### Level 2: INFER FROM CONTEXT (confidence: MEDIUM-HIGH)
Derive from related requirements, tech stack, or constraints already documented.

```
Question: "What pagination page size?"
Context: BRD says "mobile-first", NFR-PERF says "< 200ms response"
Inference: Mobile screens show ~10-20 items. 20 is standard for API pagination.
→ Answer: 20 items/page (MEDIUM-HIGH confidence, source: inferred from mobile-first + performance NFR)
```

### Level 3: WEB RESEARCH (confidence: MEDIUM)
Search the web for best practices given the project's specific tech stack and domain.

```
Question: "What email provider for transactional emails?"
Search: "best transactional email provider 2026 [project tech stack]"
Findings: Resend (modern, developer-friendly), SendGrid (established), AWS SES (cheapest)
Context: IMPL_GUIDELINES shows TypeScript + Next.js → Resend has best DX for this stack
→ Answer: Resend (MEDIUM confidence, source: web research + tech stack fit)
```

### Level 4: SENSIBLE DEFAULT (confidence: LOW-MEDIUM)
Apply industry standard defaults when research yields no clear winner.

```
Question: "What rate limit for auth endpoints?"
No project-specific guidance found.
Industry standard: 5 attempts per minute per IP for login, 3 for password reset
→ Answer: 5/min login, 3/min reset (LOW-MEDIUM confidence, source: industry default)
```

### Level 5: DOCUMENT AS OPEN (confidence: LOW)
Truly cannot determine — use best guess, flag prominently for human review.

```
Question: "Should deleted users' data be anonymized or purged?"
No requirements mention data retention policy. Legal implications.
→ Answer: Soft-delete with 30-day retention, then anonymize (LOW confidence)
→ Flag: ⚠ REQUIRES HUMAN REVIEW — legal/compliance decision
```

## Output Format

Every auto-researched answer MUST produce this entry in `agent_state/autonomous/decisions.md`:

```markdown
## Q: [Question that would have been asked to user]
- **Research level:** [1-5] — [CHECK DOCS | INFER | WEB RESEARCH | DEFAULT | OPEN]
- **Answer:** [The decision made]
- **Confidence:** [HIGH | MEDIUM-HIGH | MEDIUM | LOW-MEDIUM | LOW]
- **Evidence:**
  - [Source 1: file path, URL, or reasoning chain]
  - [Source 2: ...]
- **Risk if wrong:** [Impact description — what breaks if this decision is incorrect]
- **Phase affected:** [Which phase this decision impacts]
- **Review needed:** [NO | YES — reason]
```

## Confidence Aggregation for Human Checkpoint

Before the human checkpoint, produce a summary:

```markdown
# Decision Review — Pre-Implementation Checkpoint

## Statistics
- Total decisions: 24
- HIGH confidence: 15 (62%) — likely correct, review optional
- MEDIUM confidence: 6 (25%) — reasonable, quick review recommended
- LOW confidence: 3 (13%) — ⚠ NEEDS HUMAN INPUT

## LOW Confidence Decisions (review required)
| # | Question | Auto-Answer | Risk | Phase |
|---|----------|------------|------|-------|
| 1 | Data retention policy | Soft-delete + 30d | Legal risk | 2 |
| 2 | Third-party SMS provider | Twilio | Cost implications | 3 |
| 3 | HIPAA compliance scope | Not in scope | Regulatory risk | 1 |

## MEDIUM Confidence Decisions (quick review)
[table of 6 items]

## HIGH Confidence Decisions (auto-approved unless objected)
[table of 15 items — collapsed by default]
```

## Rules

- NEVER invent requirements — research or default, don't fabricate
- NEVER skip a question — every gap gets an answer at SOME confidence level
- ALWAYS document the evidence chain — future sessions need to understand WHY
- ALWAYS flag LOW confidence decisions prominently — these are the ones humans must review
- Web research results: cite the source URL, don't just say "web research"
- If two sources contradict: document both, pick the one aligned with project constraints, flag for review
