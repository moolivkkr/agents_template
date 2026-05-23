# startup-agents

A reusable AI-agent framework for building software products end-to-end with Claude Code. Drop in your requirements, run three commands, get a production-ready application with tests, code reviews, and acceptance validation at every phase.

---

## How it works

You provide requirements. The agents do the rest — from turning a pitch deck into a structured BRD, through implementation waves, to final acceptance testing against every user persona.

```
requirements/                  ← YOUR INPUT — agents read but never modify this
    ├── feature-spec.md        ← user stories, PRD, pitch deck (any format)
    ├── research/              ← optional: output from /startup/research
    ├── IMPLEMENTATION_GUIDELINES.md  ← optional DRAFT: fill in what you know
    └── test-data/             ← optional: seed data per phase

                ↓ /startup/init reads requirements/, interviews for gaps ↓

docs/                          ← GENERATED OUTPUT — agents write here
    ├── BRD.md                 ← numbered requirements (FR-*, NFR-*) — always generated
    └── IMPLEMENTATION_GUIDELINES.md  ← confirmed tech stack

/startup/research  →  ultra-deep market & product research (optional, before init)
/startup/init      →  BRD + agents from requirements
/startup/map       →  persistent codebase knowledge base (4 parallel focus areas)
/startup/discuss   →  surface assumptions + research decisions (before /plan)
/startup/plan      →  specs + data-contracts.md + UI specs + goal verification per phase
/startup/develop   →  implement + test + review + gate per phase
/startup/accept    →  local deploy + health gate + full-product validation + release notes
/startup/deploy    →  build + migrate + deploy + health validation

OR: /startup/autonomous  →  all of the above end-to-end with one human checkpoint

Session management:
/startup/pause     →  save session state for later resumption
/startup/resume    →  restore paused session and continue

Parallel work:
/startup/workstream →  manage concurrent feature branches (create, switch, merge)

Issue resolution (use anytime):
/startup/hotfix    →  scoped fix + scoped test + scoped review (bypasses full pipeline)
/startup/diagnose  →  trace symptom to root cause, optional auto-fix
/startup/benchmark →  performance baselines + regression detection
/startup/rollback  →  reverse deployment to previous known-good state

Pipeline diagnostics:
/startup/health    →  diagnose agent_state integrity + auto-repair
/startup/forensics →  post-mortem analysis of failed pipeline runs
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
| `/startup/product-workflows` | **NEW** Product workflow intelligence — researches docs, videos, APIs, forums for a named product. Produces screen-by-screen workflows, config schemas, dependency graphs, API coverage matrix, persona flows |
| `/startup/research` | Ultra-deep market & product research — vendors, capabilities, personas, moats. Produces `requirements/research/` that feeds `/init` |
| `/startup/init` | Reads `requirements/`, creates BRD + IMPL_GUIDELINES, generates project-specific agents. Supports `--auto` for autonomous research mode |
| `/startup/map` | **NEW** Analyzes codebase with 4 parallel mapper agents (tech, architecture, quality, concerns). Produces persistent knowledge base in `agent_state/codebase/` |
| `/startup/discuss` | **NEW** Pre-planning context gathering — surfaces assumptions (CONFIRMED/DEDUCED/HYPOTHESIZED), researches gray area decisions, identifies risks. Run before `/plan` |
| `/startup/plan` | Creates TRDs, typed data contracts, component-level UI specs, and **goal-backward verification** per phase. Supports `--auto` |
| `/startup/develop` | Implements phase end-to-end: audit → build checks → code → tests → review + acceptance (parallel) → gate. Supports `--auto` |
| `/startup/autonomous` | Runs the full pipeline end-to-end — `/map` → `/discuss` → `/plan` → `/develop` for all phases. One human checkpoint. Auto-researches all decisions |
| `/startup/accept` | Runs full-product acceptance tests + contract shape assertions after all phases |
| `/startup/test` | Runs tests standalone (unit / integration / e2e / acceptance / performance / system) |
| `/startup/review` | Standalone code review: spec compliance → style + architecture + security (parallel) |
| `/startup/optimize` | Standalone code optimization with before/after comparison — dead code, code reduction, performance |
| `/startup/deploy` | Builds, migrates, deploys to local / staging / prod, validates health post-deploy |
| `/startup/status` | Shows phase progress, BRD coverage, open issues, and next recommended action |
| `/startup/pause` | **NEW** Saves session state (phase, step, completed items, blockers, decisions) for later resumption. Supports named threads |
| `/startup/resume` | **NEW** Restores paused session state and routes to the appropriate command to continue. Use `--list` to see all paused sessions |
| `/startup/workstream` | **NEW** Manages parallel workstreams — create, list, switch, status, complete, merge. Enables concurrent work on independent features |
| `/startup/hotfix` | Fast-track bug fix — scoped change → scoped test → scoped review → merge. Bypasses full `/develop` cycle |
| `/startup/diagnose` | Structured bug investigation — traces symptom to root cause through spec ↔ implementation comparison |
| `/startup/benchmark` | Performance tracking — captures metrics per phase, saves baselines, flags regressions >10% |
| `/startup/rollback` | Deployment rollback — reverses migrations, redeploys previous build, validates health |
| `/startup/health` | **NEW** Diagnoses pipeline state integrity — manifest validity, gate consistency, file references, memory hygiene (stale sessions, stale codebase mappings, oversized logs, orphaned debates). Use `--fix` for auto-repair |
| `/startup/forensics` | **NEW** Post-mortem investigation for failed pipeline runs — timeline reconstruction, root cause classification, recovery recommendations |

### Command arguments

**`/startup/research`**
```
--domain="..."    Product domain to research (required, e.g., "XDR/EDR cybersecurity")
--depth=deep      Research depth: quick | deep (default) | ultra
--focus=all       Focus area: vendors | capabilities | technical | personas | moats | all
```

**`/startup/init`**
```
--update_agents   Re-generate project agents only (use after tech stack changes)
--brd_only        Regenerate BRD only
--auto            Auto-research mode — agents research answers instead of asking user
```

**`/startup/plan`**
```
--phase=N         Override phase number (default: auto-detect next unplanned)
--ui_only         Regenerate UI specs only
--verify_only     Verify existing specs against BRD — no new generation
--auto            Auto-assign FR-* to phases by dependency analysis
```

**`/startup/develop`**
```
--phase=N         Override phase number (default: auto-detect from gate state)
--audit_only      Gap report only — no implementation changes
--test_only       Run tests only — no implementation changes
--force_gate      Force gate to pass with failures (logged as gate_override in manifest)
--auto            Autonomous mode — auto-resolve escalations, auto-fix gate failures
```

**`/startup/product-workflows`**
```
--product="..."   Product name (required, e.g., "Trellix DLP", "CrowdStrike Falcon")
--capabilities="…" Comma-separated list (omit to discover and document FULL system)
--screenshots=DIR  Path to screenshot directory for visual analysis
--depth=standard  Research depth: quick | standard | deep (adds video + community analysis)
--version="..."   Target product version (e.g., "11.x")
--output=DIR      Output directory (default: docs/product-workflows)
```

**`/startup/discuss`**
```
--phase=N         Phase to discuss (default: auto-detect next unplanned)
--auto            Skip interactive questions — use recommended defaults, log all decisions
--focus=all       Focus: assumptions | risks | decisions | all
```

**`/startup/map`**
```
--focus=all       Focus: tech | architecture | quality | concerns | all
--incremental     Only re-map files changed since last mapping
--phase=N         Scope mapping to components relevant to a specific phase
```

**`/startup/autonomous`**
```
--confirm_each_phase   Pause for human review before EACH phase (default: Phase 1 only)
--resume               Resume from last checkpoint
--skip_init            Use existing BRD + IMPL_GUIDELINES
--max_phases=N         Limit to N phases
```

**`/startup/pause`**
```
--phase=N         Phase being worked on (auto-detected)
--reason="..."    Why work is being paused
--thread=NAME     Named thread for this work (enables multiple paused contexts)
```

**`/startup/resume`**
```
--thread=NAME     Named thread to resume (default: latest session)
--list            List all paused sessions instead of resuming
```

**`/startup/workstream`**
```
--action=ACTION   create | list | switch | status | complete | merge (required)
--name=NAME       Workstream name (required for create/switch/complete/merge)
--phase=N         Phase(s) this workstream covers (comma-separated)
--description="…" Workstream description (for create)
```

**`/startup/health`**
```
--fix             Attempt automatic repair of detected issues
--phase=N         Check specific phase only
--verbose         Show detailed results including passing checks
```

**`/startup/forensics`**
```
--phase=N         Phase to investigate (default: most recently failed)
--command=CMD     Which command failed: plan | develop | test | review | deploy
--depth=standard  Investigation depth: quick | standard | deep
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

