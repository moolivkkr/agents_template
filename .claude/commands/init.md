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

Bootstraps a new project from `./requirements/`. Produces `docs/BRD.md`, `docs/IMPLEMENTATION_GUIDELINES.md`, generates project-specific agents, writes `CLAUDE.md`.

**Run once at project start. Use `/plan` to begin phase work.**

## Session Context Budget

> Full protocol: `.claude/skills/core/context-budget-protocol.md`

**Read discipline:** `brd_agent` and `impl_guidelines_agent` run in parallel — each reads only its own inputs.

**Agent result discipline:** 3-line summary to parent. Full content stays in files.

| Step | Target input tokens |
|------|---------------------|
| Step 1+2 BRD + IMPL | ~20K (requirements/ only) |
| Step 2b Reconcile | ~15K (requirements index + BRD summary) |
| Step 3 Agent factory | ~10K (IMPL §Tech Stack + §Components only) |

---

## Step 0 — Scan ./requirements/

```bash
ls -la requirements/
```

Categorize files: functional specs/user stories → `brd_agent`, `IMPLEMENTATION_GUIDELINES.md` → `impl_guidelines_agent`, API/wireframe/arch docs → both as context.

If `--update_agents`: skip to Step 3. If `--brd_only`: run Step 1 only, then stop.

---

## Step 1 + 2 — BRD and IMPLEMENTATION_GUIDELINES (PARALLEL)

### Step 1: `brd_agent`
**Input:** All `./requirements/` except IMPLEMENTATION_GUIDELINES.md | **Output:** `docs/BRD.md`

Reads requirement docs, extracts/maps to BRD sections, identifies gaps, asks targeted questions for genuine gaps only. Writes BRD with: numbered OBJ-*, FR-*, NFR-*, personas, out-of-scope, gate checklists, traceability matrix.

### Step 2: `impl_guidelines_agent`
**Input:** `./requirements/IMPLEMENTATION_GUIDELINES.md` + technical docs | **Output:** `docs/IMPLEMENTATION_GUIDELINES.md`

Evaluates for missing context (components without tech decisions, unclear architecture, missing migration tool, no local dev setup, missing design constraints). Asks targeted clarifying questions. Writes: Tech Stack table, Architecture Overview (with Mermaid), Component Inventory, Design Constraints, Local Dev Environment.

**Both agents run in parallel. Step 3 waits for BOTH.**

---

## Step 1.5 — Post-Clarification Cross-Validation

**Checks:**
1. **BRD internal:** No dangling FR↔NFR references, no contradictory constraints
2. **BRD ↔ IMPL_GUIDELINES:** Tech stack supports all NFRs, component inventory covers all FR-*, auth mechanism matches
3. **User answer consistency:** contradictions between answers given to different agents

**On contradiction:** Surface both conflicting statements, ask user to resolve (max 1 round), update affected document.

---

## Step 2b — Reconciliation Point A: Requirements ↔ BRD

**Agent:** `requirements_brd_reconciler`

Validates both directions:
- **Forward:** features in `./requirements/` not in `docs/BRD.md`
- **Reverse:** requirements in BRD with no source (invented)

Output: `agent_state/reconciliation/requirements_vs_brd.md`. MISSING/INVENTED → surface to user before continuing.

---

## Step 3 — Generate Project-Specific Agents

**Agent:** `agent_factory`
**Input:** `docs/IMPLEMENTATION_GUIDELINES.md` | **Output:** `.claude/agents/generated/*.md`, `agent_state/agent_registry.json`

Reads Tech Stack + Component Inventory, populates templates from `.claude/agents/templates/`, writes generated agents.

---

## Step 4 — Write CLAUDE.md

Write project root `CLAUDE.md` with: project summary (from BRD), tech stack table, key documents table, active agents list, phase gate state, local dev setup, common tasks.

---

## Step 5 — Final Output

```
✅ Project initialized: <PROJECT_NAME>
  Documents: docs/BRD.md (N requirements), docs/IMPLEMENTATION_GUIDELINES.md
  Agents: .claude/agents/generated/ (N agents), agent_state/agent_registry.json
  Context: CLAUDE.md
  ▶ Next: /plan --phase=1
```

---

## Notes

- `/init` is idempotent — re-running asks only about changes
- `--update_agents` after tech stack changes
- `./requirements/` is read-only input, never modified
- Generated content → `docs/` and `.claude/agents/generated/`
- New feature requests after `/init` → `product_manager` agent → update BRD → re-run `/plan`
- Agents from Step 3 are required by `/develop`
