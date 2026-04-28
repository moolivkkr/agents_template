# startup-agents

A reusable AI-agent framework for building software products end-to-end with Claude Code. Drop in your requirements, run three commands, get a production-ready application with tests, code reviews, and acceptance validation at every phase.

---

## How it works

You provide requirements. The agents do the rest — from turning a pitch deck into a structured BRD, through implementation waves, to final acceptance testing against every user persona.

```
requirements/                  ← your docs go here
    ├── feature-spec.md        ← user stories, PRD, pitch deck
    ├── IMPLEMENTATION_GUIDELINES.md  ← optional: tech stack decisions
    └── test-data/             ← optional: seed data per phase

/startup/init  →  docs/BRD.md + docs/IMPLEMENTATION_GUIDELINES.md
/startup/plan  →  docs/design/phases/1/specs/  (TRDs + wireframes)
/startup/develop  →  implement + test + review + gate
(repeat plan/develop per phase)
/startup/accept  →  full-product validation against all BRD personas
```

---

## Quick start

### 1. Install (one time)

```bash
git clone <this-repo> ~/development/startup-agents
cd ~/development/startup-agents
bash install.sh
```

This installs commands, agents, and skill packs into `~/.claude/` so they're available globally in every project.

### 2. Start a new project

```bash
bash ~/development/startup-agents/new-project.sh my-app ~/development
cd ~/development/my-app
```

This creates the project scaffold:
```
my-app/
├── requirements/
│   └── IMPLEMENTATION_GUIDELINES.md   ← editable template
├── docs/
├── agent_state/
└── .claude/agents/generated/
```

### 3. Add your requirements

Drop any combination of these into `requirements/`:
- Feature spec or PRD (Markdown, PDF, text)
- User stories
- Pitch deck content
- API contracts or architecture notes
- Optionally: fill in `IMPLEMENTATION_GUIDELINES.md` with your tech choices

The agents work with whatever you have. If something is missing, they'll ask.

### 4. Run the SDLC

```
/startup/init       ← run once per project
/startup/plan       ← run once per phase (auto-detects next phase)
/startup/develop    ← run once per phase (auto-detects current phase)
/startup/accept     ← run once after all phases complete
```

---

## Commands

| Command | What it does |
|---------|-------------|
| `/startup/init` | Reads `requirements/`, creates `docs/BRD.md` + `docs/IMPLEMENTATION_GUIDELINES.md`, generates project-specific agents, writes `CLAUDE.md` |
| `/startup/plan` | Creates technical specs (TRDs) and wireframes for the next phase |
| `/startup/develop` | Implements the current phase end-to-end: audit → code → tests → review → gate |
| `/startup/accept` | Runs full-product acceptance tests after all phases complete |
| `/startup/test` | Runs tests standalone (unit / integration / e2e / acceptance / performance / system) |
| `/startup/review` | Standalone code review: style + architecture + security |
| `/startup/deploy` | Builds, migrates, and deploys to local / staging / prod |
| `/startup/status` | Shows phase progress, BRD coverage, open issues, and next recommended action |

### Command arguments

**`/startup/init`**
```
--update_agents   Re-generate project agents only (use after tech stack changes)
--brd_only        Regenerate BRD only
```

**`/startup/plan`**
```
--phase=N         Override phase number (default: auto-detect next unplanned)
--ui_only         Regenerate wireframes only
--verify_only     Verify existing specs against BRD — no new generation
```

**`/startup/develop`**
```
--phase=N         Override phase number (default: auto-detect from gate state)
--audit_only      Gap report only — no implementation changes
--test_only       Run tests only — no implementation changes
```

**`/startup/test`**
```
--phase=N         Target a specific phase
--unit            Unit tests only
--integration     Integration tests only
--e2e             E2E tests only
--workflow=NAME   Run a specific e2e workflow
--acceptance      Acceptance tests only
--persona=NAME    Acceptance for a specific persona
--performance     Load tests against NFR-PERF-* targets
--system          Cross-phase smoke tests
--manual          Generate manual QA test plan
```

**`/startup/deploy`**
```
--target=local|staging|prod   (default: local)
--dry_run                     Show plan without deploying
```

---

## The SDLC pipeline

`/startup/develop` runs a 7-step pipeline per phase:

```
Step 0  Orient          Detect phase, load previous manifest, start infra
Step 1  Audit           Gap report: what's missing vs what the specs require
Step 2  Implement       Wave-based parallel execution (DB → backend → UI)
Step 3  Test            Unit → Integration → E2E (if workflow unlocked)
Step 3d Reconcile C     Spec ↔ Implementation (bidirectional)
Step 3e Reconcile D     Spec ↔ Tests (bidirectional)
Step 4  Review          Style review → Architecture review + Security (parallel)
Step 5  Acceptance      Use case + persona level validation with seed data
Step 6  Gate            9 conditions must pass — writes gate.passed + manifest.json
Step 6b Document        API docs + README updates (non-blocking, parallel)
Step 7  Report          Summary of what was built, test results, gate status
```

### Phase gate — all 9 must pass

```
✅ Unit tests              all passing
✅ Integration tests       all passing
✅ E2E tests               all passing (only if phase unlocks a workflow)
✅ Reconciliation C        no MISSING implementations (spec → impl)
✅ Reconciliation D        no HIGH-priority untested behaviors (spec → tests)
✅ Code review I           no BLOCKING style issues
✅ Code review II          no architecture violations
✅ Security review         no HIGH severity findings
✅ Acceptance tests        all in-scope use cases pass
```

If any condition fails: the gate does not write. The blocker is surfaced with the specific file, finding, and how to fix it.

### Bidirectional reconciliation

At four transition points, a reconciler validates in both directions:

| Point | Agent | Checks |
|-------|-------|--------|
| A: Requirements → BRD | `requirements_brd_reconciler` | Nothing dropped, nothing invented |
| B: BRD → Specs | `brd_spec_reconciler` | Every FR-* has a spec; no gold-plating |
| C: Specs → Implementation | `spec_impl_reconciler` | Every spec behavior is built; no unspecced code |
| D: Specs → Tests | `spec_test_reconciler` | Every edge case has a test; no tests for non-spec behavior |

Forward gaps = blockers. Reverse gaps (invented/unspecced) = flagged for human review.

### Implementation waves

Each phase runs in parallel waves:

```
Wave 1  database_agent + migration_agent
Wave 2  backend_developer + api_developer
Wave 3  ui_developer  (UI phases only)
Wave 4  unit_test_agent + integration_test_agent
```

Waves are sequential. Tasks within each wave run in parallel.

---

## Project structure

```
my-project/
│
├── requirements/                      ← READ ONLY — your source documents
│   ├── *.md / *.pdf / *.txt           ← feature specs, user stories, pitch deck
│   ├── IMPLEMENTATION_GUIDELINES.md   ← optional: pre-written tech decisions
│   └── test-data/
│       ├── phase-1.yaml               ← optional: seed data for phase 1 acceptance
│       ├── phase-2.yaml               ← optional: seed data for phase 2 acceptance
│       └── global.yaml                ← optional: seed data for /accept
│
├── docs/                              ← GENERATED by agents
│   ├── BRD.md                         ← numbered requirements (FR-*, NFR-*, OBJ-*)
│   ├── IMPLEMENTATION_GUIDELINES.md   ← confirmed tech stack + components
│   ├── traceability-matrix.md         ← requirement → phase → test coverage
│   ├── adr/                           ← Architecture Decision Records
│   └── design/
│       └── phases/
│           └── N/
│               ├── PHASE_PLAN.md      ← scope, exit criteria, wave structure
│               ├── VERIFICATION_REPORT.md
│               ├── INDEX.md
│               └── specs/
│                   ├── *.md           ← TRDs (technical reference docs)
│                   └── *.wireframe.md ← UI wireframes (UI phases only)
│
├── agent_state/                       ← GENERATED runtime state
│   ├── agent_registry.json            ← active agents + tech profile
│   ├── reconciliation/
│   │   ├── requirements_vs_brd.md
│   │   └── phase-N/
│   │       ├── brd_vs_specs.md
│   │       ├── specs_vs_impl.md
│   │       └── specs_vs_tests.md
│   ├── e2e/
│   │   └── results.md
│   └── phases/
│       └── N/
│           ├── gate.passed            ← exists = phase is complete
│           ├── manifest.json          ← handshake consumed by phase N+1
│           ├── audit_report.md
│           ├── audit_report_ui.md     ← UI phases only
│           ├── test-data/
│           │   ├── generated-seed.yaml
│           │   └── seed-cleanup.md
│           └── reports/
│               ├── unit_tests.md
│               ├── integration_tests.md
│               ├── code_review_I.md
│               ├── code_review_II.md
│               ├── security_review.md
│               ├── acceptance_report.md
│               └── documentation_update.md
│
├── src/                               ← YOUR APPLICATION CODE (agents write here)
├── migrations/                        ← Database migrations
├── tests/                             ← Test files
│
├── CLAUDE.md                          ← Project context (written by /init)
│
└── .claude/
    └── agents/
        └── generated/                 ← Project-specific agents (written by /init)
            ├── go_backend_developer_myapp.md
            ├── go_api_developer_myapp.md
            ├── postgres_database_agent_myapp.md
            └── ...
```

