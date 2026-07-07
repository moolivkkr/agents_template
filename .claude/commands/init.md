---
command: init
description: Initialize a new project — read ./requirements/, create BRD and IMPLEMENTATION_GUIDELINES, generate project-specific agents, write CLAUDE.md. Run once at project start.
arguments:
  - name: update_agents
    required: false
    default: false
    description: "Re-run agent_factory only — skip BRD and IMPLEMENTATION_GUIDELINES steps (use after tech stack changes)"
  - name: brd_only
    required: false
    default: false
    description: "Re-run BRD creation only — skip IMPLEMENTATION_GUIDELINES and agent generation"
  - name: auto
    required: false
    default: false
    description: "Auto-research mode — agents research answers instead of asking user. Logs all decisions with confidence levels to agent_state/autonomous/decisions.md"
---

# /init — Project Initialization

Bootstraps a new project from scratch. Reads `./requirements/`, produces `docs/BRD.md` and `docs/IMPLEMENTATION_GUIDELINES.md`, generates project-specific agents, and writes `CLAUDE.md`.

**Run once at project start. Use `/plan` to begin phase work.**

## Session Context Budget

> Full protocol: `.claude/skills/core/context-budget-protocol.md`. Per-step token targets below are specific to this command.

**Read discipline:** `brd_agent` and `impl_guidelines_agent` run in parallel — each reads only its own input files. They do NOT read each other's outputs mid-run.

**Agent result discipline:** Each agent returns a 3-line summary to the parent. Full BRD and IMPLEMENTATION_GUIDELINES content stays in files — never echoed back.

**Per-step targets:**
| Step | Target input tokens |
|------|---------------------|
| Step 1+2 BRD + IMPL | ~20K (requirements/ files only) |
| Step 1.5 Cross-validation | ~15K (BRD summary + IMPL summary) |
| Step 2b Reconcile (req↔BRD) | ~15K (requirements index + BRD summary) |
| Step 2c Reconcile (research↔BRD) | ~10K (audit files + BRD section refs) |
| Step 2d BRD quality audit | ~8K (BRD sections + checklist) |
| Step 3 Agent factory | ~10K (IMPL §Tech Stack + §Components only) |
| Step 3.5 Agent validation | ~5K (generated agent frontmatter only) |

---

## Step 0 — Scan ./requirements/

```bash
ls -la requirements/
```

Inventory all files found. Categorize each:
- Functional specs, user stories, feature lists → feed `brd_agent`
- `IMPLEMENTATION_GUIDELINES.md` → feed `impl_guidelines_agent`
- API contracts, wireframes, architecture docs → feed both agents as context

Print inventory:
```
Found in ./requirements/:
  functional-spec.md           → BRD seed
  user-stories.md              → BRD seed
  IMPLEMENTATION_GUIDELINES.md → Tech stack seed
  wireframes/dashboard.png     → BRD context
  (empty)                      → Will conduct full interview
```

If `--update_agents` flag: skip to Step 3.
If `--brd_only` flag: skip to Step 1 only, then stop.

---

## Step 1 + 2 — BRD and IMPLEMENTATION_GUIDELINES (PARALLEL)

Run both agents simultaneously — they read from `./requirements/` independently.

### Step 1: `brd_agent`

**Agent:** `brd_agent`
**Input:** All files in `./requirements/` except `IMPLEMENTATION_GUIDELINES.md`
**Output:** `docs/BRD.md`

The agent:
1. Reads all requirement documents found in Step 0
2. Extracts and maps content to BRD sections (objectives, features, NFRs, personas)
3. Identifies gaps — what's missing for a complete, numbered BRD
4. Asks the user targeted questions ONLY for genuine gaps (not a full re-interview if docs exist)
5. Writes `docs/BRD.md` with:
   - Numbered objectives (OBJ-01, OBJ-02, ...)
   - Numbered functional requirements (FR-001, FR-002, ...)
   - Numbered non-functional requirements (NFR-PERF-01, NFR-SEC-01, ...)
   - User personas
   - Out of scope section
   - Quality gate checklists (Gate 1 / 2 / 3)
   - Traceability matrix (requirement → phase mapping, filled after Step 4)

