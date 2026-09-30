# Agent Frontmatter Schema

All agent files use YAML frontmatter (delimited by `---`) to declare metadata. This document defines all valid fields, their types, and usage patterns.

---

## Required Fields

| Field | Type | Description | Example |
|-------|------|-------------|---------|
| `name` | `string` | Unique snake_case identifier for the agent | `brd_agent`, `code_reviewer_I` |
| `description` | `string` | What the agent produces **and when to use it** - Claude Code routes delegation on this text | `"First-pass code review for idioms and naming. Use in the /develop review wave before code_reviewer_II."` |
| `model` | `enum` | Model to use. Fleet default is `opus` (Claude Opus 5.5); tune cost and speed with `effort`, not smaller models | `opus` |
| `effort` | `enum` | Thinking effort (Opus 5.5 defaults to `medium` when unset): `high` for reviewers, verifiers, security and implementation; `medium` for writers and planners; `low` for mechanical runners | `high` |
| `category` | `enum` | Functional category for grouping | See category values below |

### Valid `model` Values

| Value | When to Use |
|-------|-------------|
| `opus` | Every agent (Claude Opus 5.5). Depth and cost are tuned with `effort`, not by switching to a smaller model - see `~/.claude/skills/core/model-routing.md` |

### Valid `category` Values

| Value | Description |
|-------|-------------|
| `requirements` | BRD creation, requirement analysis, interviewing |
| `planning` | Phase planning, spec writing, spec verification |
| `design` | Architecture diagrams, UX wireframes, ADRs |
| `development` | Code implementation (backend, API, DB, migrations) |
| `testing` | Unit, integration, e2e, acceptance, performance, system, manual tests |
| `review` | Code review, security review, design quality review, tenant isolation |
| `quality` | Auditing, optimization, reconciliation |
| `decision` | Debate team (moderator, researcher, advocate, arbitrator) |
| `documentation` | API docs, demo scripts, README |
| `infrastructure` | Deployment, CI/CD, observability |
| `setup` | One-time project initialization (agent_factory) |
| `security` | Dependency scanning, vulnerability detection |
| `audit` | Pre-implementation auditing (UI audit, backend audit) |

---

## Optional Fields

| Field | Type | Description | Example |
|-------|------|-------------|---------|
| `invoked_by` | `string` | Which command or agent triggers this agent | `/init`, `/plan`, `brd_agent`, `debate_moderator` |
| `auto_spawn` | `boolean` | Whether the agent is automatically spawned by its parent | `true` |
| `subagents` | `string[]` | List of agents this orchestrator spawns | `[c4_diagram_agent, sequence_diagram_agent]` |

---

## Input/Output Fields

### `input`

Declares what data the agent reads. Has two sub-keys:

```yaml
input:
  required:
    - type: <input_type>        # What kind of data (brd, guidelines, specs, etc.)
      path: <file_or_dir>       # Where to read it from
      description: <string>     # Why this input is needed (optional)
      load: sections_only       # Partial load strategy (optional)
      sections: [<list>]        # Which sections to load (optional, used with load)
  optional:
    - type: <input_type>
      path: <file_or_dir>
      description: <string>
```

**Common input types:** `brd`, `guidelines`, `specs`, `phase_plan`, `phase_context`, `phase_manifest`, `prev_manifest`, `requirements_folder`, `existing_brd`, `change_request`, `review_I`, `skill_pack`, `wireframes`, `demo_script`, `test_data`, `unit_test_results`, `integration_test_results`, `e2e_test_results`, `registry`, `analysis`, `raw_requirements`, `handler_files`, `service_files`, `assigned_option`, `all_arguments`, `debate_request`, `research`, `data_contracts`, `openapi`, `database_design`

### `output`

Declares what the agent produces:

```yaml
output:
  primary: <file_or_dir>        # Main output artifact
  artifacts:                     # Additional outputs
    - <path>                     # Simple path form
    - path: <path>               # Object form with optional description
      description: <string>
```

