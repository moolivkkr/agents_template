---
command: discuss
description: "Pre-planning context gathering. Surfaces assumptions, risks, and open questions BEFORE planning starts. Use before /plan to avoid assumptions becoming bugs."
arguments:
  - name: phase
    required: false
    description: "Phase number to discuss. Omit to auto-detect next unplanned phase."
  - name: auto
    required: false
    default: false
    description: "Skip interactive questions — use recommended defaults for all decisions. Log all auto-resolved decisions."
  - name: focus
    required: false
    description: "Focus area: 'assumptions', 'risks', 'decisions', or 'all' (default: 'all')"
---

# /discuss — Pre-Planning Context Gathering

Surfaces assumptions, risks, and open questions about a phase BEFORE `/plan` runs. The output feeds directly into `/plan` as optional context — turning guesses into documented decisions.

**Why this exists:** Planners make assumptions about the codebase, tech stack, and requirements. Most assumptions are correct. The dangerous ones are the 5-10% that seem obvious but are wrong. `/discuss` forces those into the open before they become specs, then code, then bugs.

**Prerequisites:** `docs/BRD.md` and `docs/IMPLEMENTATION_GUIDELINES.md` must exist (run `/init` first).

**Output:** `agent_state/phases/${PHASE}/DISCUSSION.md` + `agent_state/phases/${PHASE}/decisions.jsonl`

**Consumed by:** `/plan` reads `DISCUSSION.md` when it exists, loading confirmed assumptions and resolved decisions into the planner's context. This is optional — `/plan` works without it, but produces better specs when discussion context is available.

---

## Session Context Budget

> Full protocol: `.claude/skills/core/context-budget-protocol.md`. Per-step token targets below are specific to this command.

**Agent result discipline:** Every agent returns a 3-line summary to the parent. Full analysis content is in files — never echoed back to the conversation.

**Read discipline:** `phase_assumptions_analyzer` reads the codebase deeply but writes structured output to files. The parent conversation receives only the 3-line summary. `decision_researcher` instances are independent — each reads only its assigned question's context.

**Per-step targets:**
| Step | Target input tokens |
|------|---------------------|
| Step 0 Orient | ~5K (gate files + phase detection) |
| Step 1 Codebase Analysis | ~15K (BRD §FR + IMPL §components + codebase scan) |
| Step 2 Gray Area Research (per question) | ~10K (one question + guidelines + BRD context) |
| Step 3 Risk Assessment | ~12K (assumptions.md + open_questions.md + codebase state) |
| Step 4 Interactive Resolution | ~8K (summary of all items — user reads, confirms/overrides) |
| Step 5 Write Report | ~5K (compile from all step outputs) |

**Agent return protocol:** Every agent returns 3 lines to the parent:
```
✅ <agent> complete → wrote agent_state/phases/N/<file>
   Summary: <what was found — counts and severity>
   Issues: none | <N items requiring resolution>
```

---

## Pipeline Anti-Rationalization Guard

**One rule:** Never skip a step, shortcut a gate, or accept partial results — even if it "seems fine." If you're tempted to skip, that's exactly when the step matters most. The table below lists specific temptations and their correct responses.

Before skipping ANY step or accepting incomplete analysis, review this table.

| Your Internal Reasoning | Correct Response |
|---|---|
| "The codebase is simple, no hidden assumptions" | Every codebase has implicit conventions. Run the full analysis — simple codebases have the most dangerous hidden assumptions because nobody documents the obvious. |
| "The BRD is clear enough, no gray areas to research" | BRDs describe WHAT, not HOW. The gap between "what" and "how" is exactly where assumptions live. Research every MEDIUM/LOW confidence item. |
| "This is Phase 1, there's no existing code to analyze" | Phase 1 has the MOST assumptions — tech stack choices, project structure, naming conventions, error handling patterns. These set precedent for all future phases. |
| "The user will catch wrong assumptions during /plan" | Users review specs for feature correctness, not implicit assumptions about data shapes, error formats, or concurrency models. Surface these explicitly. |
| "Auto mode means skip the hard questions" | Auto mode means ANSWER the hard questions with documented defaults and log every decision. It does NOT mean skip. Every auto-resolved decision must appear in decisions.jsonl. |
| "Risk assessment is obvious — just list the big ones" | Rate every risk on a 2D matrix (impact × likelihood). Obvious risks get obvious ratings. The value is in the non-obvious risks that surface from assumption analysis. |
| "The previous phase handled this concern" | Read the previous manifest. If the concern isn't in `resolved_issues` or `known_issues`, it wasn't handled — it was assumed away. Flag it. |

---