### Step 2: `impl_guidelines_agent`

**Agent:** `impl_guidelines_agent`
**Input:** `./requirements/IMPLEMENTATION_GUIDELINES.md` (if present), any architecture/technical docs in `./requirements/`
**Output:** `docs/IMPLEMENTATION_GUIDELINES.md`

The agent:
1. Reads `./requirements/IMPLEMENTATION_GUIDELINES.md` if it exists
2. Evaluates for missing or ambiguous context:
   - Components listed without tech decisions?
   - Architecture pattern unclear?
   - Database selected but no migration tool?
   - Infrastructure mentioned but no local dev setup?
   - Missing design constraints (API versioning, test coverage targets)?
3. Asks targeted clarifying questions for gaps only
4. Writes confirmed `docs/IMPLEMENTATION_GUIDELINES.md` with sections:

```markdown
## 1. Tech Stack
| Layer    | Technology | Version | Notes |

## 2. Architecture Overview
- Pattern: (Monolith / Modular Monolith / Microservices)
- [Mermaid component diagram]

## 3. Component Inventory
| Component | Responsibility | Technology | Depends On |

## 4. Design Constraints
- API versioning convention
- Test coverage requirements
- Code conventions (repository pattern, no direct DB in handlers, etc.)

## 5. Local Dev Environment
| Service | Port | Start Command |
```

**⚠ Both agents run in parallel. Step 3 waits for BOTH to complete.**

---

## Step 1.5 — Post-Clarification Cross-Validation (CLOSED LOOP)

**Runs after:** Both `brd_agent` and `impl_guidelines_agent` have completed their user interviews and produced draft outputs.
**Executor:** Init orchestrator (inline — reads both documents and runs checklist, no subagent needed)
**Purpose:** Catch contradictions between user answers given to different agents, internal inconsistencies within the BRD, and NFR↔tech stack feasibility gaps.

**Checks:**
1. **BRD internal consistency:**
   - No FR-* references NFR-* IDs that don't exist (and vice versa)
   - No persona references features not in scope
   - No contradictory constraints (e.g., "offline-first" + "real-time sync required" without reconciliation)
