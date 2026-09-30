# startup-agents

A reusable AI-agent framework for building software products end-to-end with Claude Code. Drop in your requirements, run three commands, get a production-ready application with tests, code reviews, and acceptance validation at every phase.

---

## How it works

You provide requirements. The agents do the rest — from turning a pitch deck into a structured BRD, through implementation waves, to final acceptance testing against every user persona.

```
requirements/                  ← YOUR INPUT — agents read but never modify this
    ├── feature-spec.md        ← user stories, PRD, pitch deck (any format)
    ├── research/              ← optional: output from /startup:research
    ├── IMPLEMENTATION_GUIDELINES.md  ← optional DRAFT: fill in what you know
    └── test-data/             ← optional: seed data per phase

                ↓ /startup:init reads requirements/, interviews for gaps ↓

docs/                          ← GENERATED OUTPUT — agents write here
    ├── BRD.md                 ← numbered requirements (FR-*, NFR-*) — always generated
    └── IMPLEMENTATION_GUIDELINES.md  ← confirmed tech stack

/startup:research  →  ultra-deep market & product research (optional, before init)
/startup:init      →  BRD + agents from requirements
/startup:map       →  persistent codebase knowledge base (4 parallel focus areas)
/startup:discuss   →  surface assumptions + research decisions (before /plan)
/startup:plan      →  specs + data-contracts.md + UI specs + goal verification per phase
/startup:design    →  UI/mobile design contract per phase (optionally rendered in Google Stitch), behind a blocking design gate
/startup:develop   →  implement + test + review + gate per phase
/startup:accept    →  local deploy + health gate + full-product validation + release notes
/startup:deploy    →  build + migrate + deploy + health validation

OR: /startup:autonomous  →  all of the above end-to-end with one human checkpoint

Session management:
/startup:pause     →  save session state for later resumption
/startup:resume    →  restore paused session and continue

Parallel work:
/startup:workstream →  manage concurrent feature branches (create, switch, merge)

Issue resolution (use anytime):
/startup:hotfix    →  scoped fix + scoped test + scoped review (bypasses full pipeline)
/startup:diagnose  →  trace symptom to root cause, optional auto-fix
/startup:benchmark →  performance baselines + regression detection
/startup:rollback  →  reverse deployment to previous known-good state

Design & demo:
/startup:stitch    →  Google Stitch workbench (init | generate | variants | edit | theme | sync | status)
/startup:ui-audit  →  audit every built page vs design standards + its Stitch baseline
/startup:demo      →  write, stand up and rehearse a stakeholder demo of a completed phase

Pipeline diagnostics:
/startup:health    →  diagnose agent_state integrity + auto-repair
/startup:forensics →  post-mortem analysis of failed pipeline runs
```

> **Command names.** `install.sh` copies the commands into `~/.claude/commands/startup/`, so Claude Code exposes them as `/startup:<name>` (for example `/startup:develop`). Inside this framework repo itself they also resolve without the prefix (`/develop`), which is how `CLAUDE.md` and the command files refer to them.

> **Convention:** `requirements/` is read-only input. `docs/` is generated output. Never write `BRD.md` by hand — always run `/startup:init`. The `IMPLEMENTATION_GUIDELINES.md` in `requirements/` is your optional draft; `/init` produces the authoritative confirmed version in `docs/`.

---

## What's new (2026-09)