---

## Agents

### Core agents (always available)

These live in `~/.claude/agents/` after install. No project setup required.

#### Requirements & Planning

| Agent | Role | Model |
|-------|------|-------|
| `brd_agent` | Reads `requirements/`, extracts and classifies requirements, interviews for gaps, produces `docs/BRD.md` | sonnet |
| `impl_guidelines_agent` | Evaluates draft IMPLEMENTATION_GUIDELINES, asks targeted clarifying questions, produces confirmed `docs/IMPLEMENTATION_GUIDELINES.md` | sonnet |
| `project_planner` | Assigns FR-* requirements to phases, defines exit criteria and implementation waves | sonnet |
| `spec_writer` | Generates TRD for one component/flow — interface contracts, data model, 10+ edge cases, test coverage requirements | sonnet |
| `agent_factory` | Reads confirmed IMPLEMENTATION_GUIDELINES, populates agent templates, writes project-specific agents to `.claude/agents/generated/` | sonnet |
| `product_manager` | Handles change requests and BRD amendments after `/init` — invoke manually | opus |

**BRD pipeline sub-agents** (invoked internally by `brd_agent`):

| Agent | Role |
|-------|------|
| `brd_analyzer` | Extracts and classifies requirements from raw documents |
| `brd_interviewer` | Presents gap questions to user, records answers |
| `brd_writer` | Produces the final structured BRD from extracted + confirmed requirements |

#### Audit

| Agent | Role | Trigger |
|-------|------|---------|
| `backend_audit_agent` | Gap analysis for backend codebase vs phase specs | Every phase |
| `ui_audit_agent` | Gap analysis for UI layer vs wireframes, API bindings, state handling | UI phases only |

#### Specification & Design

| Agent | Role | Model |
|-------|------|-------|
| `ux_designer` | Produces wireframe specs — layout, components, API bindings, interactions | opus |
| `wireframe_generator` | Initial wireframe scaffolding (invoked by `ux_designer`) | sonnet |
| `design_quality_reviewer` | Validates wireframes: no TBD bindings, loading/error/empty states, accessibility | sonnet |
| `spec_verifier` | Confirms all FR-* in scope have spec coverage; all cited IDs exist in BRD | sonnet |
| `adr_agent` | Writes Architecture Decision Records for significant design choices | sonnet |

#### Implementation (generated per project)

These are created by `agent_factory` from templates during `/init`:

| Template | Generated agent | When |
|----------|----------------|------|
| `backend_developer.tmpl.md` | `{lang}_backend_developer_{project}.md` | Always |
| `api_developer.tmpl.md` | `{lang}_api_developer_{project}.md` | Always |
| `database_agent.tmpl.md` | `{db}_database_agent_{project}.md` | Always |
| `migration_agent.tmpl.md` | `{db}_migration_agent_{project}.md` | Relational/document DB |
| `unit_test_agent.tmpl.md` | `{lang}_unit_test_agent_{project}.md` | Always |
| `integration_test_agent.tmpl.md` | `{lang}_integration_test_agent_{project}.md` | Always |
| `ui_developer.tmpl.md` | `{ui}_ui_developer_{project}.md` | `frontend.enabled = true` |
| `ui_test_agent.tmpl.md` | `{ui}_ui_test_agent_{project}.md` | `frontend.enabled = true` |

Each generated agent is pre-loaded with your project's specific language, framework, ORM, test library, and design conventions.

#### Code Review

| Agent | Role | Model |
|-------|------|-------|
| `code_reviewer_I` | Style, idioms, naming, formatting — reads active language skill pack | sonnet |
| `code_reviewer_II` | Architecture, design patterns, constraint compliance | opus |
| `security_reviewer` | OWASP top 10, auth/authz, injection, secrets, data exposure | opus |

#### Testing

| Agent | Role | Model | Invoked by |
|-------|------|-------|-----------|
| `e2e_orchestrator` | Runs complete user workflow tests across full stack | sonnet | `/develop` Step 3c, `/test --e2e` |
| `acceptance_test_agent` | Use case + persona level validation with seed data | opus | `/develop` Step 5, `/test --acceptance`, `/accept` |
| `performance_agent` | Load tests vs NFR-PERF-* targets | sonnet | `/test --performance` |
| `system_test_agent` | Cross-phase smoke tests, data flow validation | sonnet | `/test --system` |
| `manual_test_agent` | Generates structured manual QA test plan | sonnet | `/test --manual` |