**`/startup/hotfix`**
```
--phase=N         Phase containing the bug (required)
--component=NAME  Component to fix (e.g. auth, users)
--description="…" Bug description for commit message
--security        Route through security_reviewer instead of code_reviewer_I
--deploy          Fast-track to /deploy after merge
```

**`/startup/diagnose`**
```
--symptom="…"     What's broken (required, e.g. "GET /users returns 500")
--phase=N         Phase to investigate (default: auto-detect)
--component=NAME  Narrow investigation to specific component
--fix             Auto-apply recommended fix after diagnosis
```

**`/startup/benchmark`**
```
--phase=N           Target phase (default: latest completed)
--save-baseline     Save results as the baseline for this phase
--compare           Compare against previous baseline, flag regressions
--endpoints="…"     Test specific endpoints only (comma-separated)
```

**`/startup/rollback`**
```
--target=local|staging|prod   Environment to roll back (required)
--confirm                     Required for production rollback
```

---

## The SDLC pipeline

`/startup/develop` runs a multi-step pipeline per phase:

```
Step 0    Orient           Detect phase, load previous manifest, start infra
Step 0.5  Readiness Gate   Verify specs, phase_context, data-contracts.md exist
Step 1    Audit            Gap report: what's missing vs what the specs require
Step 2    Implement        Wave-based execution with build checks + smoke test:
                           DB → migration validation (auto-rollback on failure) →
                           backend → BUILD CHECK → API → SMOKE TEST → UI → tests
Step 2.5  Contract Valid.  Verify api-contracts.md matches data-contracts.md (UI phases)
                           + backward compatibility check (field removal = HARD BLOCK)
Step 3a   Unit Tests       Unit tests for all new code
Step 3a.5 Regression       Cross-phase regression check (Phase > 1 only)
Step 3b   Integration      Service↔DB + API endpoint tests + contract shape tests
Step 3c   E2E Tests        Full user workflow tests (if workflow unlocked this phase)
Step 3d+e Reconcile        Spec↔Impl + Spec↔Tests (PARALLEL, 4-level verification)
Step 3f   Optimize         Dead code removal + code optimization (backend ∥ UI)
Step 3g   Re-test          Post-optimization re-run (skipped if zero changes)
Step 4    PARALLEL TRACKS:
  Track A: Review          Spec compliance → Style + Arch + Security + SAST + Deps (parallel)
  Track B: Acceptance      Persona tests + contract shape assertions + browser E2E (UI phases)
Step 5    Gate             13 conditions must pass — writes gate.passed + manifest.json
                           Bug severity classification (critical/high/medium/low)
                           Flaky test quarantine (auto-skip after 2+ phases, tracked)
Step 5b   Document         API docs + README updates (non-blocking, parallel)
Step 6    Report           Summary of what was built, test results, gate status
```