## Step 0 — Orient

### Detect phase
```bash
# Auto-detect next unplanned phase
LAST_PLANNED=$(ls docs/design/phases/ 2>/dev/null | grep -oP '\d+' | sort -n | tail -1)
PHASE=${ARG_PHASE:-$(( ${LAST_PLANNED:-0} + 1 ))}
echo "▶ Discussing Phase $PHASE"
```

### Gate check
If PHASE > 1: verify `agent_state/phases/$((PHASE-1))/gate.passed` exists.
If missing: **STOP** — `Phase $((PHASE-1)) has not completed. Run /develop --phase=$((PHASE-1)) first.`

### Check for existing discussion
```bash
HAS_DISCUSSION=$([ -f "agent_state/phases/${PHASE}/DISCUSSION.md" ] && echo true || echo false)
HAS_DECISIONS=$([ -f "agent_state/phases/${PHASE}/decisions.jsonl" ] && echo true || echo false)
```

**If discussion exists:**
- Inform user: `Discussion for Phase ${PHASE} already exists (created <date>).`
- Offer: `Re-run full discussion? Or skip to review existing decisions?`
- If `--auto`: re-run full discussion (overwrite previous — stale discussions are worse than no discussion)

### Create output directories
```bash
mkdir -p agent_state/phases/${PHASE}
mkdir -p agent_state/phases/${PHASE}/research
```

### Agent Context Protocol — ALL agents read these before producing output

**REQUIRED READS (all agents):**
- `docs/BRD.md` — objectives (OBJ-*), functional requirements (FR-*), NFRs, gate checklists
- `docs/IMPLEMENTATION_GUIDELINES.md` — tech stack, component inventory, design constraints
- `agent_state/phases/$((PHASE-1))/manifest.json` — what previous phase built (when PHASE > 1)
- `agent_state/agent_registry.json` — active agents and skill packs for this project

---

## Step 1 — Codebase Analysis

**Agent:** `phase_assumptions_analyzer`

Deep analysis of the codebase, BRD, and implementation guidelines to surface every assumption a planner would make. This is the most important step — it produces the raw material for all subsequent steps.

The agent reads:
1. BRD requirements assigned to this phase (FR-* rows)
2. IMPLEMENTATION_GUIDELINES component inventory and tech stack
3. Previous phase manifests (if PHASE > 1)
4. Actual codebase — file structure, existing patterns, data models, API contracts

Produces two files:

**`agent_state/phases/${PHASE}/assumptions.md`** — structured assumptions with evidence levels:
```markdown
# Phase N Assumptions Analysis

## Codebase State Summary
- Files scanned: N
- Components found: [list]
- Patterns observed: [list]
- Data models: [list]

## Assumptions

### CONFIRMED (directly observed — safe to build on)
| # | Assumption | Evidence | File:Line |
|---|-----------|----------|-----------|
| 1 | Auth uses JWT with RS256 | Found in auth middleware | src/middleware/auth.go:23 |

### DEDUCED (logical inference — verify if high-impact)
| # | Assumption | Inference Chain | Confidence |
|---|-----------|----------------|------------|
| 1 | Service layer uses repository pattern | All services inject repo interfaces + no direct DB calls in services | HIGH |

### HYPOTHESIZED (plausible but unverified — MUST resolve before planning)
| # | Assumption | What Would Confirm It | What Would Refute It | Impact if Wrong |
|---|-----------|----------------------|---------------------|-----------------|
| 1 | WebSocket support for real-time updates | Finding ws dependency in go.mod | REST-only pattern in all handlers | HIGH — would require different API design |
```

**`agent_state/phases/${PHASE}/open_questions.md`** — questions requiring user input or research:
```markdown
# Open Questions — Phase N

## Requires User Decision
| # | Question | Options | Default Recommendation | Why It Matters |
|---|---------|---------|----------------------|----------------|

## Requires Research
| # | Question | What to Search For | Confidence Without Answer |
|---|---------|-------------------|--------------------------|

## Requires Codebase Investigation
| # | Question | Where to Look | Blocking? |
|---|---------|---------------|-----------|
```

**Focus filtering:** If `--focus=assumptions`, only produce `assumptions.md`. If `--focus=decisions`, prioritize `open_questions.md` with emphasis on decision points. Default (`all`): produce both.

---

## Step 2 — Gray Area Research (PARALLEL per question)

**Agent:** `decision_researcher` (one instance per question)
**Skip if:** `--focus=assumptions` (assumptions-only mode)
**Depends on:** Step 1 (needs `open_questions.md`)

For each question in `open_questions.md` marked as "Requires Research" with MEDIUM or LOW confidence:

1. Spawn one `decision_researcher` instance per question
2. Each instance researches options, produces comparison table
3. Results written to `agent_state/phases/${PHASE}/research/<question-slug>.md`

**If `--auto`:** After research completes, auto-select the recommended option for each question. Write the decision to `decisions.jsonl` with `"resolved_by": "auto"`.

**If interactive:** Hold results for Step 4 presentation.

**Parallelization limit:** Max 5 concurrent researcher instances (prevent context explosion). Queue remaining questions.

Each researcher output follows this format:
```markdown
# Research: <Question Title>

## Question
<exact question from open_questions.md>

## Options Evaluated
| Option | Pros | Cons | Risk | Effort | Fits BRD? |
|--------|------|------|------|--------|-----------|
| A      | ...  | ...  | LOW  | 2d     | Yes       |
| B      | ...  | ...  | MED  | 3d     | Partial   |

## Evidence Sources
- [source 1 — URL or file path]
- [source 2]

## Recommendation
**Option A** — [2-sentence rationale with BRD/NFR alignment]

## Confidence: HIGH | MEDIUM | LOW
[Why this confidence level — what additional data would increase it]
```

---

## Step 3 — Risk Assessment

**Depends on:** Steps 1 + 2 (needs assumptions + research results)
**Skip if:** `--focus=assumptions` or `--focus=decisions`

Analyze all assumptions, open questions, and research results to identify implementation risks.

### Risk Classification

For each risk, classify on two dimensions:

**Category:**
| Category | Description | Examples |
|----------|-------------|---------|
| TECHNICAL | Code complexity, unfamiliar patterns, novel algorithms | "No team experience with WebSocket — learning curve risk" |
| INTEGRATION | Cross-component coupling, API contract mismatches | "Frontend expects paginated response but spec shows flat array" |
| DATA | Schema design, migration complexity, data integrity | "Changing user.role from string to enum requires data migration" |
| PERFORMANCE | NFR targets at risk, scalability concerns | "Full-text search on 1M rows without index — NFR-PERF-002 at risk" |
| SECURITY | Authentication gaps, authorization bypasses, data exposure | "Admin endpoints rely on client-side role check only" |
| DEPENDENCY | External library risk, version conflicts, deprecation | "Library X last updated 18 months ago — maintenance risk" |

**Severity (Impact x Likelihood):**

```
              Impact
              HIGH    MEDIUM    LOW
Likelihood
  HIGH        CRITICAL  HIGH    MEDIUM
  MEDIUM      HIGH      MEDIUM  LOW
  LOW         MEDIUM    LOW     LOW
```

### Output: `agent_state/phases/${PHASE}/risks.md`

```markdown
# Risk Assessment — Phase N

## Risk Matrix Summary
| Severity | Count | Action Required |
|----------|-------|-----------------|
| CRITICAL | N     | Must mitigate before /plan |
| HIGH     | N     | Mitigate during /plan or early /develop |
| MEDIUM   | N     | Monitor — address if scope allows |
| LOW      | N     | Accept — document only |

## CRITICAL Risks
| # | Risk | Category | Impact | Likelihood | Mitigation | Owner |
|---|------|----------|--------|------------|------------|-------|

## HIGH Risks
| # | Risk | Category | Impact | Likelihood | Mitigation | Owner |
|---|------|----------|--------|------------|------------|-------|

## MEDIUM Risks
[same format]

## LOW Risks
[same format]

## Risk-to-Assumption Traceability
| Risk # | Originates from Assumption # | Evidence Level |
|--------|------------------------------|----------------|
| R-1    | A-3 (HYPOTHESIZED)          | Would be eliminated if assumption confirmed |
```

---

## Step 4 — Interactive Resolution (skip if --auto)

**Skip if:** `--auto` flag is set (all decisions auto-resolved in Step 2)
**Skip if:** `--focus=assumptions` (no decisions to resolve)

Present a structured summary of everything found to the user for confirmation.

### Presentation Order

1. **CRITICAL risks** — must address before proceeding
2. **HYPOTHESIZED assumptions** — need confirmation or refutation
3. **Open questions with research results** — user picks option or confirms recommendation
4. **DEDUCED assumptions** — user confirms or corrects
5. **HIGH risks** — user decides mitigation strategy

### For each item, user can:
- **Confirm** — accept as-is (default for CONFIRMED assumptions)
- **Override** — provide a different answer/decision
- **Defer** — push to `/plan` for later resolution (adds to `deferred_decisions` in report)
- **Reject** — remove from consideration (with reason)