#### Reconciliation

| Agent | Point | Checks both directions |
|-------|-------|----------------------|
| `requirements_brd_reconciler` | A: Requirements → BRD | Missing from BRD, invented in BRD |
| `brd_spec_reconciler` | B: BRD → Specs | Uncovered FR-*, scope creep in specs |
| `spec_impl_reconciler` | C: Specs → Implementation | Missing implementations, unspecced code |
| `spec_test_reconciler` | D: Specs → Tests | Untested behaviors, tests for non-spec behavior |

#### Infrastructure & Operations

| Agent | Role | Invoked by |
|-------|------|-----------|
| `deployment_agent` | Builds and deploys the application | `/deploy` |
| `ci_cd_agent` | Creates CI/CD pipeline config (GitHub Actions, etc.) | `/deploy` first time |
| `observability_agent` | Validates logging, metrics, tracing setup | `/deploy` staging/prod first time |
| `documentation_agent` | Updates API docs and README after implementation | `/develop` Step 6b (non-blocking) |

#### Diagrams & Architecture

| Agent | Role |
|-------|------|
| `architecture_orchestrator` | High-level architecture design and validation |
| `c4_diagram_agent` | C4 model diagrams (context, container, component) |
| `sequence_diagram_agent` | Sequence diagrams for key flows |
| `deployment_diagram_agent` | Infrastructure and deployment topology diagrams |

#### Demo & QA

| Agent | Role |
|-------|------|
| `demo_executor` | Runs demo scripts and captures outputs |
| `demo_validator` | Validates demo output against expected results |
| `demo_documenter` | Produces demo documentation and walkthrough |

---

## Skill packs

Skill packs are loaded by generated agents at runtime to apply language- and framework-specific idioms, patterns, and conventions. They're how `code_reviewer_I` knows what "idiomatic Go" means vs "idiomatic Python".

### Languages
`go` · `python` · `typescript` · `java` · `rust`

### Frameworks
**Backend:** `gin` · `echo` · `fastapi` · `django` · `express` · `nestjs`
**Frontend:** `react` · `nextjs` · `vue`

### Databases
`postgres` · `mysql` · `mongodb` · `redis` · `sqlite`

### Infrastructure
`docker` · `github-actions` · `kubernetes`

Missing a skill pack? Add a `.md` file to `~/.claude/skills/<category>/` following the same format. The `agent_factory` will pick it up on the next `/init`.

---

## Phase manifest — the inter-phase handshake

Every completed phase writes `agent_state/phases/N/manifest.json`. The next phase reads it to know what already exists — preventing agents from re-implementing or overwriting prior work.

```json
{
  "phase": 1,
  "goal": "User authentication and core API",
  "completed_at": "2025-04-28T14:30:00Z",
  "brd_requirements_met": ["FR-001", "FR-002", "FR-003", "NFR-SEC-01"],
  "acceptance_tests": {
    "use_cases_total": 4,
    "use_cases_passed": 4,
    "personas_exercised": ["Admin User", "End User"],
    "seed_data": "agent_state/phases/1/test-data/generated-seed.yaml"
  },
  "artifacts": {
    "api_routes": ["POST /api/v1/auth/login", "POST /api/v1/auth/logout"],
    "code": ["src/services/auth.go", "src/handlers/auth.go"],
    "migrations": ["migrations/001_add_users.sql"],
    "tests": ["src/services/auth_test.go"]
  },
  "test_results": {
    "unit": { "status": "passed", "total": 24, "passed": 24, "failed": 0 },
    "integration": { "status": "passed", "total": 8, "passed": 8, "failed": 0 },
    "e2e": { "status": "not_run" }
  },
  "known_issues": [],
  "carried_forward": []
}
```

`carried_forward[]` issues surface at the top of every audit report in subsequent phases — nothing gets silently dropped.

---

## Seed data for acceptance testing

The `acceptance_test_agent` looks for test data in priority order:

1. `requirements/test-data/phase-N.yaml` — user-provided (takes priority)
2. `requirements/test-data/global.yaml` — shared data for all phases
3. Auto-generated from BRD personas + in-scope FR-* use cases

Providing your own seed data gives you deterministic acceptance tests from day one. The format is flexible — YAML, JSON, or Markdown test scripts all work.

---

## Model cost profile