### Phase gate — all 13 must pass

```
✅ Spec compliance         implementation matches specs (no missing, no deviations)
✅ Unit tests              all passing
✅ Integration tests       all passing
✅ E2E tests               all passing (only if phase unlocks a workflow)
✅ Reconciliation C        no MISSING implementations; unspecced items acknowledged
✅ Reconciliation D        no HIGH-priority untested behaviors
✅ Code optimization       post-optimization tests pass (CLEAN or PARTIAL accepted)
✅ UI code optimization    post-optimization tests pass (if frontend enabled)
✅ Code review I           no BLOCKING style issues
✅ Code review II          no architecture violations + error response shapes match specs
✅ Security review         no HIGH severity findings
✅ SAST scan               no CRITICAL/HIGH findings (semgrep/govulncheck/bandit)
✅ Acceptance tests        all in-scope use cases pass (browser-based for UI phases)
```

**Bug severity classification:** Gate blockers are classified as critical/high/medium/low. Critical issues cannot be carried forward. High issues auto-escalate to critical after 1 phase. Medium auto-escalates after 3 phases.

If any condition fails: the gate does not write. The blocker is surfaced with the specific file, finding, and how to fix it. Use `--force_gate` to override known flakes (logged in manifest as `gate_override`).

### Bidirectional reconciliation

At five transition points, a reconciler validates in both directions:

| Point | Agent | Checks |
|-------|-------|--------|
| A: Requirements → BRD | `requirements_brd_reconciler` | Nothing dropped, nothing invented |
| B: BRD → Specs | `brd_spec_reconciler` | Every FR-* has a spec; no gold-plating |
| C: Specs → Implementation | `spec_impl_reconciler` | Every spec behavior is built; no unspecced code |
| D: Specs → Tests | `spec_test_reconciler` | Every edge case has a test; no tests for non-spec behavior |
| E: Full Chain (capstone) | `pipeline_completeness_agent` | Every requirement traces end-to-end; all logged gaps resolved; scored verdict |

Forward gaps = blockers. Reverse gaps (invented/unspecced) = flagged for human review.

Point E runs after `/accept` and validates the ENTIRE chain as a connected whole — catching requirements that passed A-D individually but were dropped between links, forced gate blockers never resolved, and cross-phase coverage holes. Produces a scored completeness verdict (COMPLETE/NEAR COMPLETE/INCOMPLETE/FAILING) that can veto release readiness.

### Intelligence protocols (inspired by ruflo analysis)

Four skill packs in `.claude/skills/core/` add intelligence to the pipeline:

| Protocol | Skill Pack | Where it applies |
|----------|-----------|-----------------|
| **Adaptive replanning** | `adaptive-replan.md` | Wave 5 — classifies failures (LOGIC/WIRING/CONTRACT/SCHEMA/UI/CONFIG/FLAKY), determines minimum re-test scope instead of re-running all tiers |
| **Change-impact test selection** | `change-impact-analysis.md` | Wave 6 gate — analyzes `git diff` to run only affected tests for per-phase regression (full regression still at `/accept`) |
| **Complexity-based model routing** | `model-routing.md` | All agents — `model: auto` selects haiku/sonnet/opus based on task complexity (spec count, LOC changed, FR-* scope) |
| **Structured lessons** | `structured-lessons.md` | Post-Gate — lessons indexed by category/tag with confidence levels, queryable by downstream agents |

### Implementation waves

Each phase runs in waves (sequential between waves, parallel within):

```
Wave 1    database_agent + migration_agent          (parallel)
Wave 1.5  Migration validation — dry-run UP/DOWN    (sequential gate)
Wave 2a   backend_developer                         (sequential — api needs service interfaces)
Wave 2b   api_developer                             (reads backend manifest for return types)
Wave 2.5  API contract validation                   (UI phases only — blocks Wave 3)
Wave 3    ui_developer                              (UI phases only — reads api-contracts.md)
Wave 3.5  Local deploy + health check               (build → migrate → start → verify healthy)
Wave 4    unit_test_agent + integration_test_agent + acceptance_test_agent  (parallel)
```

**Key dependency:** api_developer reads backend_developer's manifest to know which response helper to use (`RespondList` for list methods, `RespondOne` for single methods). This is why Wave 2 is sequential (2a → 2b), not parallel.

### Auto-checkpoints

After each wave completes, the orchestrator writes a lightweight checkpoint to `agent_state/phases/N/checkpoints/wave-N.json`. If context resets mid-pipeline (no explicit `/pause`), `/resume` detects these checkpoints and routes you to the right wave:

```
/startup/resume
  → "No explicit /pause session found, but auto-checkpoints detected:
     Phase: 2, Last wave: 3. Resume with: /develop --phase=2"
```

Checkpoint schema: `{ ts, phase, wave_completed, wave_next, git_sha, artifacts_produced, tests_passing, blocking_issues }`.

### Cross-phase learning

The framework accumulates lessons across phases:

- **`agent_state/phases/N/lessons.md`** — extracted after each phase: what worked, what didn't, recommendations for next phase
- **`agent_state/patterns.md`** — accumulated cross-phase patterns. `project_planner` reads both files to apply proven patterns and avoid known pitfalls when planning the next phase.

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
│   ├── patterns.md                        ← ACCUMULATED cross-phase patterns (what works / what to avoid)
│   ├── codebase/                        ← GENERATED by /map
│   │   ├── .last-mapped                 ← timestamp + SHA + confidence level
│   │   ├── SUMMARY.md                   ← 1-page overview
│   │   ├── tech-stack.md                ← languages, frameworks, build tools
│   │   ├── architecture.md              ← module boundaries, API surface, data models
│   │   ├── quality.md                   ← test coverage, patterns, tech debt
│   │   └── concerns.md                  ← security, performance, reliability issues
│   ├── sessions/                        ← GENERATED by /pause
│   │   └── {thread}/
│   │       └── LATEST.md               ← most recent pause snapshot
│   ├── workstreams/                     ← GENERATED by /workstream
│   │   └── registry.json               ← active workstreams + state
│   ├── forensics/                       ← GENERATED by /forensics
│   │   └── {timestamp}-phase-N.md      ← post-mortem reports
│   ├── e2e/
│   │   └── results.md
│   └── phases/
│       └── N/
│           ├── gate.passed            ← exists = phase is complete
│           ├── manifest.json          ← handshake consumed by phase N+1
│           ├── lessons.md             ← patterns that worked, issues encountered, recommendations
│           ├── checkpoints/           ← auto-checkpoints (one per wave)
│           │   ├── wave-N.json        ← { ts, phase, wave_completed, git_sha, artifacts }
│           │   └── compact-context.md ← written at 75% context — compact summary for inline resume
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
| `phase_assumptions_analyzer` | **NEW** Deep codebase analysis — surfaces structured assumptions with evidence levels (CONFIRMED/DEDUCED/HYPOTHESIZED) before planning | opus |
| `decision_researcher` | **NEW** Researches gray area decisions — produces comparison tables with pros/cons/risk/recommendation for each option | sonnet |
| `plan_goal_verifier` | **NEW** Goal-backward verification — traces phase goal → specs → components → contracts to verify the plan will achieve its objective | opus |

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
| `codebase_mapper` | **NEW** Explores codebase with focus area (tech/arch/quality/concerns), writes persistent knowledge base | `/map` |

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

### Available skill packs (160+)

| Category | Skill Packs |
|----------|-------------|
| **Core** (16) | `api-design` · `api-excellence` · `security-owasp` · `testing-principles` · `code-quality` · `git-workflow` · `auto-research` · `deep-research` · `debate-protocol` · `software-architecture` · `resiliency-patterns` · `observability-patterns` · `verification-protocol` · `context-budget-protocol` · `shared-backend-patterns` · `implementation-guidelines-template` |
| **Requirements** (9) | `requirement-clarity` · `acceptance-criteria` · `persona-definition` · `nfr-patterns` · `gap-analysis-checklist` · `conflict-detection` · `business-objectives` · `traceability-matrix` · `edge-case-taxonomy` |
| **UI Patterns** (14) | `professional-ui-standards` · `error-handling-patterns` · `form-patterns` · `accessibility-patterns` · `responsive-patterns` · `loading-states` · `component-composition` · `api-integration-patterns` · `shadcn` · `tailwind` · **NEW:** `type-generation-protocol` · `form-validation-protocol` · `advanced-state-patterns` · `structured-wireframe-format` |
| **UI Archetypes** (6) | `list-page` · `detail-page` · `form-page` · `dashboard-page` · `settings-page` · `component-test` |
| **Languages** (5) | `go` · `python` · `typescript` · `java` · `rust` |
| **Frameworks** (18) | **Backend:** `gin` · `echo` · `chi` · `fastapi` · `django` · **NEW:** `drf` · `express` · `nestjs` · **NEW:** `fastify` · `spring-boot` · **NEW:** `quarkus` · `axum` · **NEW:** `actix-web` · **NEW:** `graphql` · **Frontend:** `react` · `nextjs` · `vue` · `tanstack-query` |
| **Databases** (9) | `postgres` · `mysql` · `mongodb` · `redis` · `sqlite` · **NEW:** `dynamodb` · **NEW:** `elasticsearch` · **NEW:** `firestore` · `query-optimization` |
| **Testing** (13) | `testify` · `gomock` · `testcontainers` · `vitest` · `playwright` · `msw` · `junit-mockito` · `pytest` · `rust-test` · **NEW:** `property-based` · **NEW:** `contract-testing` · **NEW:** `load-testing` · **NEW:** `targeted-testing` · **NEW:** `external-service-mocks` |
| **Backend Archetypes** (60+) | CRUD handler/service/repository + tests (all 5 languages) · auth middleware · error handling · migrations · Dockerfiles · observability · performance · **NEW:** workers · **NEW:** WebSocket · **NEW:** gRPC · **NEW:** message queues |
| **Infrastructure** (3) | `docker` · `github-actions` · `kubernetes` |

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
| **opus** (12) | `architecture_orchestrator`, `backend_developer`, `api_developer`, `ux_designer`, `code_reviewer_II`, `security_reviewer`, `acceptance_test_agent`, `spec_impl_reconciler`, `product_manager`, **`phase_assumptions_analyzer`**, **`plan_goal_verifier`**, `tenant_isolation_verifier` | Deep reasoning: architecture design, complex code generation, security analysis, nuanced acceptance validation, assumption surfacing, goal-backward verification |
| **sonnet** (41) | `code_optimizer`, `ui_code_optimizer`, `code_reviewer_I`, **`decision_researcher`**, **`codebase_mapper`**, all spec/reconciliation/planning agents | Structured output, document processing, spec generation, reconciliation, code review style, optimization, codebase mapping, decision research |
| **haiku** (3) | `demo_executor`, `test_runner`, `dependency_scanner` | Lightweight execution, result formatting, audit tool invocation |