---

## Dependency Fields

### `dependencies`

Declares ordering relationships with other agents:

```yaml
dependencies:
  upstream: [agent_a, agent_b]     # Agents that must run BEFORE this one
  downstream: [agent_c, agent_d]   # Agents that run AFTER this one
  runs_after: [agent_e]            # Soft ordering (used by reconcilers)
```

| Sub-field | Description |
|-----------|-------------|
| `upstream` | Hard dependency: these agents must complete before this one starts |
| `downstream` | **Derived — never hand-edit.** `.claude/agents/_sync-deps.py` rewrites it as the exact inverse of every other agent's `upstream` ∪ `runs_after`. `tests/dependency-graph.test.sh` fails when it drifts. |
| `runs_after` | Soft ordering: preferred but not strictly enforced |

### `skill_packs`

List of skill pack file paths this agent loads for domain knowledge:

```yaml
skill_packs:
  - "~/.claude/skills/languages/{{LANG}}.md"
  - "~/.claude/skills/core/security-owasp.md"
```

Paths may contain `{{TEMPLATE_VARS}}` that are resolved at runtime from `agent_registry.json`.

---

## Quality Gate Fields

### `quality_gates`

Boolean flags declaring what must be true for the agent's output to pass:

```yaml
quality_gates:
  requirements_complete: true
  all_gaps_resolved_or_documented: true
  traceability_matrix_generated: true
```

Gate keys are free-form strings meaningful to the specific agent. Values are always `true` (the gate must be verified).

---

## Agent Patterns

### Pattern 1: Orchestrator

Spawns subagents in parallel, assembles results. Lightweight coordinator.

```yaml
---
name: architecture_orchestrator
description: Spawns parallel architecture subagents
model: opus
category: design
subagents: [c4_diagram_agent, sequence_diagram_agent, deployment_diagram_agent, adr_agent]
---
```

**Characteristics:**
- Has `subagents` field listing child agents
- Does not produce artifacts directly (delegates to subagents)
- Uses `opus` model for coordination decisions

**Examples:** `architecture_orchestrator`, `debate_moderator`, `e2e_orchestrator`

### Pattern 2: Subagent

Invoked by an orchestrator or parent agent. Not invoked directly by commands.

```yaml
---
name: debate_researcher
description: Gathers evidence FOR a specific option
model: sonnet
category: decision
invoked_by: debate_moderator
---
```

**Characteristics:**
- Has `invoked_by` pointing to parent agent (not a command)
- Input comes from parent agent, not from the filesystem directly
- Output consumed by parent or sibling agents

**Examples:** `brd_analyzer`, `brd_writer`, `brd_interviewer`, `wireframe_generator`, `debate_researcher`, `debate_advocate`, `debate_arbitrator`, `c4_diagram_agent`, `sequence_diagram_agent`, `deployment_diagram_agent`, `adr_agent`

### Pattern 3: Standalone (Pipeline Agent)

Invoked by pipeline commands, operates independently.

```yaml
---
name: code_reviewer_I
description: Reviews code for style, idioms, naming
model: sonnet
category: review
input:
  required:
    - type: guidelines
      path: docs/IMPLEMENTATION_GUIDELINES.md
output:
  primary: agent_state/phases/{{PHASE}}/reports/code_review_I.md
dependencies:
  upstream: [backend_developer, api_developer]
  downstream: [code_reviewer_II]
---
```

**Characteristics:**
- No `invoked_by` (triggered by pipeline commands like `/develop`, `/plan`, `/review`)
- Reads from and writes to the filesystem
- Has explicit `dependencies` for pipeline ordering
- Most agents follow this pattern

**Examples:** `brd_agent`, `project_planner`, `spec_writer`, `backend_developer`, `code_reviewer_I`, `code_reviewer_II`, `security_reviewer`, `acceptance_test_agent`

### Pattern 4: Generated (Template)

