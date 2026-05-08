# startup-agents

A reusable AI-agent framework for building software products end-to-end with Claude Code. Drop in your requirements, run three commands, get a production-ready application with tests, code reviews, and acceptance validation at every phase.

---

## How it works

You provide requirements. The agents do the rest — from turning a pitch deck into a structured BRD, through implementation waves, to final acceptance testing against every user persona.

```
requirements/                  ← YOUR INPUT — agents read but never modify this
    ├── feature-spec.md        ← user stories, PRD, pitch deck (any format)
    ├── IMPLEMENTATION_GUIDELINES.md  ← optional DRAFT: fill in what you know
    └── test-data/             ← optional: seed data per phase

                ↓ /startup/init reads requirements/, interviews for gaps ↓

docs/                          ← GENERATED OUTPUT — agents write here
    ├── BRD.md                 ← numbered requirements (FR-*, NFR-*) — always generated, never hand-written
    └── IMPLEMENTATION_GUIDELINES.md  ← confirmed tech stack — generated from your draft + interview

/startup/plan  →  docs/design/phases/1/specs/  (TRDs + wireframes)
/startup/develop  →  implement + test + review + gate
(repeat plan/develop per phase)
/startup/accept  →  full-product validation against all BRD personas
```

> **Convention:** `requirements/` is read-only input. `docs/` is generated output. Never write `BRD.md` by hand — always run `/startup/init`. The `IMPLEMENTATION_GUIDELINES.md` in `requirements/` is your optional draft; `/init` produces the authoritative confirmed version in `docs/`.

---

## Core Concepts

The framework has four building blocks. Understanding how they connect is the key to using (and extending) the system.

| Concept | What it is | Where it lives | Example |
|---------|-----------|----------------|---------|
| **Command** | User-facing entry point. You invoke these. Each command orchestrates a sequence of agents. | `.claude/commands/*.md` | `/startup/develop`, `/startup/review` |
| **Pipeline Step** | A numbered step inside a command. Steps run sequentially; some steps run agents in parallel. | Defined inside command `.md` files | Step 4 (Review) inside `/startup/develop` |
| **Agent** | The worker that does the actual job. Reads inputs, loads skill packs, produces code or reports. | `.claude/agents/core/*.md` (universal) and `.claude/agents/generated/*.md` (project-specific) | `code_reviewer_I`, `api_developer_myapp` |
| **Skill Pack** | Static knowledge file. Contains idiomatic patterns, conventions, and anti-patterns for a specific technology. Agents load these as context before executing. | `.claude/skills/**/*.md` | `go.md`, `react.md`, `testify.md` |

### How they connect

```
COMMAND                    PIPELINE STEPS              AGENTS                    SKILL PACKS
(you invoke)               (inside the command)        (do the work)             (domain knowledge)
─────────────              ──────────────────          ─────────────             ──────────────────
/startup/develop    ─┬──→  Step 0 Orient
                     ├──→  Step 1 Audit          ──→  backend_audit_agent
                     ├──→  Step 2 Implement      ──→  backend_developer    ←──  go.md, chi.md, postgresql.md
                     │                           ──→  api_developer        ←──  go.md, chi.md, api-design.md
                     │                           ──→  ui_developer         ←──  typescript.md, react.md, shadcn.md
                     ├──→  Step 3 Test           ──→  unit_test_agent      ←──  go.md, testify.md, gomock.md
                     │                           ──→  integration_test     ←──  go.md, testify.md, postgresql.md
                     ├──→  Step 3f Optimize      ──→  code_optimizer       ←──  go.md, chi.md, postgresql.md
                     │                           ──→  ui_code_optimizer    ←──  typescript.md, react.md, shadcn.md
                     ├──→  Step 4 Review         ──→  code_reviewer_I      ←──  go.md, chi.md
                     │                           ──→  security_reviewer    ←──  go.md, security-owasp.md
                     ├──→  Step 5 Acceptance     ──→  acceptance_test_agent←──  go.md, api-design.md
                     └──→  Step 6 Gate

/startup/review     ─┬──→  Step 1 Style         ──→  code_reviewer_I      ←──  go.md, chi.md
                     ├──→  Step 2 Architecture   ──→  code_reviewer_II     ←──  go.md, chi.md, postgresql.md
                     └──→  Step 3 Security       ──→  security_reviewer    ←──  go.md, security-owasp.md
```