To adjust: edit `~/.claude/settings.json` `agents.opus_agents` array.

---

## Token and context window management

### Core principle: quality over token savings

A/B testing showed that verbose, complete agent context produces **7.7% better results** on judgment tasks (review, acceptance, debugging). The framework optimizes for output quality, not token efficiency. An agent that makes wrong decisions because it lacked context costs far more to fix than a larger context payload.

### Why context windows fill up

`/develop` is a multi-step pipeline running in a single Claude Code conversation. Every file read and every subagent result gets appended to the conversation as a tool output. Without discipline, a 7-step pipeline with 10+ agents easily exceeds a 200K context window before reaching the gate.

### Four rules enforced by the framework

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

**3. Codebase knowledge is mandatory when present**

When `/map` has been run (`agent_state/codebase/.last-mapped` exists), downstream agents MUST load the focus document matching their role:

| Agent role | Focus document |
|-----------|---------------|
| `backend_developer`, `api_developer` | `architecture.md` |
| `code_reviewer_I`, `code_optimizer` | `quality.md` |
| `security_reviewer` | `concerns.md` |
| `project_planner`, `backend_audit_agent` | ALL focus documents |

The extra 5-10K per agent prevents avoidable implementation errors. If `/map` hasn't been run, agents skip this — it's optional to run, but mandatory to read when present.

Codebase mappings track a **confidence lifecycle**: `initial` (freshly mapped) → `high` (validated by a passing gate) → `degraded` (gate failed after mapping) → `stale` (>30 days old or >50 files changed). Agents adjust their trust level accordingly.

**4. Per-step context budget targets**

| Step | Target input tokens |
|------|---------------------|
| Orient + Audit | ~15K |
| Implement (per wave, per agent) | ~20K |
| Test | ~15K |
| Reconcile | ~20K |
| Review | ~15K (code diff only — not full codebase) |
| Acceptance | ~10K |
| Gate | ~5K (report headers only) |

### Auto-compact at 75% context usage

Performance degrades sharply once context exceeds ~80%. The framework enforces a **75% threshold** — at every wave boundary, the orchestrator checks context pressure:

1. **Checkpoint** — wave checkpoint is already written (happens at every boundary)
2. **Write compact context** — `agent_state/phases/N/checkpoints/compact-context.md` captures completed waves, decisions, current state, and next steps
3. **Run `/compact`** — Claude Code's built-in context compression clears scrollback
4. **Resume inline** — reads `compact-context.md` + `phase_context.md` and continues to the next wave without breaking the session

```
Wave 3 complete → checkpoint written → context at 78%
⚡ Context at 75% — compacting before Wave 4. Resuming inline.
→ /compact runs → reads compact-context.md → continues Wave 4
```

This is automatic and invisible — no manual `/pause` or session restart needed. The 5% gap before 80% is the safety margin.

### If the window fills despite compaction

Auto-checkpoints at every wave boundary mean `/resume` can always reconstruct state:

```
/startup/resume                           ← checks auto-checkpoints first, then explicit sessions
```

For explicit saves, use `/startup/pause`:

```
/startup/pause --reason="context limit"   ← saves phase, step, completed items, blockers
```

Then in a new conversation:
```
/startup/resume                           ← restores from checkpoint or pause snapshot
```

Or use the lightweight approach — all state is in `agent_state/phases/N/`:
```
/startup/status          ← shows exactly where you stopped
/startup/develop --phase=N   ← resumes from last incomplete step
```

For named threads (multiple paused sessions):
```
/startup/pause --thread=auth-refactor
/startup/pause --thread=phase-3-ui
/startup/resume --list                    ← shows all paused sessions
/startup/resume --thread=auth-refactor    ← resumes specific thread
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

This guide walks you through the system incrementally — from your first command to fully autonomous runs. Use as much or as little as you need.

---

### Level 1: Just try it (5 minutes)

The fastest way to see the system in action. One paragraph of requirements is enough.

```bash
# 1. Install (one time)
git clone <this-repo> ~/development/startup-agents
cd ~/development/startup-agents && bash install.sh

# 2. Create a project
bash new-project.sh my-app ~/development
cd ~/development/my-app