| Area | Change | Guide |
|------|--------|-------|
| **Kubernetes dev/qa on a Lima lab cluster** | `/startup:deploy --target=dev\|qa`: per-app namespaces `<app>-dev`/`<app>-qa` on k3s in Lima (one or two Macs), images promoted to qa **by digest**, migrate/seed Jobs, `env-reset.sh`, `--rollback`, evidence for the phase gate and `/accept`; one-command cluster bootstrap (`cluster-up.sh`); live e2e `tests/k8s-e2e.sh` | [lima-k8s-lab skill](.claude/skills/infrastructure/lima-k8s-lab.md) |
| **Unattended permissions, prod out of reach** | `sdlc-guard` PreToolUse hook + PATH shims (pinned cluster/credential, writable namespaces by pattern, secrets never read, CLAUDE.md ask-list), RBAC-bounded agent identity, auto-mode settings you apply with one reviewed script, optional root-owned managed layer | [docs/PERMISSIONS_GUIDE.md](docs/PERMISSIONS_GUIDE.md) |
| **React Native mobile (iOS + Android)** | New generated agents `mobile_developer` and `mobile_test_agent`; new core agents `mobile_e2e_orchestrator` (device matrix runner) and `mobile_platform_auditor`; Maestro (default), Detox and Appium skill packs; TC categories `TC-MCMP/MINT/ME2E/MPLT/MA11Y/MVIS/MPERF`; `/startup:test --mobile [--platform=ios\|android]`; IMPLEMENTATION_GUIDELINES §24 Mobile; `mobile.yml` CI guidance | [docs/MOBILE_GUIDE.md](docs/MOBILE_GUIDE.md) |
| **Google Stitch design** | `/startup:stitch` workbench; `/startup:design --source=stitch` fixed (real MCP probe, design-system Path A/B, `deviceType` on every call, `edit_screens` in the design-gate BLOCK loop, mobile-only projects included); `docs/design/stitch.json` holds the Stitch baseline for every page | [docs/STITCH_DESIGN_GUIDE.md](docs/STITCH_DESIGN_GUIDE.md) |
| **UI standards audit** | New core agent `ui_standards_auditor` and `/startup:ui-audit`: every built web and React Native page is audited against the design standards and its Stitch baseline | [docs/STITCH_DESIGN_GUIDE.md](docs/STITCH_DESIGN_GUIDE.md#7-auditing-built-pages--startupui-audit) |
| **`/startup:autonomous` no longer stalls** | Sub-commands run through the Skill tool; their "▶ Next" hints are ignored under autonomous; `/design` runs after `/plan`; every sub-command honours auto mode; a Stop hook keeps the turn going while `run.json` says `running`; resume by step id | [docs/AUTONOMOUS_GUIDE.md](docs/AUTONOMOUS_GUIDE.md) |
| **`/develop` wave execution** | Wave 2A sequenced named spawns (database → migration → backend → api → ui ∥ mobile); Wave 3 per-tier named agents; Wave 3v `test_runner` independently re-runs suites and cross-checks writer counts; Wave 4 conditional reviewers driven by the roster | [Implementation waves](#implementation-waves) |
| **`/startup:demo`** | New command: `demo_documenter` → `demo_executor` → `demo_validator` | [Commands](#commands) |
| **Dependency graph** | `downstream:` is now derived by `.claude/agents/_sync-deps.py`; `tests/dependency-graph.test.sh` checks agents ↔ commands ↔ skills in CI | [Contributing](#contributing-to-the-framework) |
| **Fixes** | TC-ID scanners now match `TC-[A-Z0-9]+` (they missed `TC-E2E-*`/`TC-A11Y-*`) and scan `e2e/`, `apps/`, `mobile/` incl. Maestro YAML; generated agents keep the bare role as `name:`; report names unified (`quality_gate.md`; reconciliation reports in `agent_state/reconciliation/phase-N/`); `product_api_researcher` wired into `/product-workflows` Step 2b; every agent loads at least one skill pack | — |

---

## Core Concepts

The framework has four building blocks. Understanding how they connect is the key to using (and extending) the system.

| Concept | What it is | Where it lives | Example |
|---------|-----------|----------------|---------|
| **Command** | User-facing entry point. You invoke these. Each command orchestrates a sequence of agents. | `.claude/commands/*.md` | `/startup:develop`, `/startup:review` |
| **Pipeline Step** | A numbered step inside a command. Steps run sequentially; some steps run agents in parallel. | Defined inside command `.md` files | Step 4 (Review) inside `/startup:develop` |
| **Agent** | The worker that does the actual job. Reads inputs, loads skill packs, produces code or reports. | `.claude/agents/core/*.md` (universal) and `.claude/agents/generated/*.md` (project-specific) | `code_reviewer_I`, `api_developer` |
| **Skill Pack** | Static knowledge file. Contains idiomatic patterns, conventions, and anti-patterns for a specific technology. Agents load these as context before executing. | `.claude/skills/**/*.md` | `go.md`, `react.md`, `testify.md` |

### How they connect

```
COMMAND                    PIPELINE STEPS              AGENTS                    SKILL PACKS
(you invoke)               (inside the command)        (do the work)             (domain knowledge)
─────────────              ──────────────────          ─────────────             ──────────────────
/startup:develop    ─┬──→  Step 0 Orient
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

/startup:review     ─┬──→  Step 1 Style         ──→  code_reviewer_I      ←──  go.md, chi.md
                     ├──→  Step 2 Architecture   ──→  code_reviewer_II     ←──  go.md, chi.md, postgresql.md
                     └──→  Step 3 Security       ──→  security_reviewer    ←──  go.md, security-owasp.md
```

**The flow:** You invoke a **command** → the command runs **pipeline steps** in order → each step spawns **agents** → each agent loads its **skill packs** for technology-specific knowledge → the agent reads code/specs, applies skill pack patterns, and produces output.

**Why skill packs matter:** Without `go.md`, the `code_reviewer_I` agent wouldn't know that `var items []Certificate` (nil slice) serializes to JSON `null` instead of `[]`. Without `testify.md`, the `unit_test_agent` wouldn't know to use `require.NoError` for preconditions and `assert.Equal` for assertions. Skill packs are what make generic agents produce idiomatic, tech-specific output.

### Skill pack loading flow

```
/startup:init
  → agent_factory reads IMPLEMENTATION_GUIDELINES
  → extracts tech profile: { lang: go, framework: chi, db_tech: postgresql, ... }
  → resolves {{PLACEHOLDER}} in agent templates: ".claude/skills/languages/{{LANG}}.md" → ".claude/skills/languages/go.md"
  → writes generated agents with resolved skill_packs paths

/startup:develop (later)
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

The rule board specialists (`.claude/agents/rule_board/`, used by the `/rules-board*` commands for vertix security-rule reviews) are project-specific, so they are never installed globally. Add them to the project that needs them:

```bash
bash ~/development/startup-agents/install.sh --rule-board ~/development/vertix
```

### 2. Start a new project

```bash
bash ~/development/startup-agents/new-project.sh my-app ~/development
cd ~/development/my-app
```

Add `--rule-board` to also scaffold the rule board specialists into the new project.

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
/startup:init       ← run once per project
/startup:plan       ← run once per phase (auto-detects next phase)
/startup:design     ← UI / mobile phases: design contract + design gate (after /plan)
/startup:develop    ← run once per phase (auto-detects current phase)
/startup:accept     ← run once after all phases complete
```

---

## Commands

| Command | What it does |
|---------|-------------|
| `/startup:product-workflows` | **NEW** Product workflow intelligence — researches docs, videos, APIs, forums for a named product. Produces screen-by-screen workflows, config schemas, dependency graphs, API coverage matrix, persona flows |
| `/startup:research` | Ultra-deep market & product research — vendors, capabilities, personas, moats. Produces `requirements/research/` that feeds `/init` |
| `/startup:init` | Reads `requirements/`, creates BRD + IMPL_GUIDELINES, generates project-specific agents. Supports `--auto` for autonomous research mode |
| `/startup:map` | **NEW** Analyzes codebase with 4 parallel mapper agents (tech, architecture, quality, concerns). Produces persistent knowledge base in `agent_state/codebase/` |
| `/startup:discuss` | **NEW** Pre-planning context gathering — surfaces assumptions (CONFIRMED/DEDUCED/HYPOTHESIZED), researches gray area decisions, identifies risks. Run before `/plan` |
| `/startup:plan` | Creates TRDs, typed data contracts, component-level UI specs, and **goal-backward verification** per phase. Supports `--auto` |
| `/startup:design` | UI/mobile design contract for a phase — wireframe pair per screen (`.wireframe.html` + `.wireframe.md`), component/API bindings, tokens, `TC-UI-*` — behind the BLOCKING `design_quality_reviewer` gate. `--source=stitch` renders screens in Google Stitch first. Runs after `/plan` |
| `/startup:develop` | Implements phase end-to-end: audit → build checks → code → tests → review + acceptance (parallel) → gate. Supports `--auto`. Executed wave by wave through `/startup:develop-orchestrator` |
| `/startup:develop-orchestrator` | The canonical `/develop` executor: the parent session spawns one named agent per wave step and verifies between waves. Supports `--auto` |
| `/startup:autonomous` | Runs the full pipeline end-to-end — `/init` → `/map` → `/discuss` → `/plan` → `/design` → `/develop` for all phases, then `/accept`. One human checkpoint. Auto-researches all decisions. See [docs/AUTONOMOUS_GUIDE.md](docs/AUTONOMOUS_GUIDE.md) |
| `/startup:accept` | Runs full-product acceptance tests + contract shape assertions after all phases. Supports `--auto` |
| `/startup:test` | Runs tests standalone (unit / integration / e2e / acceptance / performance / system / traceability / mobile) |
| `/startup:stitch` | Google Stitch workbench — `init` (project + house-style design system), `generate`, `variants`, `edit`, `theme`, `sync` (into the wireframe contract, behind the design gate), `status` |
| `/startup:ui-audit` | Audits every page of the running web + React Native UI against the design standards and its Stitch baseline. Report-only by default; `--fix=design\|code\|all`, `--approve=<pages>` |
| `/startup:demo` | Prepares and dry-runs a stakeholder demo of a completed phase (`demo_documenter` → `demo_executor` → `demo_validator`) |
| `/startup:recon` | Two-way reconcile requirements ↔ BRD ↔ TRD ↔ code ↔ tests. Bare = report only; `--fix=code` (spec wins, alias `/converge`); `--fix=docs` (as-built wins, alias `/reconcile`) |
| `/startup:remember` | Records a Tier 0 ground-truth fact in `docs/PROJECT_FACTS.md` that every session and subagent honours |
| `/startup:worklog` | Consolidates every phase's artifacts into one ledger, `docs/WORKLOG.md` |
| `/startup:consolidate` | Off-path memory maintenance — dedup lessons/patterns, audit Tier 0 facts. Non-destructive |
| `/startup:eval` | Runs the framework's own eval suite and compares against a baseline (improve / regress / wash) |
| `/startup:reset-phase` | Archives a phase's state and tags it so the phase can be re-developed cleanly |
| `/startup:review` | Standalone code review: spec compliance → style + architecture + security (parallel) |
| `/startup:optimize` | Standalone code optimization with before/after comparison — dead code, code reduction, performance |
| `/startup:deploy` | Builds, migrates, deploys to local / staging / prod, validates health post-deploy |
| `/startup:status` | Shows phase progress, BRD coverage, open issues, and next recommended action |
| `/startup:pause` | **NEW** Saves session state (phase, step, completed items, blockers, decisions) for later resumption. Supports named threads |
| `/startup:resume` | **NEW** Restores paused session state and routes to the appropriate command to continue. Use `--list` to see all paused sessions |
| `/startup:workstream` | **NEW** Manages parallel workstreams — create, list, switch, status, complete, merge. Enables concurrent work on independent features |
| `/startup:hotfix` | Fast-track bug fix — scoped change → scoped test → scoped review → merge. Bypasses full `/develop` cycle |
| `/startup:diagnose` | Structured bug investigation — traces symptom to root cause through spec ↔ implementation comparison |
| `/startup:benchmark` | Performance tracking — captures metrics per phase, saves baselines, flags regressions >10% |
| `/startup:rollback` | Deployment rollback — reverses migrations, redeploys previous build, validates health |
| `/startup:health` | **NEW** Diagnoses pipeline state integrity — manifest validity, gate consistency, file references, memory hygiene (stale sessions, stale codebase mappings, oversized logs, orphaned debates). Use `--fix` for auto-repair |
| `/startup:forensics` | **NEW** Post-mortem investigation for failed pipeline runs — timeline reconstruction, root cause classification, recovery recommendations |

### Command arguments

**`/startup:research`**
```
--domain="..."    Product domain to research (required, e.g., "XDR/EDR cybersecurity")
--depth=deep      Research depth: quick | deep (default) | ultra
--focus=all       Focus area: vendors | capabilities | technical | personas | moats | all
```

**`/startup:init`**
```
--update_agents   Re-generate project agents only (use after tech stack changes)
--brd_only        Regenerate BRD only
--auto            Auto-research mode — agents research answers instead of asking user
```

**`/startup:plan`**
```
--phase=N         Override phase number (default: auto-detect next unplanned)
--ui_only         Regenerate UI specs only
--verify_only     Verify existing specs against BRD — no new generation
--auto            Auto-assign FR-* to phases by dependency analysis
```

**`/startup:develop`**
```
--phase=N         Override phase number (default: auto-detect from gate state)
--audit_only      Gap report only — no implementation changes
--test_only       Run tests only — no implementation changes
--force_gate      Force gate to pass with failures (logged as gate_override in manifest)
--auto            Autonomous mode — auto-resolve escalations, auto-fix gate failures
--candidates=N    Build N (2–3) independent candidate implementations and pick a winner (expensive; opt-in)
```

**`/startup:design`**
```
--phase=N         Phase to design (default: auto-detect)
--source=stitch   Render screens in Google Stitch, then normalize into the same wireframe contract
                  (falls back to the pure-agent path if the Stitch MCP is unavailable)
--screen=NAME     Regenerate a single screen
--auto            No prompts; a BLOCK verdict auto-fixes (max 2 cycles), then downgrades to WARN
```

**`/startup:stitch`**
```
<action>          init | generate | variants | edit | theme | sync | status
--phase=N         Phase whose screens to work on (default: current phase)
--screen=NAME     One screen (wireframe base name); omit on generate/sync to process every in-scope screen
--device=TYPE     DESKTOP | MOBILE | TABLET (default: MOBILE for React Native, DESKTOP for web)
--prompt="…"      edit / variants: the change or direction (edit after a gate BLOCK: omit to use the reviewer's fix list)
--count=N         variants: 1-5 (default 3)
--range=R         variants: REFINE | EXPLORE | REIMAGINE (default EXPLORE)
```

**`/startup:ui-audit`**
```
--fix=MODE        none (default, report only) | design | code | all
--app=APP         web | mobile | all (default: every enabled app)
--page=ROUTE      Restrict to one route (default: every page)
--approve=KEYS    Approve 'reconstructed' Stitch baselines (recorded in docs/DECISIONS.md)
```

**`/startup:demo`**
```
--phase=N         Phase to demo (default: latest phase with gate.passed)
--validate-only   Re-run setup + validation of the existing docs/demos/phase-N/demo-script.md
```

**`/startup:accept`**
```
--persona=NAME    One persona only
--use_case=FR-ID  One use case only
--reseed          Force re-seed
--auto            No prompts (set by /autonomous)
--force_accept    Proceed past a failing cross-phase regression with a logged NOT-READY waiver
```

**`/startup:product-workflows`**
```
--product="..."   Product name (required, e.g., "Trellix DLP", "CrowdStrike Falcon")
--capabilities="…" Comma-separated list (omit to discover and document FULL system)
--screenshots=DIR  Path to screenshot directory for visual analysis
--depth=standard  Research depth: quick | standard | deep (adds video + community analysis)
--version="..."   Target product version (e.g., "11.x")
--output=DIR      Output directory (default: docs/product-workflows)
```

**`/startup:discuss`**
```
--phase=N         Phase to discuss (default: auto-detect next unplanned)
--auto            Skip interactive questions — use recommended defaults, log all decisions
--focus=all       Focus: assumptions | risks | decisions | all
```

**`/startup:map`**
```
--focus=all       Focus: tech | architecture | quality | concerns | strategy | all
--incremental     Only re-map files changed since last mapping
--phase=N         Scope mapping to components relevant to a specific phase
```

**`/startup:autonomous`**
```
--confirm_each_phase   Pause for human review before EACH phase (default: Phase 1 only)
--resume               Resume from agent_state/autonomous/run.json (next_step)
--skip_init            Use existing BRD + IMPL_GUIDELINES
--max_phases=N         Limit to N phases
```

**`/startup:pause`**
```
--phase=N         Phase being worked on (auto-detected)
--reason="..."    Why work is being paused
--thread=NAME     Named thread for this work (enables multiple paused contexts)
```

**`/startup:resume`**
```
--thread=NAME     Named thread to resume (default: latest session)
--list            List all paused sessions instead of resuming
```

**`/startup:workstream`**
```
--action=ACTION   create | list | switch | status | complete | merge (required)
--name=NAME       Workstream name (required for create/switch/complete/merge)
--phase=N         Phase(s) this workstream covers (comma-separated)
--description="…" Workstream description (for create)
```

**`/startup:health`**
```
--fix             Attempt automatic repair of detected issues
--phase=N         Check specific phase only
--verbose         Show detailed results including passing checks
```

**`/startup:forensics`**
```
--phase=N         Phase to investigate (default: most recently failed)
--command=CMD     Which command failed: plan | develop | test | review | deploy
--depth=standard  Investigation depth: quick | standard | deep
```

**`/startup:test`**
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
--traceability    TC-* ID inventory: spec IDs vs test annotations
--mobile          React Native tiers: Jest+RNTL (test_runner) + device flows on iOS simulator
                  and Android emulator (mobile_e2e_orchestrator)
--platform=P      With --mobile: ios | android (default both; a single-platform run never satisfies a gate)
```

**`/startup:optimize`**
```
--phase=N         Target phase (default: auto-detect latest completed)
--backend_only    Optimize backend only — skip UI
--ui_only         Optimize UI only — skip backend
--dry_run         Show what WOULD change without modifying code
--aggressive      Include MEDIUM-confidence dead code removal
```

**`/startup:deploy`**
```
--target=local|staging|prod   (default: local)
--dry_run                     Show plan without deploying
```

**`/startup:hotfix`**
```
--phase=N         Phase containing the bug (required)
--component=NAME  Component to fix (e.g. auth, users)
--description="…" Bug description for commit message
--security        Route through security_reviewer instead of code_reviewer_I
--deploy          Fast-track to /deploy after merge
```

**`/startup:diagnose`**
```
--symptom="…"     What's broken (required, e.g. "GET /users returns 500")
--phase=N         Phase to investigate (default: auto-detect)
--component=NAME  Narrow investigation to specific component
--fix             Auto-apply recommended fix after diagnosis
```

**`/startup:benchmark`**
```
--phase=N           Target phase (default: latest completed)
--save-baseline     Save results as the baseline for this phase
--compare           Compare against previous baseline, flag regressions
--endpoints="…"     Test specific endpoints only (comma-separated)
```

**`/startup:rollback`**
```
--target=local|staging|prod   Environment to roll back (required)
--confirm                     Required for production rollback
```

---

## The SDLC pipeline

`/startup:develop` runs a multi-step pipeline per phase. The step view below is the logical pipeline; the executed form is the wave sequence in [Implementation waves](#implementation-waves), run by `/startup:develop-orchestrator`.

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

Before any of these are evaluated, the gate runs `.claude/hooks/verify-gate.sh`: every agent named in `agent_state/phases/N/roster.json` must have a `completed` line in `execution.jsonl`, and each completed agent's report must exist and not be a stub. Conditional agents (mobile, accessibility, UI standards, migration safety, breaking change, tenant isolation) add their reports to the required set when they are in the roster; mobile phases also need device results on **both** iOS and Android.

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
| **Model and effort routing** | `model-routing.md` | All agents run on Claude Opus 5.5 at their frontmatter `effort`; Fable only for retries after a failure and cross-model gate verification. The phase complexity score feeds workflow depth and candidate selection |
| **Structured lessons** | `structured-lessons.md` | Post-Gate — lessons indexed by category/tag with confidence levels, queryable by downstream agents |

### Implementation waves

`/startup:develop-orchestrator` is the canonical executor: the parent session runs each wave as separate, **named** agent spawns (`subagent_type` = the agent's role) and verifies the outputs between waves. The wave numbers below match that file.

```
Wave 0    Scale the workflow depth (trivial / small / standard / platform)
Wave 0b   Write roster.json — the agents this phase MUST run (real agent names)
Wave 1    backend_audit_agent [+ ui_audit_agent]                → audit_report.md
Wave 2A   Single implementation, sequenced (each step reads the previous step's output):
            2A.1 database_agent    → docs/design/database.md
            2A.2 migration_agent   → migrations/
            2A.3 backend_developer → services / repositories
            2A.4 api_developer     → handlers + specs/api-contracts.md (the contract every UI/mobile test mocks from)
            2A.5 ui_developer      (web; needs 2A.4)   ∥   2A.6 mobile_developer (React Native; needs 2A.4)
Wave 2B   Candidate selection instead of 2A for hard phases (N implementations → solution_selector)
Wave 3    Tests — separate named agent per tier, parallel tracks:
            unit_test_agent · integration_test_agent
            ui_test_agent → e2e_orchestrator                 (web; non-web projects run e2e_orchestrator alone)
            mobile_test_agent → mobile_e2e_orchestrator      (React Native, iOS AND Android)
Wave 3v   test_runner — independent re-run of the Node tiers; any writer-vs-independent count mismatch is BLOCKING
Wave 3.5  Local deploy + health check (web/API: build → migrate → start → /health; mobile: build, install, cold-launch)
Wave 4    Review + reconcile + acceptance, one named agent each, in parallel:
            Track A  code_reviewer_I · code_reviewer_II · security_reviewer · dependency_scanner · code_quality_verifier
                     + conditional: tenant_isolation_verifier · accessibility_auditor · mobile_platform_auditor ·
                       ui_standards_auditor · migration_safety_reviewer · breaking_change_reviewer
            Track C  spec_impl_reconciler · spec_test_reconciler
            Track B  acceptance_test_agent (against the live app; RN persona flows on both platforms)
Wave 5    Collective feedback + fix loop (adaptive replanning, re-run affected tiers)
Wave 6    Gate — verify-gate.sh: roster.required ⊆ completed entries in execution.jsonl, reports non-stub
```

**Roster-driven report checks.** Conditional agents run only when Wave 0b puts them in `roster.json` (web UI → `accessibility_auditor`; mobile screens changed → the four mobile agents; UI or mobile changed → `ui_standards_auditor`; migrations → `migration_safety_reviewer`; cross-phase contract change → `breaking_change_reviewer`; multi-tenant → `tenant_isolation_verifier`). The Wave 3 and Wave 4 verification blocks require exactly the reports of the agents in the roster, so a skipped reviewer is either an explicit, documented omission or a gate failure.

**Report locations.** Test and review reports go to `agent_state/phases/N/reports/` (the code-quality report is `quality_gate.md`); reconciliation reports (`specs_vs_impl.md`, `specs_vs_tests.md`, `test_case_inventory.md`, `brd_vs_specs.md`) go to `agent_state/reconciliation/phase-N/`, where `/plan`, `/test`, `/recon` and `pipeline_completeness_agent` read them.

**Key dependency:** api_developer reads backend_developer's manifest to know which response helper to use (`RespondList` for list methods, `RespondOne` for single methods), and publishes `api-contracts.md` for the UI and mobile steps. This is why Wave 2A is sequenced, not parallel.

### Auto-checkpoints

After each wave completes, the orchestrator writes a lightweight checkpoint to `agent_state/phases/N/checkpoints/wave-N.json`. If context resets mid-pipeline (no explicit `/pause`), `/resume` detects these checkpoints and routes you to the right wave:

```
/startup:resume
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
│       ├── stitch.json                ← Google Stitch project, design system, screens + all-pages baseline map
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
│   │       ├── specs_vs_tests.md
│   │       └── test_case_inventory.md
│   ├── patterns.md                        ← ACCUMULATED cross-phase patterns (what works / what to avoid)
│   ├── autonomous/                        ← GENERATED by /autonomous
│   │   ├── run.json                       ← run state read by the Stop hook (status, phase, step, next_step)
│   │   ├── checkpoint.json · approved.json · auto-resolved.jsonl
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
│           ├── roster.json            ← agents this phase MUST run (Wave 0b)
│           ├── execution.jsonl        ← one "completed" line per agent that ran (checked by verify-gate.sh)
│           └── reports/
│               ├── unit_tests.md
│               ├── integration_tests.md
│               ├── ui_test_results.md          ← web UI component/integration tests (UI phases)
│               ├── e2e_results.md
│               ├── mobile_test_results.md      ← React Native Jest/RNTL (mobile phases)
│               ├── mobile_e2e_results.md/.json ← device flows per platform (mobile phases)
│               ├── test_results.md/.json       ← Wave 3v independent re-run (test_runner)
│               ├── regression_check.md         ← cross-phase regression (Phase > 1)
│               ├── code_optimization.md        ← backend dead code + optimization
│               ├── ui_code_optimization.md     ← UI dead code + optimization (UI phases)
│               ├── code_review_I.md
│               ├── code_review_II.md
│               ├── security_review.md
│               ├── dependency_scan.md          ← CVE/outdated/license scan
│               ├── quality_gate.md             ← code_quality_verifier
│               ├── accessibility_audit.md      ← conditional reviewers: only when in the roster
│               ├── mobile_platform_audit.md
│               ├── ui_standards_audit.md/.json + ui_standards_stitch_requests.json
│               ├── migration_safety.md
│               ├── breaking_change_review.md
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
    ├── settings.json                  ← hooks: SessionStart fact injection; Stop = verify-gate + autonomous-continue
    ├── hooks/                         ← copied in by new-project.sh or /autonomous Step 0
    └── agents/
        └── generated/                 ← Project-specific agents (written by /init)
            ├── go_backend_developer_myapp.md
            ├── go_api_developer_myapp.md
            ├── postgres_database_agent_myapp.md
            └── ...
```

Generated file names carry the project suffix, but each generated agent's `name:` stays the bare role (`backend_developer`, `unit_test_agent`, `mobile_test_agent`, …). That one name is the `subagent_type` the orchestrator spawns, the `"agent"` written to `execution.jsonl`, and the entry in `roster.json`, so the three always agree.

---

## Agents

### Core agents (always available)

These live in `~/.claude/agents/` after install. No project setup required. The repo ships **69 core agents** (`.claude/agents/core/`) and **10 generation templates** (`.claude/agents/templates/`); the tables below cover the main ones, and [.claude/agents/INVENTORY.md](.claude/agents/INVENTORY.md) is the complete index with inputs, outputs and effort levels.

#### Requirements & Planning

| Agent | Role | Model |
|-------|------|-------|
| `brd_agent` | Reads `requirements/`, extracts and classifies requirements, interviews for gaps, produces `docs/BRD.md` | opus/medium |
| `impl_guidelines_agent` | Evaluates draft IMPLEMENTATION_GUIDELINES, asks targeted clarifying questions, produces confirmed `docs/IMPLEMENTATION_GUIDELINES.md` | opus/medium |
| `project_planner` | Assigns FR-* requirements to phases, defines exit criteria and implementation waves | opus/medium |
| `spec_writer` | Generates TRD for one component/flow — interface contracts, data model, 10+ edge cases, test coverage requirements | opus/medium |
| `agent_factory` | Reads confirmed IMPLEMENTATION_GUIDELINES, populates agent templates, writes project-specific agents to `.claude/agents/generated/` | opus/medium |
| `product_manager` | Handles change requests and BRD amendments after `/init` — invoke manually | opus/medium |
| `phase_assumptions_analyzer` | **NEW** Deep codebase analysis — surfaces structured assumptions with evidence levels (CONFIRMED/DEDUCED/HYPOTHESIZED) before planning | opus/high |
| `decision_researcher` | **NEW** Researches gray area decisions — produces comparison tables with pros/cons/risk/recommendation for each option | opus/medium |
| `plan_goal_verifier` | **NEW** Goal-backward verification — traces phase goal → specs → components → contracts to verify the plan will achieve its objective | opus/high |

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
| `ux_designer` | Produces wireframe specs — layout, components, API bindings, interactions; normalizes Google Stitch renders into the same wireframe pair; mobile screens get testIDs + Tier 4M TCs | opus/medium |
| `wireframe_generator` | Initial wireframe scaffolding (invoked by `ux_designer`) | opus/low |
| `design_quality_reviewer` | BLOCKING design gate — validates wireframes against 11 quality dimensions (no TBD bindings, loading/error/empty states, accessibility, design-system adherence, …) | opus/medium |
| `spec_verifier` | Confirms all FR-* in scope have spec coverage; all cited IDs exist in BRD | opus/high |
| `adr_agent` | Writes Architecture Decision Records for significant design choices | opus/medium |

#### Implementation (generated per project)

These are created by `agent_factory` from templates during `/init`:

| Template | Generated agent | When |
|----------|----------------|------|
| `backend_developer.tmpl` | `{lang}_backend_developer_{project}.md` | Always |
| `api_developer.tmpl` | `{lang}_api_developer_{project}.md` | Always |
| `database_agent.tmpl` | `{db}_database_agent_{project}.md` | Always |
| `migration_agent.tmpl` | `{db}_migration_agent_{project}.md` | Relational/document DB |
| `unit_test_agent.tmpl` | `{lang}_unit_test_agent_{project}.md` | Always |
| `integration_test_agent.tmpl` | `{lang}_integration_test_agent_{project}.md` | Always |
| `ui_developer.tmpl` | `{ui}_ui_developer_{project}.md` | `frontend.enabled = true` |
| `ui_test_agent.tmpl` | `{ui}_ui_test_agent_{project}.md` | `frontend.enabled = true` |
| `mobile_developer.tmpl` | React Native app developer (iOS + Android) | `mobile.enabled = true` |
| `mobile_test_agent.tmpl` | React Native test writer (Jest + RNTL, device flows) | `mobile.enabled = true` |

Each generated agent is pre-loaded with your project's specific language, framework, ORM, test library, and design conventions. `agent_factory` resolves template placeholders that are not filenames (for example a mock library or a component kit) through a skill-pack resolution table, so every resolved skill path exists. The generated agent's `name:` is always the bare role (see [Project structure](#project-structure)). When `mobile.enabled = true`, the core agents `mobile_e2e_orchestrator` and `mobile_platform_auditor` are also activated for the project.

#### Code Optimization

| Agent | Role | Model | Trigger |
|-------|------|-------|---------|
| `code_optimizer` | Backend dead code removal + code/performance optimization | opus/medium | `/develop` Step 3f (mandatory) |
| `ui_code_optimizer` | UI dead code removal + bundle size/render optimization | opus/medium | `/develop` Step 3f (if frontend enabled) |
| `dependency_scanner` | Scans dependencies for CVEs, outdated packages, license issues | opus/low | `/develop` Step 4 (parallel with review) |

#### Code Review

| Agent | Role | Model |
|-------|------|-------|
| `code_reviewer_I` | Style, idioms, naming, formatting — reads active language skill pack | opus/high |
| `code_reviewer_II` | Architecture, design patterns, constraint compliance | opus/high |
| `security_reviewer` | OWASP top 10, auth/authz, injection, secrets, data exposure | opus/high |
| `code_quality_verifier` | TODOs, stubs, hardcoded secrets, dead imports, debug statements → `quality_gate.md` | opus/high |
| `tenant_isolation_verifier` | Traces tenantID from every handler to every data access (multi-tenant projects) | opus/high |
| `accessibility_auditor` | WCAG 2.1 AA against the built, running web UI (axe, keyboard, contrast, ARIA) | opus/high |
| `ui_standards_auditor` | Every built web + React Native page vs the design standards and its Stitch baseline; emits Stitch requests for missing or flawed baselines | opus/high |
| `mobile_platform_auditor` | React Native iOS/Android conformance: VoiceOver/TalkBack, touch targets, text scaling, permissions, deep links, secure storage, cleartext/ATS, platform parity | opus/high |
| `migration_safety_reviewer` | Adversarial migration review — data loss, irreversible ops, lock risk, rollback | opus/high |
| `breaking_change_reviewer` | Changes that break contracts earlier phases depend on | opus/high |

All Wave 4 reviewers run as separate named agents in parallel; the ones after `security_reviewer` except `code_quality_verifier` are conditional and run when the phase roster includes them.

#### Testing

| Agent | Role | Model | Invoked by |
|-------|------|-------|-----------|
| `e2e_orchestrator` | Runs complete user workflow tests across full stack | opus/medium | `/develop` Wave 3c (after `ui_test_agent` on web), `/test --e2e` |
| `test_runner` | Runs the suites with the project's commands and never edits tests; in Wave 3v it re-runs them independently and fails the wave on any writer-vs-independent count mismatch | opus/low | `/develop` Wave 3v, `/test` |
| `mobile_e2e_orchestrator` | Builds the React Native app, boots the iOS simulator + Android emulator matrix, runs every device flow on both platforms with evidence | opus/medium | `/develop` Wave 3d, `/test --mobile` |
| `acceptance_test_agent` | Use case + persona level validation with seed data | opus/high | `/develop` Step 5, `/test --acceptance`, `/accept` |
| `performance_agent` | Load tests vs NFR-PERF-* targets | opus/medium | `/test --performance` |
| `system_test_agent` | Cross-phase smoke tests, data flow validation | opus/medium | `/test --system` |
| `manual_test_agent` | Generates structured manual QA test plan | opus/medium | `/test --manual` |

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
| `demo_documenter` | Writes the demo script, test-data setup and walkthrough |
| `demo_executor` | Stands up the demo environment — starts services, seeds data |
| `demo_validator` | Walks every step of the script and verifies each result |

All three run in that order from `/startup:demo`.

---

## Skill packs

Skill packs are static knowledge files that agents load as context before executing. They contain idiomatic patterns, code examples, conventions, and anti-patterns for a specific technology. They're how `code_reviewer_I` knows what "idiomatic Go" means vs "idiomatic Python", and how `code_optimizer` knows to check for nil-slice → JSON null bugs in Go but `undefined` → omitted-field bugs in TypeScript.

### Available skill packs (230+)

`.claude/skills/` holds 238 skill-pack files (plus `INDEX.md`): backend 88, core 47, ui 23 (incl. 6 archetypes and a README), frameworks 22, testing 22, databases 11, infrastructure 10, requirements 10, languages 5. The Core, Backend, Databases, Requirements and Infrastructure rows below name a selection; see `.claude/skills/INDEX.md` for the full list.

| Category | Skill Packs |
|----------|-------------|
| **Core** (16) | `api-design` · `api-excellence` · `security-owasp` · `testing-principles` · `code-quality` · `git-workflow` · `auto-research` · `deep-research` · `debate-protocol` · `software-architecture` · `resiliency-patterns` · `observability-patterns` · `verification-protocol` · `context-budget-protocol` · `shared-backend-patterns` · `implementation-guidelines-template` |
| **Requirements** (9) | `requirement-clarity` · `acceptance-criteria` · `persona-definition` · `nfr-patterns` · `gap-analysis-checklist` · `conflict-detection` · `business-objectives` · `traceability-matrix` · `edge-case-taxonomy` |
| **UI Patterns** (16) | `professional-ui-standards` · `error-handling-patterns` · `form-patterns` · `accessibility-patterns` · `responsive-patterns` · `loading-states` · `component-composition` · `api-integration-patterns` · `shadcn` · `tailwind` · `type-generation-protocol` · `form-validation-protocol` · `advanced-state-patterns` · `structured-wireframe-format` · `vertix-portal-design-system` · **NEW:** `stitch-design` (Google Stitch MCP) |
| **UI Archetypes** (6) | `list-page` · `detail-page` · `form-page` · `dashboard-page` · `settings-page` · `component-test` |
| **Languages** (5) | `go` · `python` · `typescript` · `java` · `rust` |
| **Frameworks** (22) | **Backend:** `gin` · `echo` · `chi` · `fastapi` · `django` · `drf` · `express` · `nestjs` · `fastify` · `spring-boot` · `quarkus` · `axum` · `actix-web` · `graphql` · `trpc` · **Frontend:** `react` · `nextjs` · `vue` · `svelte` · `tanstack-query` · **Mobile (NEW):** `react-native` · `react-native-app-patterns` |
| **Databases** (9) | `postgres` · `mysql` · `mongodb` · `redis` · `sqlite` · **NEW:** `dynamodb` · **NEW:** `elasticsearch` · **NEW:** `firestore` · `query-optimization` |
| **Testing** (22) | `testify` · `gomock` · `testcontainers` · `vitest` · `playwright` · `msw` · `junit-mockito` · `pytest` · `rust-test` · `property-based` · `contract-testing` · `load-testing` · `targeted-testing` · `external-service-mocks` · `reproduction-first` · `test-case-generation` · `test-case-traceability` · **Mobile (NEW):** `mobile-testing-strategy` · `react-native-testing-library` · `maestro` · `detox` · `appium-mobile` |
| **Backend Archetypes** (60+) | CRUD handler/service/repository + tests (all 5 languages) · auth middleware · error handling · migrations · Dockerfiles · observability · performance · **NEW:** workers · **NEW:** WebSocket · **NEW:** gRPC · **NEW:** message queues |
| **Infrastructure** (10) | `docker` · `github-actions` · `kubernetes` · `terraform` · `localstack-aws-local` · `secrets-management` · `feature-flags` · `caching-strategies` · `auth-session-flows` · `saas-tenancy-models` |

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

`{{PLACEHOLDER}}` values are resolved from `IMPLEMENTATION_GUIDELINES.md` during `/startup:init` by `agent_factory`.

### Adding a custom skill pack

Create a `.md` file in `~/.claude/skills/<category>/` following the format of any existing skill pack. Then run `/startup:init --update_agents` to regenerate project agents with the new skill.

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
/startup:init --update_agents
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

Every agent runs on Claude Opus 5.5 (`model: opus`); depth and cost are tuned per agent with `effort` rather than by switching to a smaller model. One model family also keeps the whole pipeline in one prompt-cache namespace.

Counts cover the 69 core agents and 10 generation templates (79 files).

| Effort | Agents | Rationale |
|------|--------|-----------|
| **high** (29) | reviewers, verifiers, reconcilers, security and migration safety, implementation templates | Correctness-critical judgment and code generation |
| **medium** (46) | spec, planning, design, documentation, research, test-writing agents | Structured writing and analysis |
| **low** (4) | `test_runner`, `demo_executor`, `dependency_scanner`, `wireframe_generator` | Mechanical execution and result formatting |

Escalation: when an agent's first attempt fails on an external signal (tests, a blocking review finding, a gate miss), the orchestrator retries it with `model: fable`; Layer 3 gate verification also runs on `fable`. See `.claude/skills/core/model-routing.md`. To change an agent's depth, edit `effort:` in its frontmatter.

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

### Long sessions and compaction

The main session runs with a 1M-token context window, and Claude Code compacts the conversation automatically as it nears the limit (only the user can run `/compact`). The orchestrator doesn't pause or wrap up because a session is long; instead, at every wave boundary it refreshes a self-contained resume summary:

1. **Checkpoint** — the wave checkpoint JSON is written at every boundary
2. **Resume summary** — `agent_state/phases/N/checkpoints/compact-context.md` captures completed waves, decisions, current state, and next steps
3. **After a compaction or `/resume`** — the orchestrator reads `compact-context.md` + `phase_context.md` and continues with the next wave, without re-running completed ones

### If the window fills despite compaction

Auto-checkpoints at every wave boundary mean `/resume` can always reconstruct state:

```
/startup:resume                           ← checks auto-checkpoints first, then explicit sessions
```

For explicit saves, use `/startup:pause`:

```
/startup:pause --reason="context limit"   ← saves phase, step, completed items, blockers
```

Then in a new conversation:
```
/startup:resume                           ← restores from checkpoint or pause snapshot
```

Or use the lightweight approach — all state is in `agent_state/phases/N/`:
```
/startup:status          ← shows exactly where you stopped
/startup:develop --phase=N   ← resumes from last incomplete step
```

For named threads (multiple paused sessions):
```
/startup:pause --thread=auth-refactor
/startup:pause --thread=phase-3-ui
/startup:resume --list                    ← shows all paused sessions
/startup:resume --thread=auth-refactor    ← resumes specific thread
```

---

## Updating startup-agents

After pulling new changes:

```bash
cd ~/development/startup-agents
git pull
bash install.sh
```

`install.sh` also stages the framework hooks in `~/.claude/hooks/startup/` (with a `project-settings.json`). Projects created with `new-project.sh` get `.claude/hooks/` and `.claude/settings.json` copied in; `/startup:autonomous` Step 0 copies them into an existing project that lacks them. Hook paths use `$CLAUDE_PROJECT_DIR`, so they resolve inside each project. To refresh hooks in an older project after an update, copy `~/.claude/hooks/startup/*.sh` into its `.claude/hooks/`.

---

## Common patterns

### Resuming after a break

```
/startup:status         ← tells you exactly where you are and what to run next
```

### Re-running a phase

Delete the gate file to unlock re-development:
```bash
rm agent_state/phases/2/gate.passed
/startup:develop --phase=2
```

### Handling a change request mid-project

1. Use `product_manager` agent to evaluate the change and update `docs/BRD.md`
2. Re-run `/startup:plan --phase=N` for the affected phase
3. Re-run `/startup:develop --phase=N`

### Adding a tech stack not in skill packs

Create `~/.claude/skills/<category>/<tech>.md` following the format of an existing skill. Run `/startup:init --update_agents` to regenerate agents with the new skill pack.

### Skipping UI wireframes

If your project has no frontend, set `frontend.enabled = false` in `docs/IMPLEMENTATION_GUIDELINES.md`. The `ui_developer`, `ui_audit_agent`, and `ui_test_agent` will not be generated.

### Adding a React Native app

Fill in IMPLEMENTATION_GUIDELINES §24 (Mobile) so the tech profile has `mobile.enabled = true`, then run `/startup:init --update_agents`. See [docs/MOBILE_GUIDE.md](docs/MOBILE_GUIDE.md).

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

## Contributing to the framework

This section is for editing the framework itself (agents, commands, skills, hooks in this repo), not for using it in a project.

### Dependency graph: agents ↔ commands ↔ skills

Each agent's frontmatter declares its place in the graph (schema: [.claude/agents/AGENT_SCHEMA.md](.claude/agents/AGENT_SCHEMA.md)):

| Field | Who writes it | Meaning |
|-------|---------------|---------|
| `upstream` | You | Hard ordering. Must point to an agent in an **earlier** `/develop-orchestrator` wave; an agent in the same wave belongs in `runs_after` |
| `runs_after` | You | Soft ordering — this agent reads the other's output when it exists |
| `downstream` | `_sync-deps.py` | **Derived, never hand-edited:** the exact inverse of every other agent's `upstream` ∪ `runs_after` |
| `skill_packs` | You (or `_add-packs.py`) | Every agent loads at least one skill pack; every path must exist |

### Maintenance workflow

After adding or editing an agent, template, command or skill:

```bash
python3 .claude/agents/_sync-deps.py        # re-derive downstream lists (--check = dry run for CI)
.claude/agents/_sync-contract.sh            # regenerate the reference-packs + operating-contract blocks
bash tests/run-all.sh                       # must print ALL TESTS PASSED
./install.sh                                # deploy to ~/.claude (the installed copy is not git-tracked)
```

To add skill packs to an agent: `python3 .claude/agents/_add-packs.py <agent-file> <category>/<pack>.md [...]` (it refuses a pack that doesn't exist), then run `_sync-contract.sh` on the same file.

### Framework tests

`bash tests/run-all.sh` runs six suites (111 checks at the time of writing; requires `python3` with PyYAML and `jq`):

| Suite | Guards |
|-------|--------|
| `agent-registry.test.sh` | Base-roster names that have no agent file; INVENTORY.md core-agent count drift |
| `autonomous-chain.test.sh` | The `/autonomous` chain: every referenced sub-command/flag exists, Skill-tool invocation, `/design` after `/plan`, auto-mode contracts in sub-commands, force-gate policy, Stop hook registered and installed into projects |
| `autonomous-continue.test.sh` | The Stop hook blocks mid-run stops, allows `awaiting_human`/`paused`/`failed`/`complete`, and marks a no-progress run `stalled` |
| `dependency-graph.test.sh` | `tests/lib/depgraph.py` finding classes (below) plus derived-deps sync, the skill-resolution table, TC-ID regex, generated-agent identity, mobile wiring and the Stitch tool surface |
| `remember.test.sh` | Deterministic bi-temporal fact supersession in `remember.sh` |
| `verify-gate.test.sh` | The phase-gate hook (roster completeness, stub reports, forged `gate.passed`) |

`python3 tests/lib/depgraph.py` reports ten finding classes, all of which must be empty:

| Class | Meaning |
|-------|---------|
| `DANGLING_AGENT` | A dependency or spawn names an agent with no file |
| `DANGLING_SKILL` | A `skill_packs` entry or body path names a skill file that doesn't exist |
| `ASYMMETRIC` | A lists B downstream but B doesn't list A upstream / runs_after |
| `WAVE_ORDER` | A hard `upstream` edge to an agent in the same or a later wave |
| `IO_UNPRODUCED` | An agent reads a file no agent or command produces |
| `REPORT_NAME` | The orchestrator expects a report name the agent never writes |
| `ORPHAN_AGENT` | An agent nothing invokes |
| `ORPHAN_SKILL` | A skill pack nothing references |
| `NO_SKILLS` | An agent that loads no skill pack |
| `YAML_ERROR` | Frontmatter that doesn't parse |

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
/startup:init
```

That's it. `/init` reads your paragraph, interviews you for gaps, creates a structured BRD with numbered requirements (FR-001, FR-002, ...), confirms your tech stack, and generates project-specific agents.

**What you now have:**
```
docs/BRD.md                          ← 30+ numbered requirements extracted from your paragraph
docs/IMPLEMENTATION_GUIDELINES.md    ← confirmed: Go 1.22 / Chi / PostgreSQL / Docker
.claude/agents/generated/            ← 8 agents customized for Go + Chi + PostgreSQL
```

**Next step:** Run `/startup:status` to see what the system recommends.

---

### Level 2: Build one phase (30-60 minutes)

Now build the first feature set. The system breaks your BRD into phases automatically.

```
/startup:plan               ← creates specs for Phase 1 (auto-detected)
```

This produces:
- Technical specs (TRDs) for each component
- Typed data contracts (TypeScript interfaces for every endpoint)
- UI specs (if frontend enabled)
- Goal verification: "will these specs achieve the phase goal?"

Review the specs in `docs/design/phases/1/specs/`. Then:

```
/startup:develop            ← implements Phase 1 end-to-end
```

This runs the full pipeline: audit → code → tests → review → acceptance → gate. Takes 15-40 minutes depending on phase size. You don't need to do anything — watch the progress.

**What happens inside `/develop`:**
```
Wave 1:   Audit — what exists vs what the specs require
Wave 2:   Database → migrations → backend → API (publishes api-contracts.md) → UI ∥ mobile app
Wave 3:   Tests, one agent per tier (unit, integration, UI → browser E2E, mobile → device E2E)
Wave 3v:  test_runner re-runs the suites independently and cross-checks the writers' counts
Wave 3.5: Local deploy + health check
Wave 4:   Reviewers + reconcilers + acceptance tests (parallel, one named agent each)
Wave 5:   Fix loop
Wave 6:   Gate — every agent in the phase roster must have completed, every report must pass
```

**If the gate passes:** `agent_state/phases/1/gate.passed` is written. You're done with Phase 1.

**If the gate blocks:** The system tells you exactly what failed and how to fix it. Fix it, then re-run `/startup:develop`.

---

### Level 3: Add pre-planning rigor (recommended for complex projects)

Before planning, surface assumptions and research decisions. This prevents "assumption bugs" — the #1 cause of mid-implementation rework.

```
/startup:map                ← maps the codebase (skip for greenfield projects)
/startup:discuss            ← surfaces assumptions + researches decisions
/startup:plan               ← plans with full context
/startup:develop            ← implements with confidence
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
/startup:discuss --auto     ← auto-resolves all decisions, logs everything
/startup:plan               ← reads DISCUSSION.md automatically
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
/startup:map --incremental

# 2. Surface assumptions and research decisions
/startup:discuss --phase=N

# 3. Generate specs with goal verification
/startup:plan --phase=N

# 3b. UI / mobile phases: design contract behind the design gate
/startup:design --phase=N                  # add --source=stitch to render screens in Google Stitch

# 4. Review specs (optional but recommended)
#    Check: docs/design/phases/N/specs/
#    Check: agent_state/phases/N/plan_check.md (goal verification)

# 5. Implement end-to-end
/startup:develop --phase=N

# 6. Gate passes → Phase N complete!
#    Repeat from step 1 for Phase N+1
```

**Between phases — optional quality commands:**
```
/startup:test --phase=N          ← re-run tests independently
/startup:review                  ← standalone code review
/startup:optimize                ← dead code removal + performance
/startup:benchmark --save-baseline  ← capture performance metrics
```

**After all phases:**
```
/startup:accept                  ← global acceptance testing (all personas, all use cases)
/startup:deploy --target=local   ← deploy locally
```

---

### Level 5: Fully autonomous (hands-off)

Let the system build everything. You review once, then walk away.

```
/startup:autonomous
```

**What happens:**

```
Phase 0:   Environment pre-flight (Docker, ports, tools, framework hooks, run.json)
Phase 1:   /init --auto         Creates BRD + agents (auto-researches all gaps)
Phase 1b:  /map                 Codebase knowledge base (skipped for greenfield)
Phase 2:   /discuss --auto      Surfaces assumptions (auto-resolved)
Phase 2b:  /plan --auto         Specs + data contracts + goal verification
Phase 2c:  /design --source=stitch --auto   UI/mobile phases only — AFTER /plan (needs PHASE_PLAN + data-contracts);
                                            pure-agent fallback if Stitch is unavailable

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

Phase 4:   /develop --auto      Implements Phase 1 (via /develop-orchestrator, wave by wave)
Phase 5:   For each remaining phase:
             /map --incremental → /discuss --auto → /plan --auto → /design (UI phases) → /develop --auto
Phase 5b:  Local deploy
Phase 6:   /accept --auto       Global validation + pipeline completeness
Phase 7:   Final report + /health integrity check
```

**It runs as one continuous turn.** Each sub-command is invoked through the Skill tool (`startup:<cmd>`), their closing "▶ Next: …" hints are ignored, and a Stop hook (`.claude/hooks/autonomous-continue.sh`) blocks the turn from ending while `agent_state/autonomous/run.json` has `"status": "running"`. The run stops only at the human checkpoint, a security pause, a real failure, or completion. Approving the checkpoint also approves the force-gate policy for later phases. Full walkthrough: [docs/AUTONOMOUS_GUIDE.md](docs/AUTONOMOUS_GUIDE.md).

**Safety guarantees in autonomous mode:**
- Security decisions NEVER auto-resolve permissively (uses hardened defaults)
- Escalation circuit breaker: >10 auto-resolutions per phase → exits auto mode
- Every auto-decision is logged to `agent_state/autonomous/auto-resolved.jsonl`
- Force-gated phases are fully documented (what failed, why it was forced)
- Git branch per phase with immutable tags at each boundary

**Customize autonomous runs:**
```
/startup:autonomous --confirm_each_phase    ← checkpoint before EVERY phase
/startup:autonomous --max_phases=2          ← only build first 2 phases
/startup:autonomous --skip_init             ← reuse existing BRD
/startup:autonomous --resume                ← continue from run.json next_step
```

---

### Session management

**Save and resume work across conversations:**
```
/startup:pause                              ← saves phase, step, decisions, blockers
/startup:pause --reason="end of day"        ← with reason
/startup:pause --thread=auth-work           ← named thread (multiple paused contexts)

# In a new conversation:
/startup:resume                             ← restores latest session
/startup:resume --list                      ← shows all paused sessions
/startup:resume --thread=auth-work          ← resumes specific thread
```

**Context window fills up?** Same flow:
```
/startup:pause --reason="context limit"
# Start new conversation
/startup:resume
```

---

### Parallel workstreams

Work on independent features concurrently:

```
# Create workstreams (each gets its own git branch)
/startup:workstream create --name=auth --phase=3 --description="Authentication system"
/startup:workstream create --name=reports --phase=4 --description="Reporting dashboard"

# Work on auth
/startup:workstream switch --name=auth
/startup:discuss --phase=3
/startup:plan --phase=3
/startup:develop --phase=3

# Switch to reports (auth progress is saved automatically)
/startup:workstream switch --name=reports
/startup:discuss --phase=4
/startup:plan --phase=4
/startup:develop --phase=4

# Check progress across all workstreams
/startup:workstream list
# Output:
#   ● auth      (active)  Phase 3   branch: workstream/auth      progress: 100%
#   ○ reports   (paused)  Phase 4   branch: workstream/reports   progress: 60%

# Merge completed auth back to main (runs integration check + regression tests)
/startup:workstream merge --name=auth
```

**When to use workstreams:** Features that don't share components. If Phase 3 and Phase 4 both modify the same service, use sequential phases instead.

---

### Starting with deep research

For new products or unfamiliar markets:

```
# 1. Research first (6 parallel agents, 15-30 minutes)
/startup:research --domain="XDR/EDR cybersecurity"

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
/startup:autonomous
# OR manually: /startup:init → /startup:plan → /startup:develop
```

---

### When things go wrong

| Situation | What to run | What it does |
|-----------|------------|-------------|
| Pipeline failed mid-run | `/startup:forensics` | Timeline reconstruction → root cause → recovery steps |
| Suspect corrupted state | `/startup:health` | Checks manifest integrity, gate consistency, file references |
| Auto-repair state issues | `/startup:health --fix` | Fixes orphaned reports, dead refs, incomplete logs |
| Bug in the built app | `/startup:diagnose --symptom="..."` | Traces symptom → spec → implementation → root cause |
| Quick fix needed | `/startup:hotfix --phase=N --component=auth` | Scoped fix → scoped test → scoped review → merge |
| Need to undo a deploy | `/startup:rollback --target=local` | Reverses migrations, redeploys previous build |
| Phase needs a redo | `/startup:reset-phase --phase=N` | Archives state, creates safety tag, prepares clean re-run |
| Flaky test blocking gate | `/startup:develop --force_gate` | Forces gate with full logging (tracked in manifest) |

---

### Quick reference — what to run when

| I want to... | Run this |
|-------------|----------|
| Build everything hands-off | `/startup:autonomous` |
| Understand a competitor's product deeply | `/startup:product-workflows --product="Trellix DLP"` |
| Research a market first | `/startup:research --domain="..."` |
| Start a new project | `bash new-project.sh my-app` → `/startup:init` |
| Understand codebase before planning | `/startup:map` |
| Surface assumptions before planning | `/startup:discuss` |
| Build the next feature set | `/startup:discuss` → `/startup:plan` → `/startup:develop` |
| See where I am | `/startup:status` |
| Save progress for later | `/startup:pause` → (new session) → `/startup:resume` |
| Work on two features in parallel | `/startup:workstream create --name=feature-a` |
| Run tests without building | `/startup:test --phase=N` |
| Review code quality | `/startup:review` |
| Optimize code | `/startup:optimize` |
| Deploy | `/startup:deploy --target=local` |
| Validate the full product | `/startup:accept` |
| Fix a bug fast | `/startup:hotfix --phase=N --component=auth` |
| Investigate a bug | `/startup:diagnose --symptom="..."` |
| Check pipeline health | `/startup:health` |
| Investigate a failure | `/startup:forensics` |
| Track performance | `/startup:benchmark --save-baseline` |
| Roll back a deploy | `/startup:rollback --target=local` |
| Add a feature mid-project | `product_manager` agent → `/startup:plan` |
| Re-do a phase | `/startup:reset-phase --phase=N` → `/startup:develop` |
| Design screens in Google Stitch | `/startup:stitch init` → `/startup:design --source=stitch` |
| Check built pages against the design | `/startup:ui-audit` (add `--fix=all` to repair) |
| Test the React Native app on both platforms | `/startup:test --mobile` |
| Rehearse a stakeholder demo | `/startup:demo --phase=N` |
| Resume an interrupted autonomous run | `/startup:autonomous --resume` |

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
Pipeline (44 command files in total, including the rules-board family and aliases):
/startup:product-workflows  Product workflow intelligence (docs + videos + APIs).
/startup:research     Deep market & product research. Vendors, capabilities, moats.
/startup:init         One-time project setup. Creates BRD + agents from requirements.
/startup:map          Codebase knowledge base — parallel focus areas.
/startup:discuss      Surface assumptions + research decisions. Run before /plan.
/startup:plan         Plans a phase. Creates specs, data contracts, goal verification.
/startup:design       UI/mobile design contract behind a blocking design gate (after /plan).
/startup:develop      Builds a phase end-to-end with parallel review + acceptance.
/startup:autonomous   Full pipeline: init → map → discuss → plan → design → develop → accept.
/startup:accept       Full-product validation after all phases complete.
/startup:deploy       Build and deploy to local, staging, or production.

Design & Demo:
/startup:stitch       Google Stitch workbench (init/generate/variants/edit/theme/sync/status).
/startup:ui-audit     Every built page vs design standards + its Stitch baseline.
/startup:demo         Write, stand up and rehearse a stakeholder demo.

Session & Workflow:
/startup:pause        Save session state for later resumption.
/startup:resume       Restore paused session and continue working.
/startup:workstream   Manage parallel workstreams (create/switch/merge).

Standalone:
/startup:test         Runs tests standalone. Many flags for targeting specific tiers (incl. --mobile).
/startup:review       Code review: spec compliance → style + arch + security (parallel).
/startup:optimize     Code cleanup and optimization with before/after comparison.
/startup:benchmark    Performance tracking with baselines and regression detection.
/startup:status       Where am I? What should I run next?

Issue Resolution:
/startup:hotfix       Fast-track bug fix. Scoped test + scoped review. No full pipeline.
/startup:diagnose     Trace a symptom to root cause. Optional auto-fix.
/startup:rollback     Roll back a deployment. Reverse migrations + redeploy previous build.
/startup:reset-phase  Reset a phase for re-development with state preservation.

Pipeline Diagnostics:
/startup:health       Check pipeline state integrity. Use --fix for auto-repair.
/startup:forensics    Investigate failed pipeline runs. Timeline + root cause + recovery.
```

### Tips

- **Start small.** Your first requirements file can be a single paragraph. `/init` will ask clarifying questions.
- **Check status often.** `/startup:status` always tells you the next action.
- **Trust the gate.** If the gate blocks, read the blocker — it tells you the exact file, line, and fix.
- **Use `--dry_run` for optimize.** See what would change before committing to it.
- **Commit between phases.** Each phase is a natural commit point.
- **Provide seed data for predictable tests.** Drop YAML files into `requirements/test-data/` for deterministic acceptance tests.
- **Add your own skill packs.** Using a framework not in the defaults? Create a `.md` file in `~/.claude/skills/` and re-run `/startup:init --update_agents`.