**The flow:** You invoke a **command** → the command runs **pipeline steps** in order → each step spawns **agents** → each agent loads its **skill packs** for technology-specific knowledge → the agent reads code/specs, applies skill pack patterns, and produces output.

**Why skill packs matter:** Without `go.md`, the `code_reviewer_I` agent wouldn't know that `var items []Certificate` (nil slice) serializes to JSON `null` instead of `[]`. Without `testify.md`, the `unit_test_agent` wouldn't know to use `require.NoError` for preconditions and `assert.Equal` for assertions. Skill packs are what make generic agents produce idiomatic, tech-specific output.

### Skill pack loading flow

```
/startup/init
  → agent_factory reads IMPLEMENTATION_GUIDELINES
  → extracts tech profile: { lang: go, framework: chi, db_tech: postgresql, ... }
  → resolves {{PLACEHOLDER}} in agent templates: ".claude/skills/languages/{{LANG}}.md" → ".claude/skills/languages/go.md"
  → writes generated agents with resolved skill_packs paths

/startup/develop (later)
  → spawns backend_developer agent
  → agent reads skill_packs: [go.md, chi.md, postgresql.md]
  → skill content becomes part of agent's working context
  → agent writes Go code using patterns from the skill packs
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
| `/startup/optimize` | Standalone code optimization with before/after comparison — dead code, code reduction, performance |
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
--force_gate      Force gate to pass with failures (logged as gate_override in manifest)
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

**`/startup/optimize`**
```
--phase=N         Target phase (default: auto-detect latest completed)
--backend_only    Optimize backend only — skip UI
--ui_only         Optimize UI only — skip backend
--dry_run         Show what WOULD change without modifying code
--aggressive      Include MEDIUM-confidence dead code removal
```

**`/startup/deploy`**
```
--target=local|staging|prod   (default: local)
--dry_run                     Show plan without deploying
```

---

## The SDLC pipeline

`/startup/develop` runs a multi-step pipeline per phase:

```
Step 0    Orient           Detect phase, load previous manifest, start infra
Step 1    Audit            Gap report: what's missing vs what the specs require
Step 2    Implement        Wave-based execution (DB → backend → contract validation → UI → tests)
Step 2.5  Contract Valid.  Verify api-contracts.md before UI starts (UI phases only)
Step 3a   Unit Tests       Unit tests for all new code
Step 3a.5 Regression       Cross-phase regression check (Phase > 1 only)
Step 3b   Integration      Service↔DB + API endpoint tests + response shape contract tests
Step 3c   E2E Tests        Full user workflow tests (if workflow unlocked this phase)
Step 3d   Reconcile C      Spec ↔ Implementation (bidirectional)
Step 3e   Reconcile D      Spec ↔ Tests (bidirectional)
Step 3f   Optimize         Dead code removal + code optimization (backend ∥ UI, mandatory)
Step 3g   Re-test          Post-optimization test re-run (mandatory safety net)
Step 4    Review           Style → Architecture + Security + Dependency scan (parallel)
Step 5    Acceptance       Use case + persona level validation with seed data
Step 6    Gate             11 conditions must pass — writes gate.passed + manifest.json
Step 6b   Document         API docs + README updates (non-blocking, parallel)
Step 7    Report           Summary of what was built, test results, gate status
```

### Phase gate — all 11 must pass

```
✅ Unit tests              all passing
✅ Integration tests       all passing
✅ E2E tests               all passing (only if phase unlocks a workflow)
✅ Reconciliation C        no MISSING implementations; unspecced items acknowledged
✅ Reconciliation D        no HIGH-priority untested behaviors
✅ Code optimization       post-optimization tests pass (CLEAN or PARTIAL accepted)
✅ UI code optimization    post-optimization tests pass (if frontend enabled)
✅ Code review I           no BLOCKING style issues
✅ Code review II          no architecture violations
✅ Security review         no HIGH severity findings
✅ Acceptance tests        all in-scope use cases pass
```

If any condition fails: the gate does not write. The blocker is surfaced with the specific file, finding, and how to fix it. Use `--force_gate` to override known flakes (logged in manifest as `gate_override`).

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

Each phase runs in waves (sequential between waves, parallel within):

```
Wave 1    database_agent + migration_agent          (parallel)
Wave 1.5  Migration validation — dry-run UP/DOWN    (sequential gate)
Wave 2a   backend_developer                         (sequential — api needs service interfaces)
Wave 2b   api_developer                             (reads backend manifest for return types)
Wave 2.5  API contract validation                   (UI phases only — blocks Wave 3)
Wave 3    ui_developer                              (UI phases only — reads api-contracts.md)
Wave 4    unit_test_agent + integration_test_agent   (parallel)
```

**Key dependency:** api_developer reads backend_developer's manifest to know which response helper to use (`RespondList` for list methods, `RespondOne` for single methods). This is why Wave 2 is sequential (2a → 2b), not parallel.

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
│               ├── regression_check.md         ← cross-phase regression (Phase > 1)
│               ├── code_optimization.md        ← backend dead code + optimization
│               ├── ui_code_optimization.md     ← UI dead code + optimization (UI phases)
│               ├── code_review_I.md
│               ├── code_review_II.md
│               ├── security_review.md
│               ├── dependency_scan.md          ← CVE/outdated/license scan
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

#### Code Optimization

| Agent | Role | Model | Trigger |
|-------|------|-------|---------|
| `code_optimizer` | Backend dead code removal + code/performance optimization | sonnet | `/develop` Step 3f (mandatory) |
| `ui_code_optimizer` | UI dead code removal + bundle size/render optimization | sonnet | `/develop` Step 3f (if frontend enabled) |
| `dependency_scanner` | Scans dependencies for CVEs, outdated packages, license issues | haiku | `/develop` Step 4 (parallel with review) |

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

Skill packs are static knowledge files that agents load as context before executing. They contain idiomatic patterns, code examples, conventions, and anti-patterns for a specific technology. They're how `code_reviewer_I` knows what "idiomatic Go" means vs "idiomatic Python", and how `code_optimizer` knows to check for nil-slice → JSON null bugs in Go but `undefined` → omitted-field bugs in TypeScript.

### Available skill packs (37)

| Category | Skill Packs |
|----------|-------------|
| **Languages** (5) | `go` · `python` · `typescript` · `java` · `rust` |
| **Frameworks** (11) | **Backend:** `gin` · `echo` · `chi` · `fastapi` · `django` · `express` · `nestjs` · **Frontend:** `react` · `nextjs` · `vue` · `tanstack-query` |
| **Databases** (6) | `postgres` · `postgresql` · `mysql` · `mongodb` · `redis` · `sqlite` |
| **Testing** (6) | `testify` · `gomock` · `testcontainers` · `vitest` · `playwright` · `msw` |
| **UI** (2) | `shadcn` · `tailwind` |
| **Infrastructure** (3) | `docker` · `github-actions` · `kubernetes` |
| **Core** (4) | `api-design` · `security-owasp` · `testing-principles` · `git-workflow` |

### Which agents load which skills

Each agent loads a specific set of skill packs based on what it needs to do:

| Agent | Skills Loaded | What the skills teach the agent |
|-------|--------------|--------------------------------|
| **backend_developer** | `{{LANG}}`, `{{FRAMEWORK}}`, `{{DB_TECH}}` | Language idioms, framework patterns, query patterns, connection pooling |
| **api_developer** | `{{LANG}}`, `{{FRAMEWORK}}`, `api-design`, `security-owasp` | Handler patterns, REST conventions, OWASP checks, response serialization |
| **ui_developer** | `{{LANG}}`, `{{UI_FRAMEWORK}}`, `{{STATE_MANAGEMENT}}`, `{{UI_COMPONENTS}}` | Component patterns, hooks, state management, component library usage |
| **unit_test_agent** | `{{LANG}}`, `{{TEST_FRAMEWORK}}`, `{{MOCK_FRAMEWORK}}`, `testing-principles` | Assert vs require, table-driven tests, mock setup, test isolation |
| **integration_test_agent** | `{{LANG}}`, `{{DB_TECH}}`, `{{TEST_FRAMEWORK}}`, `testing-principles` | Container setup, DB fixtures, API endpoint testing, tenant isolation |
| **ui_test_agent** | `{{LANG}}`, `{{UI_FRAMEWORK}}`, `{{TEST_FRAMEWORK}}`, `{{E2E_TOOL}}`, `{{API_MOCK_TOOL}}`, `testing-principles` | Component rendering, E2E browser tests, API mocking, accessible locators |
| **code_optimizer** | `{{LANG}}`, `{{FRAMEWORK}}`, `{{DB_TECH}}`, `testing-principles` | Dead code tools per language, framework-specific anti-patterns, N+1 query detection |
| **ui_code_optimizer** | `{{LANG}}`, `{{UI_FRAMEWORK}}`, `{{STATE_MANAGEMENT}}`, `{{UI_COMPONENTS}}`, `testing-principles` | Unused components, render optimization (memo/useMemo), bundle size patterns |
| **code_reviewer_I** | `{{LANG}}`, `{{FRAMEWORK}}` | Language idioms to enforce, naming conventions, error handling patterns |
| **code_reviewer_II** | `{{LANG}}`, `{{FRAMEWORK}}`, `{{DB_TECH}}` | Layer boundaries, dependency direction, repository pattern compliance |
| **security_reviewer** | `{{LANG}}`, `security-owasp`, `{{DB_TECH}}` | Language-specific injection risks, SQL injection, auth patterns, secret handling |
| **dependency_scanner** | `{{LANG}}`, `security-owasp` | Package manager audit commands, vulnerability triage |
| **acceptance_test_agent** | `{{LANG}}`, `api-design`, `testing-principles` | API call patterns, persona-based testing, response validation |
| **e2e_orchestrator** | `{{LANG}}`, `testing-principles` | Test execution commands, workflow test design |

`{{PLACEHOLDER}}` values are resolved from `IMPLEMENTATION_GUIDELINES.md` during `/startup/init` by `agent_factory`.

### Adding a custom skill pack

Create a `.md` file in `~/.claude/skills/<category>/` following the format of any existing skill pack. Then run `/startup/init --update_agents` to regenerate project agents with the new skill.

```bash
# Example: add a skill pack for Prisma ORM
cat > ~/.claude/skills/databases/prisma.md << 'EOF'
# Prisma ORM patterns for TypeScript.
## Schema definition
...
## Query patterns
...
## Migration commands
...
EOF