# 3. Add ONE requirement file (even a single paragraph works)
cat > requirements/spec.md << 'EOF'
Build a REST API for a task management app.
Users can create, list, update, and delete tasks.
Each task has a title, description, status (todo/in-progress/done), and due date.
Use Go with Chi router and PostgreSQL.
EOF

# 4. Open Claude Code in this directory and run:
/startup/init
```

That's it. `/init` reads your paragraph, interviews you for gaps, creates a structured BRD with numbered requirements (FR-001, FR-002, ...), confirms your tech stack, and generates project-specific agents.

**What you now have:**
```
docs/BRD.md                          ← 30+ numbered requirements extracted from your paragraph
docs/IMPLEMENTATION_GUIDELINES.md    ← confirmed: Go 1.22 / Chi / PostgreSQL / Docker
.claude/agents/generated/            ← 8 agents customized for Go + Chi + PostgreSQL
```

**Next step:** Run `/startup/status` to see what the system recommends.

---

### Level 2: Build one phase (30-60 minutes)

Now build the first feature set. The system breaks your BRD into phases automatically.

```
/startup/plan               ← creates specs for Phase 1 (auto-detected)
```

This produces:
- Technical specs (TRDs) for each component
- Typed data contracts (TypeScript interfaces for every endpoint)
- UI specs (if frontend enabled)
- Goal verification: "will these specs achieve the phase goal?"

Review the specs in `docs/design/phases/1/specs/`. Then:

```
/startup/develop            ← implements Phase 1 end-to-end
```

This runs the full pipeline: audit → code → tests → review → acceptance → gate. Takes 15-40 minutes depending on phase size. You don't need to do anything — watch the progress.

**What happens inside `/develop`:**
```
Wave 1:  Database schema + migrations
Wave 2:  Backend services → API handlers (sequential — API needs service interfaces)
Wave 3:  UI components (if frontend enabled)
Wave 4:  Unit tests + integration tests (parallel)
Wave 5:  Code review (style + architecture + security) + acceptance tests (parallel)
Wave 6:  13-point quality gate — all must pass to proceed
```

**If the gate passes:** `agent_state/phases/1/gate.passed` is written. You're done with Phase 1.

**If the gate blocks:** The system tells you exactly what failed and how to fix it. Fix it, then re-run `/startup/develop`.

---

### Level 3: Add pre-planning rigor (recommended for complex projects)

Before planning, surface assumptions and research decisions. This prevents "assumption bugs" — the #1 cause of mid-implementation rework.

```
/startup/map                ← maps the codebase (skip for greenfield projects)
/startup/discuss            ← surfaces assumptions + researches decisions
/startup/plan               ← plans with full context
/startup/develop            ← implements with confidence
```

**What `/discuss` does:**

1. **Assumption analysis** — An opus-tier agent reads your codebase + BRD and identifies what the planner would ASSUME silently. Each assumption is classified:
   - **CONFIRMED** — directly observed with file:line reference
   - **DEDUCED** — logical inference, chain of evidence shown
   - **HYPOTHESIZED** — plausible but unverified, states what would confirm it

2. **Decision research** — For each open question or low-confidence assumption, a parallel agent researches options and produces a comparison table:
   ```
   | Option | Pros | Cons | Risk | Effort | Recommendation |
   ```

3. **Risk assessment** — Technical, integration, data, performance, and security risks ranked by impact × likelihood

You review the output, confirm or override decisions, then `/plan` uses your confirmed decisions instead of guessing.

**Use `--auto` to skip the interactive review** (agents pick recommended defaults):
```
/startup/discuss --auto     ← auto-resolves all decisions, logs everything
/startup/plan               ← reads DISCUSSION.md automatically
```

**What `/map` does:**

4 parallel agents explore the codebase with different lenses:
```
agent_state/codebase/
├── tech-stack.md      ← languages, frameworks, build tools, dependency counts
├── architecture.md    ← module boundaries, API surface, data models, cross-cutting concerns
├── quality.md         ← test coverage, code patterns, tech debt indicators
└── concerns.md        ← security, performance, reliability, maintainability issues
```

This knowledge base persists across sessions. All planning agents read it instead of re-exploring the codebase each time. Use `--incremental` after Phase 1 to update only what changed.

---

### Level 4: Full manual workflow (maximum control)

The complete step-by-step workflow for each phase:

```
# ── Phase N ───────────────────────────────────────────────

# 1. Update codebase knowledge (skip for Phase 1 of greenfield)
/startup/map --incremental

# 2. Surface assumptions and research decisions
/startup/discuss --phase=N

# 3. Generate specs with goal verification
/startup/plan --phase=N

# 4. Review specs (optional but recommended)
#    Check: docs/design/phases/N/specs/
#    Check: agent_state/phases/N/plan_check.md (goal verification)

# 5. Implement end-to-end
/startup/develop --phase=N