### Record every response:
```jsonl
{"id":"D-001","type":"assumption","item":"Auth uses JWT RS256","resolution":"confirmed","resolved_by":"user","timestamp":"<ISO>","phase":N}
{"id":"D-002","type":"question","item":"Use repository pattern or direct DB?","resolution":"override","value":"Direct DB for Phase 1, refactor later","resolved_by":"user","timestamp":"<ISO>","phase":N}
{"id":"D-003","type":"risk","item":"WebSocket learning curve","resolution":"defer","reason":"Not needed until Phase 3","resolved_by":"user","timestamp":"<ISO>","phase":N}
```

---

## Step 5 — Write Discussion Report

Compile all outputs into the final discussion report and decision log.

### Output 1: `agent_state/phases/${PHASE}/DISCUSSION.md`

```markdown
# Discussion Report — Phase N

> Generated by /discuss on <date>. Consumed by /plan as optional context.
> Re-run /discuss to update if codebase or requirements change.

## Summary
- Assumptions analyzed: N (CONFIRMED: N, DEDUCED: N, HYPOTHESIZED: N)
- Open questions: N (resolved: N, deferred: N)
- Risks identified: N (CRITICAL: N, HIGH: N, MEDIUM: N, LOW: N)
- Decisions made: N (user: N, auto: N, deferred: N)

## Confirmed Assumptions (safe for /plan to build on)
| # | Assumption | Evidence | Source |
|---|-----------|----------|--------|

## Resolved Decisions (binding for /plan)
| # | Decision | Choice | Rationale | Resolved By |
|---|----------|--------|-----------|-------------|

## Deferred Decisions (flagged for /plan to handle)
| # | Decision | Options | Why Deferred |
|---|----------|---------|-------------|

## Active Risks (must be addressed in /plan specs)
| # | Risk | Severity | Mitigation Strategy |
|---|------|----------|---------------------|

## Rejected Items (excluded with reason)
| # | Item | Reason for Rejection |
|---|------|---------------------|

## Codebase State at Discussion Time
<hash of latest commit when discussion ran — stale detection>
```

### Output 2: `agent_state/phases/${PHASE}/decisions.jsonl`

One JSON line per decision (format shown in Step 4). This file is machine-readable for downstream tooling and reconciliation.

### Output 3: Summary to user

```
✅ Phase N discussion complete

   Assumptions: N analyzed (N confirmed, N deduced, N hypothesized)
   Questions: N researched (N resolved, N deferred)
   Risks: N identified (N critical, N high)
   Decisions: N recorded

   ▶ Next: /plan --phase=N
```

---

## Integration with /plan

When `/plan` runs and `agent_state/phases/${PHASE}/DISCUSSION.md` exists:

1. `project_planner` reads the Discussion Report as additional context
2. CONFIRMED assumptions become constraints — planner does not re-derive them
3. Resolved decisions are binding — planner implements the chosen option, not an alternative
4. Deferred decisions are surfaced as open items in `PHASE_PLAN.md`
5. Active risks are incorporated into the wave structure (high-risk items early, with fallback plans)
6. Stale detection: if git HEAD differs from the discussion's commit hash, warn user that codebase changed since discussion

**If no discussion exists:** `/plan` proceeds normally. Discussion is optional but recommended — especially for Phase 1 (most assumptions) and phases with significant architectural decisions.

---

## Rules

### Execution rules
- Every assumption must have an evidence level (CONFIRMED/DEDUCED/HYPOTHESIZED). No unclassified assumptions.
- Every risk must have a severity rating (Impact x Likelihood). No unrated risks.
- Every decision must be recorded in `decisions.jsonl` with resolver identity (user/auto).
- `--auto` resolves ALL questions — it does not skip any. Every auto-resolution is logged.
- If the codebase has zero files (Phase 1 of a new project), Step 1 still runs — it analyzes BRD + IMPL_GUIDELINES assumptions about the tech stack, project structure, and conventions that will be established.

### Quality rules
- HYPOTHESIZED assumptions with HIGH impact MUST be resolved (by user or research) before the discussion report is written. Do not write the report with unresolved high-impact hypotheses.
- Research results (Step 2) must include at least 2 options per question. Single-option research is not research — it's confirmation bias.
- Risk-to-assumption traceability is mandatory. Every risk must trace to the assumption or question that generated it.

### Anti-staleness rules
- Record git HEAD hash in the discussion report. If `/plan` detects a different HEAD, it warns about potential staleness.
- If re-running `/discuss` on a phase that already has a discussion: overwrite the old report entirely. Partial merges create inconsistency.
- Decisions from a previous `/discuss` run are NOT automatically carried forward to a re-run. Each run is a fresh analysis.