2. **BRD ↔ IMPLEMENTATION_GUIDELINES consistency:**
   - Tech stack in IMPL_GUIDELINES can support all NFR-* (e.g., if NFR says "sub-50ms latency", IMPL_GUIDELINES doesn't specify a language/framework known to be slow for that workload)
   - Component inventory covers all FR-* (no feature without a component to implement it)
   - Auth mechanism in IMPL_GUIDELINES matches auth requirements in BRD
3. **User answer consistency:**
   - If user told `brd_agent` "users are internal only" but told `impl_guidelines_agent` "public-facing API with rate limiting" → contradiction
4. **NFR ↔ Tech Stack Feasibility (CRITICAL):**
   For EVERY NFR-* in the BRD:
   - Is there a component in IMPLEMENTATION_GUIDELINES §3 that owns this NFR?
   - Is the required technology in IMPLEMENTATION_GUIDELINES §1 Tech Stack?
   - If NFR requires new infrastructure (OTEL, Redis, message queue, etc.), is it in Docker Compose / §5 Local Dev?
   - If any NFR has NO supporting component or technology → BLOCK and surface to user

   For EVERY component in IMPLEMENTATION_GUIDELINES §3:
   - Is there at least one FR-* or NFR-* that requires this component?
   - If not, flag as potentially unnecessary (inform, don't block)

**On contradiction or feasibility gap found:**
- Surface the specific issue to user with both conflicting statements
- Ask user to resolve: "NFR-OBS-01 requires distributed tracing but IMPLEMENTATION_GUIDELINES has no OTEL components. Add OTEL to tech stack?"
- Max 1 round of clarification → update the affected document
- **Infrastructure NFRs (observability, security, data) are NOT auto-deferrable** — they must be explicitly resolved

**On pass:** Proceed to Step 2b.

---

## Step 2b — Reconciliation Point A: Requirements ↔ BRD

**Agent:** `requirements_brd_reconciler` (runs immediately after Step 1+2 complete)

Validates both directions:
- **Forward:** features/constraints in `./requirements/` that didn't make it into `docs/BRD.md`
- **Reverse:** requirements in `docs/BRD.md` with no source in `./requirements/` (invented)

Output: `agent_state/reconciliation/requirements_vs_brd.md`

If MISSING or INVENTED items found: surface to user before continuing.
User decides: update BRD, or accept with rationale. Does not auto-proceed if gaps exist.

---

## Step 2c — Research ↔ BRD Reconciliation (when research/ exists)

**Runs after:** Step 2b
**Executor:** `requirements_brd_reconciler` agent (extended scope — same agent as Step 2b, second pass with research inputs)
**Skip if:** No `requirements/research/` directory exists (project initialized without `/research`)

When `/research` was run before `/init`, the research directory contains critical audit documents that the BRD MUST incorporate. This step verifies incorporation.

**Check 1: Contradiction Audit Incorporation**
If `requirements/research/contradiction-audit.md` exists:

| Contradiction Status | BRD Action Required |
|---------------------|---------------------|
| CONFLICT | BRD MUST contain the corrected value, NOT the original spec claim |
| CORRECTION | BRD MUST use the corrected version |
| REFINEMENT | BRD SHOULD use the more specific numbers |
| UNVERIFIABLE | BRD MUST list as Open Question |

For each CONFLICT/CORRECTION in the audit → verify the BRD actually incorporated the fix. If not → BLOCK.

**Check 2: Completeness Audit Incorporation**
If `requirements/research/completeness-audit.md` exists:

For each dimension scored < 70%:
- Is it addressed in the BRD (as a requirement, constraint, or explicit out-of-scope)?
- Infrastructure dimensions (observability, security, data retention, monitoring) are **NOT auto-deferrable** — they must be explicitly resolved with user or have a documented NFR
- Non-infrastructure dimensions (localization, deprecation) may be scoped out with rationale

**Check 3: Edge Case Coverage**
If `requirements/research/08b-edge-cases.md` exists:

For every P0 feature with edge cases documented:
- Does the corresponding FR-* in the BRD have acceptance criteria that cover the edge cases?
- At minimum: happy path + 2 error paths + 1 boundary case per P0 FR-*
- If edge cases exist in research but NOT in BRD ACs → flag as gap

**Check 4: NFR Evidence Traceability**
If `requirements/research/08c-performance-baselines.md` exists:

For every NFR-PERF-* in the BRD:
- Does it cite a source from the performance baselines research?
- If NFR has no evidence source → flag (may be an arbitrary target)

**Check 5: Visual Spec Linkage**
If `requirements/research/08d-visual-specifications.md` exists:

For any FR-* related to UI fidelity:
- Does the FR reference specific values from the visual spec (hex colors, px dimensions, animation values)?
- At minimum, the FR should state: "Implements visual specifications documented in 08d-visual-specifications.md"

**Output:** `agent_state/reconciliation/research_vs_brd.md`

If BLOCK items found: surface to user. Do NOT auto-proceed.

---

## Step 2d — BRD Quality Self-Audit

**Runs after:** Step 2c (or Step 2b if no research exists)
**Executor:** Init orchestrator (inline — reads BRD and runs gap-analysis checklist)
**Purpose:** Quality gate on the BRD itself — ensures the BRD covers all dimensions downstream agents expect.

Run the 17-dimension gap-analysis checklist (`.claude/skills/requirements/gap-analysis-checklist.md`) against `docs/BRD.md`:

```
| # | Dimension | Covered in BRD? | BRD Section | Completeness | Gap |
|---|-----------|-----------------|-------------|-------------|-----|
| 1 | Target Users / Actors | ? | §3 Personas | ? | ? |
| 2 | Business Objectives | ? | §2 Objectives | ? | ? |
| 3 | Scope Boundary | ? | §7 Out of Scope | ? | ? |
| 4 | Non-Functional Targets | ? | §5 NFRs | ? | ? |
| 5 | Error / Failure Handling | ? | ACs in FR-* | ? | ? |
| 6 | External Integrations | ? | §6 Constraints or §4 FRs | ? | ? |
| 7 | Data Ownership | ? | NFR-MAINT-* | ? | ? |
| 8 | Compliance | ? | NFR-SEC-* or N/A | ? | ? |
| 9 | Rollout / Phasing | ? | §11 Phasing | ? | ? |
| 10-17 | ... | ... | ... | ... | ... |
```

**Additional quality checks:**
- Every FR-* has acceptance criteria? (at minimum happy path + 1 error path)
- Every NFR-* has a measurable target? (not "fast" but "< 100ms p95")
- Every OBJ-* has success metrics? (not "good quality" but "80% test coverage")
- Every persona has at least one journey map or workflow?
- Open Questions section exists and captures unresolved items?
- Definition of Ready and Definition of Done checklists present?

**Output:** `agent_state/init/brd_quality_audit.md`

**Scoring:**
- **PASS** (>= 80% overall, zero CRITICAL gaps) → proceed to Step 3
- **WARN** (60-79% or non-critical gaps) → surface gaps, user decides to proceed or fix
- **FAIL** (< 60% or CRITICAL gaps) → BLOCK, must fix before proceeding

---

## Step 3 — Generate Project-Specific Agents

**Agent:** `agent_factory`
**Input:** `docs/IMPLEMENTATION_GUIDELINES.md`
**Output:** `.claude/agents/generated/*.md`, `agent_state/agent_registry.json`

Reads Section 1 (Tech Stack) and Section 3 (Component Inventory) from the confirmed IMPLEMENTATION_GUIDELINES. Populates templates from `.claude/agents/templates/` and writes generated agents to `.claude/agents/generated/`.

See `agent_factory.md` for full template-population logic.

---

## Step 3.5 — Validate Generated Agents

**Runs after:** Step 3
**Executor:** Init orchestrator (inline — reads agent frontmatter and checks file paths)
**Purpose:** Ensure generated agents are correctly instantiated and will work when `/develop` invokes them.

For each agent in `.claude/agents/generated/`:

1. **Template variable resolution:** No remaining `{{PLACEHOLDER}}` tokens in the file
2. **Skill pack existence:** Every path in `skill_packs:` → file exists in `.claude/skills/`
3. **Input path validity:** Every `input.required` path will exist after `/plan` or `/develop` creates it
4. **Model tier correctness:**
   - Review/judgment agents → `opus`
   - Implementation/generation agents → `sonnet`
   - Execution/scanning agents → `haiku`
5. **Dependency reciprocity:** If agent A lists B in `upstream`, agent B should list A in `downstream`

**Output:** `agent_state/init/agent_validation.md`

```
| Agent | Variables Resolved? | Skill Packs Valid? | Model Correct? | Issues |
|-------|--------------------|--------------------|----------------|--------|
| go_backend_developer_calc.md | Yes | Yes (5/5) | sonnet ✓ | None |
| react_ui_developer_calc.md | Yes | Yes (8/8) | sonnet ✓ | None |
```

If any agent has unresolved variables or missing skill packs → BLOCK. Fix before proceeding.

---

## Step 4 — Write CLAUDE.md

Write `CLAUDE.md` at the project root with:

```markdown
# <PROJECT_NAME> — Project Context

## What We're Building
<One paragraph from BRD executive summary>

## Tech Stack
<Condensed table from IMPLEMENTATION_GUIDELINES Section 1>

## Key Documents
| Document | Path | Purpose |
|----------|------|---------|
| BRD | docs/BRD.md | Numbered requirements — all agents cite FR-*, NFR-*, OBJ-* |
| Implementation Guidelines | docs/IMPLEMENTATION_GUIDELINES.md | Tech stack, components, constraints |
| Phase specs | docs/design/phases/N/specs/ | TRDs and wireframes per phase |
| Agent registry | agent_state/agent_registry.json | Generated agents and skill packs |

## Active Agents
<List of generated agents from agent_registry.json>

## Phase Gate State
<Current state — "No phases started. Run /plan --phase=1 to begin.">

## Local Dev Setup
<From IMPLEMENTATION_GUIDELINES Section 5>

## Common Tasks
<Auto-generated from tech stack — e.g. docker compose up, go test ./..., npm test>
```

Also embed the **Ground Truth** block from `.claude/templates/CLAUDE.md.template` (the
`⛔ GROUND TRUTH` section pointing at `docs/PROJECT_FACTS.md`) near the top of CLAUDE.md.

### Step 4b — Create the Tier 0 ground-truth file

```bash
mkdir -p docs
sed "s/{{PROJECT_NAME}}/<PROJECT_NAME>/g" \
  .claude/templates/PROJECT_FACTS.md.template > docs/PROJECT_FACTS.md
```

Seed it with any invariants already known from IMPLEMENTATION_GUIDELINES or the interview
(retired/renamed components, off-limits directories, environment gotchas) using the `/remember`
format. If none are known yet, leave it empty — `/remember` fills it over time. See
`.claude/skills/core/shared-context-protocol.md`.

---

## Step 5 — Final Output

```
✅ Project initialized: <PROJECT_NAME>

  Documents created:
    docs/BRD.md                          (N FR + N NFR + N OBJ)
    docs/IMPLEMENTATION_GUIDELINES.md    (confirmed tech stack + N components)
    docs/PROJECT_FACTS.md                (Tier 0 ground truth — add facts with /remember)

  Agents generated:
    .claude/agents/generated/            (N project-specific agents — all validated)
    agent_state/agent_registry.json

  Quality audits:
    agent_state/reconciliation/requirements_vs_brd.md    (forward + reverse check)
    agent_state/reconciliation/research_vs_brd.md        (research incorporation check)
    agent_state/init/brd_quality_audit.md                (17-dimension quality: X%)
    agent_state/init/agent_validation.md                 (N agents validated)

  Project context:
    CLAUDE.md                            (all future sessions start here)
```

**MANDATORY: Surface flagged decisions before proceeding.**

If `--auto` mode was used and `agent_state/autonomous/decisions.md` exists:

```
⚠️  DECISIONS REQUIRING REVIEW:

| # | Confidence | Question | Auto-Answer | Risk if Wrong |
|---|-----------|----------|------------|---------------|
| 1 | LOW-MEDIUM | [question] | [answer] | [risk] |
| 2 | LOW-MEDIUM | [question] | [answer] | [risk] |

  INFRASTRUCTURE DECISIONS (observability, security, data) cannot be auto-deferred.
  If any infrastructure decision is LOW-MEDIUM → surface explicitly and WAIT for user response.

  Non-infrastructure LOW-MEDIUM decisions: user may accept or override.
  All HIGH/MEDIUM decisions: auto-approved (listed in decisions.md for reference).
```

After all flagged decisions are resolved:
```
  ▶ Next: /plan --phase=1
```

---

## Notes

- `/init` is idempotent for BRD and IMPLEMENTATION_GUIDELINES — re-running asks only about changes
- Use `/init --update_agents` after changing tech stack in IMPLEMENTATION_GUIDELINES
- `./requirements/` is never modified — it is read-only input
- All generated content goes to `docs/` and `.claude/agents/generated/`
- To handle new feature requests after `/init`: use `product_manager` agent to evaluate the change, update `docs/BRD.md`, then re-run `/plan` for the affected phase
- Agents generated by `agent_factory` during Step 3 are required by `/develop`. Run `/init` before running `/plan` or `/develop` on a new project