| Tier | Agents | Rationale |
|------|--------|-----------|
| **opus** | `architecture_orchestrator`, `backend_developer`, `api_developer`, `ux_designer`, `code_reviewer_II`, `security_reviewer`, `acceptance_test_agent`, `spec_impl_reconciler`, `product_manager` | Deep reasoning: architecture design, complex code generation, security analysis, nuanced acceptance validation |
| **sonnet** | Everything else (31 agents) | Structured output, document processing, spec generation, reconciliation, code review style |
| **haiku** | `demo_executor`, `test_runner`, `status` | Lightweight execution, result formatting |

To adjust: edit `~/.claude/settings.json` `agents.opus_agents` array.

---

## Token and context window management

### Why context windows fill up

`/develop` is a multi-step pipeline running in a single Claude Code conversation. Every file read and every subagent result gets appended to the conversation as a tool output. Without discipline, a 7-step pipeline with 10+ agents easily exceeds a 200K context window before reaching the gate.

### Three rules enforced by the framework

**1. `phase_context.md` replaces full document loads**

During `/plan`, `project_planner` writes `docs/design/phases/N/phase_context.md` — a structured **6-8K** complete context file containing the full tech stack, all coding conventions, all security NFRs, full acceptance criteria, and "what already exists." It is intentionally complete — agents need enough context to make correct decisions.

All implementation agents load this instead of the full `docs/BRD.md` (~20-50K) and `docs/IMPLEMENTATION_GUIDELINES.md` (~10-20K).

Estimated savings per `/develop` run (8 parallel agents, Wave 2):
```
Before:  8 agents × (BRD 30K + IMPL 15K + all specs 10K) = 440K tokens in document reads
After:   8 agents × (phase_context 7K + own spec 7K)     = 112K tokens in document reads
Saving:  ~75% reduction in document-reading tokens
```

The extra cost of a thorough `phase_context.md` (6-8K vs a 2K stub) is worth it: an agent with incomplete context makes wrong architectural decisions that cost 10× more to fix.

**2. Agents return summaries, not content**

Every agent ends with exactly this 3-line return — nothing more:
```
✅ backend_developer complete → wrote agent_state/phases/2/backend_developer/manifest.json
   Done: UserService, AuthService, UserRepository — 3 services, 2 repos
   Issues: none
```
The full implementation is in files. The parent reads the output file path when needed — it never asks the agent to reproduce content.

**3. Per-step context budget targets**

| Step | Target input tokens |
|------|---------------------|
| Orient + Audit | ~15K |
| Implement (per wave, per agent) | ~20K |
| Test | ~15K |
| Reconcile | ~20K |
| Review | ~15K (code diff only — not full codebase) |
| Acceptance | ~10K |
| Gate | ~5K (report headers only) |

### If the window fills mid-pipeline

All state is in `agent_state/phases/N/`. Start a new conversation and resume from the last completed step — the step reads its input files, runs, writes output, returns 3-line summary. No conversation history needed.

```
/startup/status          ← shows exactly where you stopped
/startup/develop --phase=N   ← resumes from last incomplete step
```

---

## Updating startup-agents

After pulling new changes:

```bash
cd ~/development/startup-agents
git pull
bash install.sh
```

---

## Common patterns

### Resuming after a break

```
/startup/status         ← tells you exactly where you are and what to run next
```

### Re-running a phase

Delete the gate file to unlock re-development:
```bash
rm agent_state/phases/2/gate.passed
/startup/develop --phase=2
```

### Handling a change request mid-project

1. Use `product_manager` agent to evaluate the change and update `docs/BRD.md`
2. Re-run `/startup/plan --phase=N` for the affected phase
3. Re-run `/startup/develop --phase=N`

### Adding a tech stack not in skill packs

Create `~/.claude/skills/<category>/<tech>.md` following the format of an existing skill. Run `/startup/init --update_agents` to regenerate agents with the new skill pack.

### Skipping UI wireframes

If your project has no frontend, set `frontend.enabled = false` in `docs/IMPLEMENTATION_GUIDELINES.md`. The `ui_developer`, `ui_audit_agent`, and `ui_test_agent` will not be generated.

---

## Requirements folder reference

```
requirements/
├── *.md / *.pdf / *.txt      ← any format, any content — brd_agent reads all of it
├── IMPLEMENTATION_GUIDELINES.md   ← optional tech stack template (see new-project.sh)
└── test-data/
    ├── phase-1.yaml          ← seed data for phase 1 acceptance tests
    ├── phase-2.yaml          ← seed data for phase 2 acceptance tests
    └── global.yaml           ← shared seed data for /accept
```

`requirements/` is **read-only**. Agents never modify it. All generated output goes to `docs/`, `agent_state/`, and `.claude/agents/generated/`.