# 6. Gate passes → Phase N complete!
#    Repeat from step 1 for Phase N+1
```

**Between phases — optional quality commands:**
```
/startup/test --phase=N          ← re-run tests independently
/startup/review                  ← standalone code review
/startup/optimize                ← dead code removal + performance
/startup/benchmark --save-baseline  ← capture performance metrics
```

**After all phases:**
```
/startup/accept                  ← global acceptance testing (all personas, all use cases)
/startup/deploy --target=local   ← deploy locally
```

---

### Level 5: Fully autonomous (hands-off)

Let the system build everything. You review once, then walk away.

```
/startup/autonomous
```

**What happens:**

```
Phase 0:   Environment pre-flight (Docker, ports, tools)
Phase 1:   /init --auto         Creates BRD + agents (auto-researches all gaps)
Phase 1b:  /map                 Codebase knowledge base
Phase 2:   /discuss --auto      Surfaces assumptions (auto-resolved)
Phase 2b:  /plan --auto         Specs + goal verification

     ┌─────────────────────────────────────────────────────────┐
     │  🛑 HUMAN CHECKPOINT — the ONE required interaction     │
     │                                                         │
     │  Review:                                                │
     │  • LOW confidence decisions (need your input)           │
     │  • HYPOTHESIZED assumptions (unverified)                │
     │  • Phase 1 scope + tech stack                           │
     │                                                         │
     │  Type "go" to approve, or describe changes              │
     └─────────────────────────────────────────────────────────┘

Phase 4:   /develop --auto      Implements Phase 1
Phase 5:   For each remaining phase:
             /map --incremental → /discuss --auto → /plan --auto → /develop --auto
Phase 6:   /accept --auto       Global validation
Phase 7:   Final report + /health integrity check
```

**Safety guarantees in autonomous mode:**
- Security decisions NEVER auto-resolve permissively (uses hardened defaults)
- Escalation circuit breaker: >10 auto-resolutions per phase → exits auto mode
- Every auto-decision is logged to `agent_state/autonomous/auto-resolved.jsonl`
- Force-gated phases are fully documented (what failed, why it was forced)
- Git branch per phase with immutable tags at each boundary

**Customize autonomous runs:**
```
/startup/autonomous --confirm_each_phase    ← checkpoint before EVERY phase
/startup/autonomous --max_phases=2          ← only build first 2 phases
/startup/autonomous --skip_init             ← reuse existing BRD
/startup/autonomous --resume                ← continue from last checkpoint
```

---

### Session management

**Save and resume work across conversations:**
```
/startup/pause                              ← saves phase, step, decisions, blockers
/startup/pause --reason="end of day"        ← with reason
/startup/pause --thread=auth-work           ← named thread (multiple paused contexts)

# In a new conversation:
/startup/resume                             ← restores latest session
/startup/resume --list                      ← shows all paused sessions
/startup/resume --thread=auth-work          ← resumes specific thread
```

**Context window fills up?** Same flow:
```
/startup/pause --reason="context limit"
# Start new conversation
/startup/resume
```

---

### Parallel workstreams

Work on independent features concurrently:

```
# Create workstreams (each gets its own git branch)
/startup/workstream create --name=auth --phase=3 --description="Authentication system"
/startup/workstream create --name=reports --phase=4 --description="Reporting dashboard"

# Work on auth
/startup/workstream switch --name=auth
/startup/discuss --phase=3
/startup/plan --phase=3
/startup/develop --phase=3

# Switch to reports (auth progress is saved automatically)
/startup/workstream switch --name=reports
/startup/discuss --phase=4
/startup/plan --phase=4
/startup/develop --phase=4

# Check progress across all workstreams
/startup/workstream list
# Output:
#   ● auth      (active)  Phase 3   branch: workstream/auth      progress: 100%
#   ○ reports   (paused)  Phase 4   branch: workstream/reports   progress: 60%

# Merge completed auth back to main (runs integration check + regression tests)
/startup/workstream merge --name=auth
```

**When to use workstreams:** Features that don't share components. If Phase 3 and Phase 4 both modify the same service, use sequential phases instead.

---

### Starting with deep research

For new products or unfamiliar markets:

```
# 1. Research first (6 parallel agents, 15-30 minutes)
/startup/research --domain="XDR/EDR cybersecurity"

# Produces:
#   requirements/research/01-vendors.md
#   requirements/research/02-market-dynamics.md
#   requirements/research/03-vendor-leaders.md
#   requirements/research/07-capability-matrix.md
#   requirements/research/08b-edge-cases.md
#   requirements/research/contradiction-audit.md
#   ... (12+ documents)

# 2. Review research, adjust priorities