# Regenerate agents to pick up the new skill
/startup/init --update_agents
```

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
| **sonnet** | `code_optimizer`, `ui_code_optimizer`, `code_reviewer_I`, all spec/reconciliation/planning agents (33 agents) | Structured output, document processing, spec generation, reconciliation, code review style, optimization |
| **haiku** | `demo_executor`, `test_runner`, `status`, `dependency_scanner` | Lightweight execution, result formatting, audit tool invocation |

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

---

## User Guide

### Your first project — step by step

```
1. INSTALL (once)          bash install.sh
2. CREATE PROJECT          bash new-project.sh my-app ~/development
3. ADD REQUIREMENTS        Drop specs/stories into my-app/requirements/
4. INITIALIZE              /startup/init
5. PLAN PHASE 1            /startup/plan
6. BUILD PHASE 1           /startup/develop
7. REPEAT 5-6              For each phase until all features are built
8. FINAL VALIDATION        /startup/accept
```

That's it. Everything else is automatic.

### What to run when

| I want to... | Run this |
|-------------|----------|
| Start a new project | `bash new-project.sh my-app` then `/startup/init` |
| Build the next feature set | `/startup/plan` then `/startup/develop` |
| See where I am | `/startup/status` |
| Run tests without building | `/startup/test` |
| Review code quality | `/startup/review` |
| Clean up and optimize code | `/startup/optimize` |
| Preview optimizations without changing code | `/startup/optimize --dry_run` |
| Deploy the app | `/startup/deploy --target=local` |
| Validate the full product | `/startup/accept` |
| Resume after a break | `/startup/status` then follow its recommendation |
| Fix a bug and re-validate | Fix the code, then `/startup/test --phase=N` |
| Add a feature mid-project | Use `product_manager` agent to update BRD, then `/startup/plan` |
| Re-do a phase | `rm agent_state/phases/N/gate.passed` then `/startup/develop --phase=N` |
| Force past a flaky test | `/startup/develop --force_gate` (logged as override) |

### What you DON'T need to do

- **Don't write BRD.md** — `/init` creates it from your requirements
- **Don't pick which agent to use** — commands select the right agents automatically
- **Don't manage phases manually** — commands auto-detect the current phase
- **Don't write test data** — agents generate it (or use yours if you provide it)
- **Don't configure skill packs** — `agent_factory` assigns them based on your tech stack
- **Don't worry about context windows** — the framework manages token budgets internally

### How the pipeline protects your code

Every phase goes through 11 quality checks before it can pass:

```
Your code
  ↓
