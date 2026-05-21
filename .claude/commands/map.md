---
command: map
description: "Analyze codebase with parallel mapper agents. Produces persistent knowledge base in agent_state/codebase/ that all agents can reference."
arguments:
  - name: focus
    required: false
    description: "Focus area: 'tech', 'architecture', 'quality', 'concerns', 'strategy', or 'all' (default: 'all')"
  - name: incremental
    required: false
    default: false
    description: "Only re-map files changed since last mapping (uses git diff)"
  - name: phase
    required: false
    description: "Scope mapping to components relevant to a specific phase"
---

# /map — Codebase Knowledge Base Generator

Produces a persistent, reusable codebase knowledge base in `agent_state/codebase/` by spawning parallel `codebase_mapper` agents. The knowledge base survives context resets and informs all downstream agents (`/plan`, `/develop`, `/review`, `/diagnose`).

**Use when:** Starting a new project, onboarding to an existing codebase, or after significant refactoring. The output replaces "read the whole codebase from scratch" in every session.

**Prerequisites:** A codebase must exist (at minimum: source files, a package manager lockfile, or a build config). No BRD or IMPLEMENTATION_GUIDELINES required — `/map` discovers what exists.

---

## Session Context Budget

> Full protocol: `.claude/skills/core/context-budget-protocol.md`. Per-step token targets below are specific to this command.

**Agent result discipline:** Every `codebase_mapper` agent returns a 3-line summary to the parent. Full analysis content is in files — never echoed back to the conversation.

**Read discipline:** Each mapper agent reads files relevant to its focus area only. No agent reads the entire codebase. Use Glob for discovery, targeted Read for analysis.

**Per-step targets:**
| Step | Target input tokens |
|------|---------------------|
| Step 0 Orient | ~3K (check existing mapping, git diff, phase plan) |
| Step 1 Per mapper agent | ~15K each (Glob discovery + targeted file reads) |
| Step 2 Synthesize | ~10K (read 4 focus documents, write summary) |
| Step 3 Output | ~1K (format and print summary) |

**Agent return protocol:** Every mapper agent returns 3 lines to the parent:
```
codebase_mapper ({{FOCUS}}) — complete → wrote agent_state/codebase/{{FOCUS}}.md
   Covered: <N> files analyzed, <N> patterns found
   Issues: none | <N> concerns identified
```

---

## Pipeline Anti-Rationalization Guard

**One rule:** Never skip a focus area, shortcut the analysis, or accept surface-level findings — even if it "seems obvious." If you're tempted to skip, that's exactly when the step matters most. The table below lists specific temptations and their correct responses.

Before skipping ANY step or accepting incomplete mapper output, review this table.

| Your Internal Reasoning | Correct Response |
|---|---|
| "The tech stack is obvious from package.json / go.mod" | Read the ACTUAL imports used in source files. Declared dependencies != used dependencies. |
| "The architecture is just MVC, no need to analyze" | Map the ACTUAL module boundaries and import graph. "MVC" means nothing without specific layer violations documented. |
| "Test coverage is fine, most files have tests" | Count the ACTUAL files with vs without test counterparts. "Most" is not a number. |
| "Security concerns are for the security reviewer" | `/map` identifies STRUCTURAL concerns (missing validation patterns, no auth middleware). Security reviewer does ADVERSARIAL testing. |
| "This codebase is small, I can skip the parallel agents" | Run all 4 focus areas regardless of size. Small codebases have the same categories of concerns. |
| "The previous mapping is recent enough" | If `--incremental` was not specified, run a full mapping. Stale knowledge bases cause downstream errors. |
| "I'll just list the files and directories" | Listing is not analysis. Every finding must include WHAT the pattern is, WHERE it occurs (file:line), and WHY it matters. |
| "This is a framework project, not a deployable app" | Frameworks have tech stacks, architecture patterns, quality concerns, and security considerations. Map them. |

---

## Step 0 — Orient

### Check existing mapping
```bash
CODEBASE_DIR="agent_state/codebase"
HAS_PREVIOUS=$([ -d "$CODEBASE_DIR" ] && [ -f "$CODEBASE_DIR/.last-mapped" ] && echo true || echo false)

if [ "$HAS_PREVIOUS" = "true" ]; then
  LAST_MAPPED=$(cat "$CODEBASE_DIR/.last-mapped")
  LAST_SHA=$(head -1 "$CODEBASE_DIR/.last-mapped" | grep -oP 'sha:\K.*' || echo "unknown")
  echo "Previous mapping found: $LAST_MAPPED"
else
  echo "No previous mapping — full scan required"
fi
```

### Handle --incremental
If `--incremental` AND previous mapping exists:
1. Get the git SHA from `.last-mapped`
2. Run `git diff --name-only ${LAST_SHA}...HEAD` to get changed files
3. If no files changed: print `No changes since last mapping (${LAST_SHA}). Knowledge base is current.` and **STOP**
4. If files changed: pass the changed file list to each mapper agent as scope constraint