# 3. Build (research feeds into /init automatically)
/startup/autonomous
# OR manually: /startup/init → /startup/plan → /startup/develop
```

---

### When things go wrong

| Situation | What to run | What it does |
|-----------|------------|-------------|
| Pipeline failed mid-run | `/startup/forensics` | Timeline reconstruction → root cause → recovery steps |
| Suspect corrupted state | `/startup/health` | Checks manifest integrity, gate consistency, file references |
| Auto-repair state issues | `/startup/health --fix` | Fixes orphaned reports, dead refs, incomplete logs |
| Bug in the built app | `/startup/diagnose --symptom="..."` | Traces symptom → spec → implementation → root cause |
| Quick fix needed | `/startup/hotfix --phase=N --component=auth` | Scoped fix → scoped test → scoped review → merge |
| Need to undo a deploy | `/startup/rollback --target=local` | Reverses migrations, redeploys previous build |
| Phase needs a redo | `/startup/reset-phase --phase=N` | Archives state, creates safety tag, prepares clean re-run |
| Flaky test blocking gate | `/startup/develop --force_gate` | Forces gate with full logging (tracked in manifest) |

---

### Quick reference — what to run when

| I want to... | Run this |
|-------------|----------|
| Build everything hands-off | `/startup/autonomous` |
| Understand a competitor's product deeply | `/startup/product-workflows --product="Trellix DLP"` |
| Research a market first | `/startup/research --domain="..."` |
| Start a new project | `bash new-project.sh my-app` → `/startup/init` |
| Understand codebase before planning | `/startup/map` |
| Surface assumptions before planning | `/startup/discuss` |
| Build the next feature set | `/startup/discuss` → `/startup/plan` → `/startup/develop` |
| See where I am | `/startup/status` |
| Save progress for later | `/startup/pause` → (new session) → `/startup/resume` |
| Work on two features in parallel | `/startup/workstream create --name=feature-a` |
| Run tests without building | `/startup/test --phase=N` |
| Review code quality | `/startup/review` |
| Optimize code | `/startup/optimize` |
| Deploy | `/startup/deploy --target=local` |
| Validate the full product | `/startup/accept` |
| Fix a bug fast | `/startup/hotfix --phase=N --component=auth` |
| Investigate a bug | `/startup/diagnose --symptom="..."` |
| Check pipeline health | `/startup/health` |
| Investigate a failure | `/startup/forensics` |
| Track performance | `/startup/benchmark --save-baseline` |
| Roll back a deploy | `/startup/rollback --target=local` |
| Add a feature mid-project | `product_manager` agent → `/startup/plan` |
| Re-do a phase | `/startup/reset-phase --phase=N` → `/startup/develop` |

---

### What you DON'T need to do

- **Don't write BRD.md** — `/init` creates it from your requirements
- **Don't pick which agent to use** — commands select the right agents automatically
- **Don't manage phases manually** — commands auto-detect the current phase
- **Don't write test data** — agents generate it (or use yours if you provide it)
- **Don't configure skill packs** — `agent_factory` assigns them based on your tech stack
- **Don't worry about context windows** — use `/pause` and `/resume` when they fill up
- **Don't manually track decisions** — `/discuss` logs all assumptions and decisions to files
- **Don't investigate failures manually** — `/forensics` reconstructs the timeline for you

### How the pipeline protects your code

Every phase goes through 13 quality checks before it can pass:

```
Your code
  ↓
Spec compliance               ← did you build what the spec says?
Unit tests                    ← does each function work?
Integration tests             ← do services + DB work together?
E2E tests                     ← does the full user workflow work?
Cross-phase regression        ← did new code break old features?
Spec ↔ Implementation check   ← is everything from the spec built?
Spec ↔ Test check             ← is every behavior tested?
Code optimization             ← dead code removed, code simplified
Style review                  ← idiomatic, clean, consistent
Architecture review           ← right patterns, right layers + error response shapes
Security review               ← no OWASP vulnerabilities
SAST scan                     ← automated static analysis (semgrep/govulncheck/bandit)
Acceptance tests              ← works for real users, real scenarios (browser-based for UI)
  ↓
Phase gate PASSED ✅
```

If any check fails, the gate blocks and tells you exactly what to fix.

### Commands at a glance

```
Pipeline (24 commands total):
/startup/product-workflows  Product workflow intelligence (docs + videos + APIs).
/startup/research     Deep market & product research. Vendors, capabilities, moats.
/startup/init         One-time project setup. Creates BRD + agents from requirements.
/startup/map          Codebase knowledge base — 4 parallel focus areas.
/startup/discuss      Surface assumptions + research decisions. Run before /plan.
/startup/plan         Plans a phase. Creates specs, data contracts, goal verification.
/startup/develop      Builds a phase end-to-end with parallel review + acceptance.
/startup/autonomous   Full pipeline: map → discuss → plan → develop (all phases).
/startup/accept       Full-product validation after all phases complete.
/startup/deploy       Build and deploy to local, staging, or production.

Session & Workflow:
/startup/pause        Save session state for later resumption.
/startup/resume       Restore paused session and continue working.
/startup/workstream   Manage parallel workstreams (create/switch/merge).

Standalone:
/startup/test         Runs tests standalone. Many flags for targeting specific tiers.
/startup/review       Code review: spec compliance → style + arch + security (parallel).
/startup/optimize     Code cleanup and optimization with before/after comparison.
/startup/benchmark    Performance tracking with baselines and regression detection.
/startup/status       Where am I? What should I run next?

Issue Resolution:
/startup/hotfix       Fast-track bug fix. Scoped test + scoped review. No full pipeline.
/startup/diagnose     Trace a symptom to root cause. Optional auto-fix.
/startup/rollback     Roll back a deployment. Reverse migrations + redeploy previous build.
/startup/reset-phase  Reset a phase for re-development with state preservation.

Pipeline Diagnostics:
/startup/health       Check pipeline state integrity. Use --fix for auto-repair.
/startup/forensics    Investigate failed pipeline runs. Timeline + root cause + recovery.
```

### Tips

- **Start small.** Your first requirements file can be a single paragraph. `/init` will ask clarifying questions.
- **Check status often.** `/startup/status` always tells you the next action.
- **Trust the gate.** If the gate blocks, read the blocker — it tells you the exact file, line, and fix.
- **Use `--dry_run` for optimize.** See what would change before committing to it.
- **Commit between phases.** Each phase is a natural commit point.
- **Provide seed data for predictable tests.** Drop YAML files into `requirements/test-data/` for deterministic acceptance tests.
- **Add your own skill packs.** Using a framework not in the defaults? Create a `.md` file in `~/.claude/skills/` and re-run `/startup/init --update_agents`.