Unit tests                    ← does each function work?
Integration tests             ← do services + DB work together?
E2E tests                     ← does the full user workflow work?
Cross-phase regression        ← did new code break old features?
Spec ↔ Implementation check   ← is everything from the spec built?
Spec ↔ Test check             ← is every behavior tested?
Code optimization             ← dead code removed, code simplified
Style review                  ← idiomatic, clean, consistent
Architecture review           ← right patterns, right layers
Security review               ← no OWASP vulnerabilities
Acceptance tests              ← works for real users, real scenarios
  ↓
Phase gate PASSED ✅
```

If any check fails, the gate blocks and tells you exactly what to fix.

### Commands at a glance

```
/startup/init       One-time project setup. Creates BRD + agents from your requirements.
/startup/plan       Plans the next phase. Creates specs and wireframes.
/startup/develop    Builds a phase end-to-end. Fully autonomous.
/startup/test       Runs tests standalone. Many flags for targeting specific tiers.
/startup/review     Code review: style + architecture + security.
/startup/optimize   Code cleanup and optimization with before/after comparison.
/startup/accept     Full-product validation after all phases complete.
/startup/deploy     Build and deploy to local, staging, or production.
/startup/status     Where am I? What should I run next?
```

### Tips

- **Start small.** Your first requirements file can be a single paragraph. `/init` will ask clarifying questions.
- **Check status often.** `/startup/status` always tells you the next action.
- **Trust the gate.** If the gate blocks, read the blocker — it tells you the exact file, line, and fix.
- **Use `--dry_run` for optimize.** See what would change before committing to it.
- **Commit between phases.** Each phase is a natural commit point.
- **Provide seed data for predictable tests.** Drop YAML files into `requirements/test-data/` for deterministic acceptance tests.
- **Add your own skill packs.** Using a framework not in the defaults? Create a `.md` file in `~/.claude/skills/` and re-run `/startup/init --update_agents`.