If `--incremental` AND no previous mapping exists:
- Warn: `No previous mapping found — running full scan instead of incremental`
- Proceed with full scan

### Handle --phase
If `--phase` is provided:
1. Read `docs/design/phases/${ARG_PHASE}/PHASE_PLAN.md` to get components in scope
2. Read `docs/IMPLEMENTATION_GUIDELINES.md` §Component Inventory to get file paths for those components
3. Pass the component file paths as scope constraint to each mapper agent

### Create output directory
```bash
mkdir -p agent_state/codebase
```

### Determine focus areas
```bash
FOCUS="${ARG_FOCUS:-all}"
if [ "$FOCUS" = "all" ]; then
  FOCUS_AREAS="tech architecture quality concerns strategy"
else
  FOCUS_AREAS="$FOCUS"
fi
```

---

## Step 1 — Parallel Codebase Analysis (codebase_mapper agents)

Spawn one `codebase_mapper` agent per focus area. All agents run in **parallel**.

**Agent:** `codebase_mapper` (one instance per focus area)

Each agent receives:
- `focus_area` — which analysis to perform (tech | architecture | quality | concerns)
- `scope` — full codebase, changed files (incremental), or phase components
- `previous_mapping` — path to existing focus document (if incremental, for merge)

### Focus: tech → `agent_state/codebase/tech-stack.md`

The `codebase_mapper` with `focus=tech` analyzes:
- Languages detected (by file extension counts and actual usage)
- Framework identification (from imports, not just package manifests)
- Build tools and configuration files
- Package managers, dependency counts, and lockfile presence
- Runtime requirements (Docker, Node version, Go version, Python version)
- Database technologies (from connection strings, ORM configs, migration files)
- External service integrations (from import patterns and config)

### Focus: architecture → `agent_state/codebase/architecture.md`

The `codebase_mapper` with `focus=architecture` analyzes:
- Directory structure and organizational pattern (MVC, DDD, hexagonal, monorepo, etc.)
- Module/package boundaries and the import dependency graph
- API surface — routes, handlers, middleware chain
- Data models and schema definitions
- Service layer structure and dependency injection patterns
- Cross-cutting concerns — how auth, logging, error handling, and config are implemented
- Entry points and initialization flow

### Focus: quality → `agent_state/codebase/quality.md`

The `codebase_mapper` with `focus=quality` analyzes:
- Test coverage estimate (files with test counterparts vs without)
- Test framework and patterns in use
- Code consistency — naming conventions, file structure patterns, error handling uniformity
- Documentation coverage — README, inline comments, API docs
- Technical debt indicators — TODO/FIXME/HACK counts with locations
- Code duplication indicators — similar patterns repeated across files
- Dependency health — outdated packages, known CVE indicators

### Focus: concerns → `agent_state/codebase/concerns.md`

The `codebase_mapper` with `focus=concerns` analyzes:
- **Security:** hardcoded secrets, missing input validation patterns, auth gaps, SQL injection vectors
- **Performance:** N+1 query patterns, missing indexes, unbounded list operations, no pagination
- **Reliability:** missing error handling, no retry patterns, no circuit breakers, no graceful shutdown
- **Maintainability:** tight coupling (god objects, circular dependencies), missing interfaces, large functions (>100 lines)

Each concern is classified: **HIGH** (likely to cause issues), **MEDIUM** (should address), **LOW** (improvement opportunity).

### Focus: strategy → `agent_state/codebase/strategy.md`

The `codebase_mapper` with `focus=strategy` provides a CTO-level strategic assessment:
- Scaling readiness — 10x/100x capacity assessment per layer (DB, compute, API, vendors, state)
- Build vs buy ledger — every significant dependency evaluated for lock-in risk and switch cost
- Engineering velocity indicators — build times, test times, deploy steps, onboarding complexity, contribution safety
- Cost scaling patterns — infrastructure spend trajectory as users/data grow
- Architecture scorecard — 1-5 ratings across 7 dimensions (modularity, testability, deployability, scalability, security, observability, DX)
- Strategic risk matrix — top risks ranked by likelihood x impact with mitigation timeline
- Investment priorities — top 5 engineering moves with business ROI

---

## Step 2 — Synthesize

**Runs after:** All `codebase_mapper` agents complete (all 4 focus documents written)

### Read all focus documents
Read each produced document:
- `agent_state/codebase/tech-stack.md`
- `agent_state/codebase/architecture.md`
- `agent_state/codebase/quality.md`
- `agent_state/codebase/concerns.md`
- `agent_state/codebase/strategy.md`

### Write SUMMARY.md

Write `agent_state/codebase/SUMMARY.md` — a 1-page overview with key stats that any agent can load for quick orientation:

```markdown
# Codebase Summary
Generated: {{TIMESTAMP}}
Git SHA: {{GIT_SHA}}

## Tech Stack
- **Primary language:** <language> <version>
- **Framework:** <framework> <version>
- **Database:** <db technology>
- **Package manager:** <manager> (<N> dependencies)
- **Build tool:** <tool>

## Architecture
- **Pattern:** <organizational pattern>
- **Modules:** <N> top-level packages/modules
- **API routes:** <N> endpoints across <N> route groups
- **Data models:** <N> models/entities
- **Services:** <N> service-layer components

## Quality
- **Test coverage:** <N>% of implementation files have test counterparts
- **Test framework:** <framework>
- **Technical debt:** <N> TODOs, <N> FIXMEs, <N> HACKs
- **Documentation:** <assessment — good/partial/minimal>

## Top Concerns
1. **[HIGH]** <most critical concern — 1 line>
2. **[HIGH]** <second most critical — 1 line>
3. **[MEDIUM]** <notable concern — 1 line>
(up to 5 top concerns)

## Quick Reference
| Document | Path | Key Finding |
|----------|------|-------------|
| Tech stack | agent_state/codebase/tech-stack.md | <1-line summary> |
| Architecture | agent_state/codebase/architecture.md | <1-line summary> |
| Quality | agent_state/codebase/quality.md | <1-line summary> |
| Concerns | agent_state/codebase/concerns.md | <1-line summary> |
```

### Write .last-mapped timestamp

Write `agent_state/codebase/.last-mapped`:
```
sha:{{GIT_SHA}}
timestamp:{{ISO_8601_TIMESTAMP}}
focus_areas:{{COMMA_SEPARATED_FOCUS_AREAS}}
mode:{{full|incremental|phase-scoped}}
files_analyzed:{{COUNT}}
```

### Handle incremental merge

If `--incremental`:
1. For each focus document, read the EXISTING document first
2. Identify sections that correspond to changed files
3. Update ONLY those sections with new findings
4. Preserve findings for unchanged files
5. Update the "Last Updated" timestamp and git SHA at the top of each document
6. Append a `## Change Log` entry at the bottom:
   ```markdown
   ## Change Log
   - {{TIMESTAMP}} (incremental) — Updated N sections based on M changed files since {{PREVIOUS_SHA}}
   ```

---

## Step 3 — Output

Print the mapping summary:

```
✅ Codebase mapped → agent_state/codebase/

  Tech stack:    <language> / <framework> / <db>
  Components:    <N> modules, <N> routes, <N> models
  Test coverage: <N>% files with tests
  Concerns:      <N> HIGH, <N> MEDIUM, <N> LOW

  Files:
    agent_state/codebase/SUMMARY.md
    agent_state/codebase/tech-stack.md
    agent_state/codebase/architecture.md
    agent_state/codebase/quality.md
    agent_state/codebase/concerns.md
    agent_state/codebase/strategy.md
```

If `--incremental`:
```
✅ Codebase mapping updated (incremental) → agent_state/codebase/

  Changed files: <N> (since <PREVIOUS_SHA>)
  Updated:       <list of focus documents that changed>
  Unchanged:     <list of focus documents with no updates>

  Files:
    agent_state/codebase/SUMMARY.md (updated)
    agent_state/codebase/tech-stack.md
    agent_state/codebase/architecture.md
    agent_state/codebase/quality.md
    agent_state/codebase/concerns.md
```

If `--phase`:
```
✅ Codebase mapped (phase-scoped: Phase <N>) → agent_state/codebase/

  Scope:         <N> components from Phase <N>
  Tech stack:    <language> / <framework> / <db>
  Components:    <N> modules, <N> routes, <N> models
  Test coverage: <N>% files with tests
  Concerns:      <N> HIGH, <N> MEDIUM, <N> LOW

  Files:
    agent_state/codebase/SUMMARY.md
    agent_state/codebase/tech-stack.md
    agent_state/codebase/architecture.md
    agent_state/codebase/quality.md
    agent_state/codebase/concerns.md
```

---

## Rules

- `/map` is **read-only** — it analyzes the codebase but never modifies source files
- Every finding must include **file:line references** — "the codebase uses MVC" without evidence is not a finding
- The knowledge base is **append-friendly** — incremental mode updates sections, never deletes previous findings unless the underlying code was deleted
- `agent_state/codebase/SUMMARY.md` is the **entry point** for all downstream agents — keep it under 2K tokens
- Focus documents can be detailed — no hard token limit, but use structured tables and avoid prose
- The `.last-mapped` file is the **single source of truth** for incremental mode — if corrupted, fall back to full scan
- All 4 focus areas run even for small codebases — the categories of analysis don't change with project size
- If a focus area finds nothing (e.g., no tests exist), the document still gets written with an explicit "No findings" section — absence of evidence IS the finding
- Do not analyze files in `node_modules/`, `vendor/`, `.git/`, `dist/`, `build/`, `__pycache__/`, or other dependency/build output directories
- Binary files, images, and generated code (protobuf output, swagger output) are noted but not analyzed for patterns
