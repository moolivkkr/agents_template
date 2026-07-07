# Agent Common Protocol — shared blocks every agent inherits

> **Purpose.** Three things were missing or inconsistent across the agent fleet: (1) the ground-truth
> reading invariant lived under different headings, (2) only 4 of 68 agents self-verified before
> returning, and (3) 0 of 68 wrote lessons back — so the Tier 1 memory system received no data. This
> file is the single canonical source for those shared blocks. Agents reference it; new agents copy
> these blocks verbatim. `AGENT_SCHEMA.md` mandates all three.

---

## Block 1 — Required Reading (ground truth FIRST)

Every agent's `## Required Reading` section MUST begin with these two items, in this order, before
any project/spec file:

```
0. **`docs/PROJECT_FACTS.md` — GROUND TRUTH. Read FIRST, before any other file.** Retired/renamed
   components, hard constraints, environment facts. OVERRIDES any conflicting assumption in this
   prompt, the specs, or your training. If your task touches anything RETIRED/superseded there, STOP
   and flag it. (Protocol: `.claude/skills/core/shared-context-protocol.md`)
0b. **`docs/DECISIONS.md` — settled decisions (Tier 0.5).** Prior decisions with rationale. Do not
   re-litigate an active decision without new evidence; if new evidence contradicts one, append a
   reversing entry or escalate — don't silently diverge.
```

The heading MUST be `## Required Reading` (not `## Skill Packs to Load`, not `## Tech Context`) so a
grep-based invariant check (`/health` 5.5e) can verify it.

---

## Block 2 — Definition of Done (self-verify before returning)

Every agent MUST end its work with an explicit self-check. A silent no-op or a stub report is the
single largest failure mode (a report file exists, so the gate passes, but the work never happened).
Copy this block, specialized to the agent's output:

```
## Definition of Done (verify before returning — do not report success until all pass)
- [ ] Output written to the EXACT path in my frontmatter `output.primary` (not a nearby path).
- [ ] Output is real content, not a stub/placeholder/"TODO" — it would satisfy a skeptical reviewer.
- [ ] Every claim / finding cites `file:line` (or the specific artifact it is derived from).
- [ ] Any counts I report (tests, findings, coverage) are REAL numbers I derived, not estimates.
- [ ] If I found nothing / could not proceed, I say so explicitly with the reason — I do NOT emit an
      empty-but-present report that reads as success.
- [ ] I logged a completion line to `agent_state/phases/${PHASE}/execution.jsonl` (roster check).
```

**Anti-rationalization:** "the output looks about right, no need to re-check" is how stubs ship.
Run the checklist.

---

## Block 3 — Lessons write-back (feed Tier 1 memory)

When an agent encounters something a FUTURE phase should know — a pattern that worked, an issue hit,
an anti-pattern, an agent-performance problem — it appends a tagged lesson so the memory system
actually receives data. Without this, `memory_search` returns nothing forever.

Append to `agent_state/phases/${PHASE}/lessons.md` (aggregated to the root index at gate — see
`memory-as-tools.md` / `structured-lessons.md`):

```
### L-${PHASE}-<seq>
- **Category:** testing|implementation|security|performance|infrastructure|agent_performance|planning|ux
- **Tags:** <comma-separated: language, domain, pattern>
- **Type:** pattern_that_worked|issue_encountered|agent_issue|anti_pattern|recommendation
- **Summary:** <one line>
- **Detail:** <2-3 lines with context>
- **Evidence:** <report/file that proves it>
- **Reuse:** <actionable instruction for a future phase>
```

Only write a lesson when there IS one — do not manufacture filler. Zero lessons is a valid outcome
for a clean, unremarkable run.

---

## Block 4 — Unified Severity Model (for any agent that produces findings)

Reviewers, testers, reconcilers, scanners, and verifiers MUST classify findings with ONE model so
the gate can map them uniformly (full model: `.claude/skills/core/code-quality.md`):

| Severity | Meaning | Gate impact |
|---|---|---|
| **BLOCKING** | Correctness/security/data-loss; in-scope requirement unmet | Blocks the gate — must fix or explicitly carry forward with reason |
| **WARNING** | Real problem, has a workaround, or out-of-scope-but-noted | Does not block; tracked in known_issues |
| **INFO** | Style/suggestion/nice-to-have | Advisory only |

End every findings report with a one-line count: `BLOCKING:N WARNING:N INFO:N`.

---

## Block 5 — Output template requirement

Any agent that writes a report MUST include an explicit output template (a fenced markdown block
showing the report's shape) in its definition, so format doesn't drift run-to-run. An agent with a
prose-only "Output" description is a format-drift and silent-stub risk.