Lives in `~/.claude/agents/templates/` with a `.tmpl` extension, which keeps Claude Code from loading unfilled templates as live agents. `agent_factory` instantiates them into the project's `.claude/agents/generated/` as `.md` files with project-specific values.

```yaml
---
name: backend_developer
description: Implements backend services
model: sonnet
category: development
---
```

**Characteristics:**
- File extension is `.tmpl` (not `.md`, so the template itself is never loaded as an agent)
- Contains `{{TEMPLATE_VARS}}` resolved at project init time
- Created by `agent_factory` agent
- Moved to active agents directory after generation

**Examples:** `backend_developer.tmpl`, `api_developer.tmpl`, `database_agent.tmpl`, `migration_agent.tmpl`

---

## Frontmatter Validation Rules

1. `name` must be unique across all agents (core + generated)
2. `name` must match the filename (e.g., `name: brd_agent` in `brd_agent.md`)
3. `model` must be one of: `opus`, `sonnet`, `haiku`
4. `category` must be one of the values listed above
5. If `subagents` is declared, each listed agent must exist as a file
6. If `invoked_by` references an agent, that agent should list this one in `subagents` or `downstream`
7. `upstream`/`runs_after` are authored; `downstream` is generated by `_sync-deps.py`, so reciprocity always holds. A hard `upstream` must point to an agent that `/develop-orchestrator` runs in an EARLIER wave (same-wave → use `runs_after`).
8. All paths in `input` and `output` should use forward slashes and may contain `{{PHASE}}` or `{{LANG}}` template variables

---

## Body Structure Requirements (MANDATORY sections)

Frontmatter is not enough — the prompt BODY must contain these sections. This is enforced by
`/health` 5.5e and reviewed by the agent-quality pass. Shared block text lives in
`~/.claude/skills/core/agent-common.md` (copy verbatim; don't paraphrase the invariant lines).

| Section | Rule |
|---|---|
| `## Role` | One-paragraph mission statement. |
| `## Required Reading` | MUST use this exact heading and MUST begin with `docs/PROJECT_FACTS.md` (item 0) then `docs/DECISIONS.md` (item 0b) — see agent-common Block 1. Ground truth is read FIRST, always. |
| `## Output` | If the agent writes a report, MUST include a fenced template showing the report's shape (agent-common Block 5). A prose-only output description is non-conformant. |
| Severity model | Any agent that emits findings MUST use the Unified Severity Model BLOCKING/WARNING/INFO and end with a `BLOCKING:N WARNING:N INFO:N` count (agent-common Block 4). |
| `## Definition of Done` | MANDATORY for every agent. Self-verify output path, real (non-stub) content, cited claims, real counts, explicit "nothing found" handling, and the `execution.jsonl` completion line (agent-common Block 2). |
| Lessons write-back | Agents that can learn something reusable append a tagged lesson to `agent_state/phases/{{PHASE}}/lessons.md` (agent-common Block 3). Not filler — only when there's a real lesson. |

**Why these are mandatory:** an agent without a Definition-of-Done can silently no-op and still leave
a present-but-empty report that passes a file-existence gate; an agent that never writes lessons
starves the Tier 1 memory system; an inconsistent Required-Reading heading breaks the ground-truth
invariant check. All three were real gaps found in the fleet audit.

## Generated blocks (do not hand-edit)

`_sync-contract.sh` maintains two marked blocks in every agent, just above `## Definition of Done`:

- **reference-packs** - rendered from `skill_packs:`. Claude Code ignores that frontmatter key, so this block is what makes an agent read its packs. Pack paths are user-level: `~/.claude/skills/...` (a project-relative `.claude/skills/...` does not resolve inside projects).
- **operating-contract** - copied from Block 0 of `~/.claude/skills/core/agent-common.md`: unattended operation (subagents cannot ask the user; interviewers return `NEEDS_INPUT`), scope, evidence, correction only on external signals, and the final-message format the orchestrator relies on.

After adding an agent or editing either source, run `~/.claude/agents/_sync-contract.sh`.
