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

**Read discipline:** `brd_agent` and `impl_guidelines_agent` run in parallel — each reads only its own input files. They do NOT read each other's outputs mid-run.

**Agent result discipline:** Each agent returns a 3-line summary to the parent. Full BRD and IMPLEMENTATION_GUIDELINES content stays in files — never echoed back.

**Per-step targets:**
| Step | Target input tokens |
|------|---------------------|
| Step 1+2 BRD + IMPL | ~20K (requirements/ files only) |
| Step 2b Reconcile | ~15K (requirements index + BRD summary) |
| Step 3 Agent factory | ~10K (IMPL §Tech Stack + §Components only) |

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

## Step 2b — Reconciliation Point A: Requirements ↔ BRD

**Agent:** `requirements_brd_reconciler` (runs immediately after Step 1+2 complete)

Validates both directions:
- **Forward:** features/constraints in `./requirements/` that didn't make it into `docs/BRD.md`
- **Reverse:** requirements in `docs/BRD.md` with no source in `./requirements/` (invented)

Output: `agent_state/reconciliation/requirements_vs_brd.md`

If MISSING or INVENTED items found: surface to user before continuing.
User decides: update BRD, or accept with rationale. Does not auto-proceed if gaps exist.

---

## Step 3 — Generate Project-Specific Agents

**Agent:** `agent_factory`
**Input:** `docs/IMPLEMENTATION_GUIDELINES.md`
**Output:** `.claude/agents/generated/*.md`, `agent_state/agent_registry.json`

Reads Section 1 (Tech Stack) and Section 3 (Component Inventory) from the confirmed IMPLEMENTATION_GUIDELINES. Populates templates from `.claude/agents/templates/` and writes generated agents to `.claude/agents/generated/`.

See `agent_factory.md` for full template-population logic.

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

---

## Step 5 — Final Output

```
✅ Project initialized: <PROJECT_NAME>

  Documents created:
    docs/BRD.md                          (N requirements)
    docs/IMPLEMENTATION_GUIDELINES.md    (confirmed tech stack + components)

  Agents generated:
    .claude/agents/generated/            (N project-specific agents)
    agent_state/agent_registry.json

  Project context:
    CLAUDE.md                            (all future sessions start here)

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
