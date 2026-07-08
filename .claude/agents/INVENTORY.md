# Agent Inventory

Complete index of all agents in the SDLC pipeline.

---

## Quick Reference: Which Agent for Which Task?

| I need to... | Use this agent | Invoked by |
|---|---|---|
| Run full rule pipeline for any plugin | `rule_pipeline_orchestrator` | `/rules-plugin` |
| Research coverage gaps + vendor rules | `market_research_agent` | `/rules-plugin` Stage 1 |
| Author rule + entity JSON files | `rule_developer_agent` | `/rules-plugin` Stage 2 |
| Validate + auto-fix FP patterns in rules | `rule_fp_optimizer_agent` | `/rules-plugin` Stage 3 |
| Audit corpus coverage + vendor parity | `corpus_completeness_agent` | `/rules-plugin` Stage 4 |
| Publish rules to DB + Artifactory | `rule_db_publisher_agent` | `/rules-plugin` Stage 5 |
| Register plugin pages in React UI | `plugin_ui_developer_agent` | `/rules-plugin` Stage 6 |
| Write + run all test tiers for plugin | `plugin_test_agent` | `/rules-plugin` Stage 7 |
| Add a new plugin (edr/dlp/certs/siem) | Create `.claude/agents/plugins/<id>.json` | manual then `/rules-plugin` |
| Create BRD from requirements | `brd_agent` | `/init` |
| Handle post-init BRD changes | `product_manager` | manual |
| Confirm/complete tech stack | `impl_guidelines_agent` | `/init` |
| Generate project-specific agents | `agent_factory` | `/init` |
| Validate requirements match BRD | `requirements_brd_reconciler` | `/init` (after brd_agent) |
| Plan a phase | `project_planner` | `/plan` |
| Write technical specs (TRDs) | `spec_writer` | `/plan` |
| Design UI wireframes | `ux_designer` | `/plan` |
| Verify specs are complete | `spec_verifier` | `/plan` |
| Validate BRD matches specs | `brd_spec_reconciler` | `/plan` (after spec_verifier) |
| Generate architecture diagrams | `architecture_orchestrator` | `/init` (after guidelines) |
| Write backend code | `backend_developer` | `/develop` |
| Write API layer code | `api_developer` | `/develop` |
| Design database schema | `database_agent` | `/develop` |
| Create migrations | `migration_agent` | `/develop` |
| Audit code before implementation | `backend_audit_agent` | `/develop` Step 1 |
| Audit UI before implementation | `ui_audit_agent` | `/develop` Step 1 (UI phases) |
| Review code style/idioms | `code_reviewer_I` | `/develop` Step 5 |
| Review architecture compliance | `code_reviewer_II` | `/develop` Step 5 |
| Review security | `security_reviewer` | `/develop` Step 5 |
| Verify tenant isolation | `tenant_isolation_verifier` | `/develop` Step 5 |
| Verify quality gates | `code_quality_verifier` | `/develop` Step 5 |
| Validate specs match code | `spec_impl_reconciler` | `/develop` Step 5 |
| Validate specs match tests | `spec_test_reconciler` | `/develop` Step 5 |
| Run acceptance tests | `acceptance_test_agent` | `/develop` Step 5 |
| Run e2e tests | `e2e_orchestrator` | `/test --e2e` |
| Execute test commands | `test_runner` | `/test` |
| Run performance tests | `performance_agent` | `/test --performance` |
| Run system smoke tests | `system_test_agent` | `/test --system` |
| Generate manual test plans | `manual_test_agent` | `/test --manual` |
| Optimize backend code | `code_optimizer` | `/optimize` |
| Optimize frontend code | `ui_code_optimizer` | `/optimize` |
| Scan dependencies for CVEs | `dependency_scanner` | `/review` |
| Deploy the application | `deployment_agent` | `/deploy` |
| Set up CI/CD | `ci_cd_agent` | `/deploy` (first time) |
| Validate observability | `observability_agent` | `/deploy` (staging/prod) |
| Update documentation | `documentation_agent` | `/develop` Step 6b |
| Create demo scripts | `demo_documenter` | manual |
| Execute demo setup | `demo_executor` | manual |
| Validate demo works | `demo_validator` | manual |
| Make a technical decision | `debate_moderator` | any agent (escalation) |
| Review UI spec quality | `design_quality_reviewer` | `/plan` (UI phases) |
| Surface assumptions before planning | `phase_assumptions_analyzer` | `/discuss` |
| Research gray area decisions | `decision_researcher` | `/discuss` |
| Verify plan achieves phase goal | `plan_goal_verifier` | `/plan` Step 4b |
| Validate full pipeline chain end-to-end | `pipeline_completeness_agent` | `/accept` Step 5b |
| Map codebase for persistent knowledge | `codebase_mapper` | `/map` |
| Research product documentation | `product_doc_researcher` | `/product-workflows` |
| Extract workflow intelligence from videos | `product_video_researcher` | `/product-workflows` |
| Research product APIs + automation gaps | `product_api_researcher` | `/product-workflows` |
| Map capability into screen-by-screen workflow | `capability_flow_mapper` | `/product-workflows` |
| Synthesize workflows into unified intelligence | `workflow_synthesizer` | `/product-workflows` |

---

## Agent Categories

### Plugin Rule Development

All agents are **plugin-agnostic** — they read `.claude/agents/plugins/<plugin_id>.json` for all plugin-specific knowledge (entity types, coverage framework, vendor sources, quality thresholds). Add a new plugin by creating a manifest file; all 7 agents work immediately with `--plugin <id>`.

| Agent | Model | Input | Output | Notes |
|---|---|---|---|---|
| `rule_pipeline_orchestrator` | sonnet | plugin manifest, args | pipeline_summary.md | Orchestrates all 7 stages with checkpoints + feedback loop |
| `market_research_agent` | opus | plugin manifest, scope | `<plugin>_wave_N_research.md` | Coverage gap analysis + 7-source vendor research |
| `rule_developer_agent` | opus | research doc, plugin manifest | `policies/<plugin>/` JSON files | Framework reference for all condition/entity/operator patterns |
| `rule_fp_optimizer_agent` | sonnet | plugin manifest, rule files | `<plugin>_wave_N_fp_optimization_report.md` | 10-check validation + auto-fix (not_in/OR bug, impossible AND, dangling refs) |
| `corpus_completeness_agent` | sonnet | plugin manifest, corpus | `<plugin>_corpus_completeness_<ts>.md` + `wave_next_scope.json` | Coverage % + vendor parity + feedback loop artifact |
| `rule_db_publisher_agent` | sonnet | plugin manifest, wave tag | `<plugin>_wave_N_publish_report.md` | Manifest rebuild → API push → git tag → Artifactory |
| `plugin_ui_developer_agent` | sonnet | plugin manifest | `<plugin>_ui_report.md` + React pages | Home + list + detail pages per entity type, routes, nav, RJSF forms, 4-state component tests |
| `plugin_test_agent` | sonnet | plugin manifest, wave tag | `<plugin>_test_report.md` | Unit + integration + E2E pipeline + UI component + Playwright browser tests |

**Plugin manifests:** `.claude/agents/plugins/`
- `edr.json` — ATT&CK tactics, MITRE coverage, process/network/user entity types, sensor map
- `dlp.json` — channels, data categories, regulations, DLP vendor sources

---

### Requirements & BRD

| Agent | Model | Input | Output | Notes |
|---|---|---|---|---|
| `brd_agent` | sonnet | requirements/ | docs/BRD.md | Orchestrates full BRD creation pipeline |
| `brd_analyzer` | sonnet | requirements/ | agent_state/brd_refiner/analysis.yaml | Subagent of brd_agent |
| `brd_interviewer` | sonnet | analysis.yaml | agent_state/brd_refiner/decisions.yaml | Subagent of brd_agent |
| `brd_writer` | sonnet | analysis.yaml | docs/BRD.md | Subagent of brd_agent |
| `product_manager` | opus | docs/BRD.md, change request | docs/BRD.md (amended), docs/user-stories/ | Post-init BRD amendments |
| `impl_guidelines_agent` | sonnet | docs/BRD.md | docs/IMPLEMENTATION_GUIDELINES.md | Tech stack confirmation |
| `agent_factory` | sonnet | IMPLEMENTATION_GUIDELINES.md | .claude/agents/generated/ | Generates project-specific agents |

### Product Workflow Intelligence

| Agent | Model | Input | Output | Notes |
|---|---|---|---|---|
| `product_doc_researcher` | opus | product name, capabilities | doc-corpus.md, CAPABILITY-TAXONOMY.md | Official docs, KB, training, forums |
| `product_video_researcher` | sonnet | product name, capabilities | video-intelligence.md | YouTube demos, conference talks, webinars |
| `product_api_researcher` | sonnet | product name, capabilities | api-intelligence.md, api-schemas.yaml, api-coverage-matrix.md | REST/GraphQL/SDK/CLI research |
| `capability_flow_mapper` | sonnet | capability + doc corpus + video/API intel | workflow.md, quickstart.md, advanced.md, prerequisites.md, gotchas.md, lifecycle.md | Per-capability deep mapping (parallel) |
| `workflow_synthesizer` | sonnet | all capability flows + API intel | OVERVIEW.md, dependency-graph.md, personas/*.md, reference/*.yaml | Final assembly + persona summaries |

### Planning & Specs

| Agent | Model | Input | Output | Notes |
|---|---|---|---|---|
| `project_planner` | sonnet | BRD, guidelines, prev manifest | PHASE_PLAN.md, phase_context.md | Defines scope, exit criteria, waves |
| `spec_writer` | sonnet | PHASE_PLAN.md, BRD | docs/design/phases/N/specs/*.md | One TRD per component/flow |
| `spec_verifier` | sonnet | BRD, PHASE_PLAN, specs | VERIFICATION_REPORT.md | Quality gate for specs completeness |
| `phase_assumptions_analyzer` | opus | BRD, guidelines, codebase | assumptions.md, open_questions.md | Deep pre-planning assumption surfacing |
| `decision_researcher` | sonnet | open question, guidelines | research/*.md | Gray area decision comparison tables |
| `plan_goal_verifier` | opus | PHASE_PLAN, BRD, specs | plan_check.md | Goal-backward plan verification |

### Design

| Agent | Model | Input | Output | Notes |
|---|---|---|---|---|
| `architecture_orchestrator` | opus | BRD, guidelines | docs/architecture/ | Spawns 4 subagents in parallel |
| `c4_diagram_agent` | sonnet | BRD, guidelines | docs/architecture/c4-diagram.md | Subagent of architecture_orchestrator |
| `sequence_diagram_agent` | sonnet | BRD, guidelines | docs/architecture/sequence-diagrams.md | Subagent of architecture_orchestrator |
| `deployment_diagram_agent` | sonnet | guidelines | docs/architecture/deployment-diagram.md | Subagent of architecture_orchestrator |
| `eagle_diagram_agent` | sonnet | BRD, guidelines | docs/architecture/eagle-view.md | 10,000-ft strategic overview: pattern classification, domain boundaries, evolution recs |
| `adr_agent` | sonnet | guidelines | docs/architecture/adrs/ | Subagent of architecture_orchestrator; also invoked by /plan |
| `ux_designer` | opus | BRD, guidelines | docs/design/phases/N/specs/*.wireframe.md | UI wireframe specifications |
| `wireframe_generator` | sonnet | BRD | wireframe scaffolding | Subagent of ux_designer |
| `design_quality_reviewer` | sonnet | wireframes, guidelines | design quality report | Validates UI specs against 9 dimensions |

### Implementation (Generated)

| Agent | Model | Input | Output | Notes |
|---|---|---|---|---|
| `backend_developer` | sonnet | guidelines, phase specs | backend source code | Template: .claude/agents/generated/ |
| `api_developer` | sonnet | guidelines, phase specs | API layer code | Template: .claude/agents/generated/ |
| `database_agent` | sonnet | guidelines, phase specs | schema design | Template: .claude/agents/generated/ |
| `migration_agent` | sonnet | guidelines, database design | migration files | Template: .claude/agents/generated/ |

### Testing

| Agent | Model | Input | Output | Notes |
|---|---|---|---|---|
| `test_runner` | haiku | agent_registry.json | test results | Executes test commands |
| `acceptance_test_agent` | opus | BRD, PHASE_PLAN, guidelines | acceptance_report.md | Final validation before gate |
| `e2e_orchestrator` | sonnet | guidelines, phase manifests | e2e test results | End-to-end workflow tests |
| `performance_agent` | sonnet | BRD (NFR-PERF-*) | performance report | Load tests, latency/throughput |
| `system_test_agent` | sonnet | BRD | system smoke test results | Cross-phase boundary tests |
| `manual_test_agent` | sonnet | PHASE_PLAN | manual test plan | Structured QA plan for humans |

### Review & Security

| Agent | Model | Input | Output | Notes |
|---|---|---|---|---|
| `code_reviewer_I` | sonnet | guidelines, skill pack | code_review_I.md | Style, idioms, naming (pass 1 of 2) |
| `code_reviewer_II` | opus | guidelines, code_review_I.md | code_review_II.md | Architecture compliance (pass 2 of 2) |
| `security_reviewer` | opus | guidelines, OWASP skill pack | security_review.md | OWASP Top 10, IDOR chains |
| `tenant_isolation_verifier` | opus | handler + service files | isolation_report.md | tenantID trace through every route |
| `breaking_change_reviewer` | opus | current diff, prior-phase contracts | breaking_change_report.md | Cross-phase contract breakage (API sig, response shape, event schema, shared types, config keys, DB columns) |
| `migration_safety_reviewer` | opus | migration files | migration_safety.md | Destructive/irreversible ops, backfill safety, lock risk, rollback correctness |
| `threat_model_agent` | opus | phase specs, data flows | threat_model.md (+ .json) | Design-time STRIDE per trust boundary; threat→mitigation→TC-SEC-* (runs in /plan for security-relevant phases) |
| `accessibility_auditor` | sonnet | built UI, wireframes | accessibility_audit.md (+ .json) | WCAG-AA pass/fail per rule against the BUILT UI (axe/keyboard/contrast/ARIA); runs in /develop UI phases |
| `code_quality_verifier` | sonnet | guidelines, manifest | quality_gate_verification.md | TODO/stub/secret/import checks |
| `design_quality_reviewer` | sonnet | wireframes, guidelines | design quality report | UI spec quality validation |
| `dependency_scanner` | haiku | guidelines | dependency scan results | CVE detection, license compliance |

### Reconciliation

| Agent | Model | Input | Output | Notes |
|---|---|---|---|---|
| `requirements_brd_reconciler` | sonnet | requirements/, BRD | requirements_vs_brd.md | Step 0: source docs match BRD |
| `spec_verifier` | sonnet | BRD, PHASE_PLAN, specs | VERIFICATION_REPORT.md | Step 1: specs are complete |
| `brd_spec_reconciler` | sonnet | BRD, PHASE_PLAN, specs | brd_vs_specs.md | Step 2: BRD matches specs |
| `spec_impl_reconciler` | opus | specs, manifest | specs_vs_impl.md | Step 3: specs match code |
| `spec_test_reconciler` | sonnet | specs, test results | specs_vs_tests.md | Step 4: specs match tests |
| `pipeline_completeness_agent` | opus | all reconciliation reports, manifests, BRD | pipeline_completeness_report.md | Step 5: full chain validation (capstone) |

### Decision Support

| Agent | Model | Input | Output | Notes |
|---|---|---|---|---|
| `debate_moderator` | sonnet | debate_request JSON | verdict JSON + transcript | Orchestrates debate team |
| `debate_researcher` | sonnet | assigned option | research evidence | Subagent: one per option |
| `debate_advocate` | opus | assigned option + all research | argument | Subagent: argues FOR an option |
| `debate_arbitrator` | opus | all arguments | verdict + scores | Subagent: final decision-maker |
| `solution_selector` | opus | N candidate impls + cross_test_matrix.md | reports/candidate_selection.md | Picks winning implementation via rubric + model-test voting; emits graft list (candidate-selection mode) |

### Infrastructure & Deployment

| Agent | Model | Input | Output | Notes |
|---|---|---|---|---|
| `deployment_agent` | sonnet | guidelines | deployment artifacts | Docker, orchestration, health checks |
| `ci_cd_agent` | sonnet | guidelines | CI/CD pipeline config | First deployment only |
| `observability_agent` | sonnet | guidelines | observability validation | First staging/prod deployment |
| `reliability_agent` | opus | specs, NFR-* targets, guidelines | reliability_review.md (+ .json), runbooks | SLI/SLO/error-budget, health-check design, timeout/retry/circuit-breaker, runbook stubs (runs in /plan + /deploy) |

### Quality & Optimization

| Agent | Model | Input | Output | Notes |
|---|---|---|---|---|
| `backend_audit_agent` | sonnet | phase_context, specs | audit_report.md | Pre-implementation gap analysis |
| `ui_audit_agent` | sonnet | PHASE_PLAN, specs | UI audit report | Pre-implementation UI gap analysis |
| `code_optimizer` | sonnet | guidelines | optimization report | Dead code removal, perf optimization |
| `ui_code_optimizer` | sonnet | guidelines | UI optimization report | Bundle size, render performance |
| `codebase_mapper` | sonnet | guidelines, codebase | agent_state/codebase/*.md | Persistent codebase knowledge base |

### Documentation & Demo

| Agent | Model | Input | Output | Notes |
|---|---|---|---|---|
| `documentation_agent` | sonnet | guidelines, manifest | API docs, README, guides | Post-implementation docs |
| `demo_documenter` | sonnet | BRD, manifest | demo scripts | Stakeholder demo documentation |
| `demo_executor` | haiku | demo script, guidelines | demo environment | Seeds data, starts services |
| `demo_validator` | sonnet | demo script | validation report | Verifies demo works end-to-end |

---

## Dependency Graph

```
/rules-plugin pipeline (plugin-agnostic, driven by .claude/agents/plugins/<id>.json):
  rule_pipeline_orchestrator
    Stage 1: market_research_agent      → <plugin>_wave_N_research.md
    Stage 2: rule_developer_agent       → policies/<plugin>/**/*.json (committed)
    Stage 3: rule_fp_optimizer_agent    → fp_optimization_report.md + entity stubs
    Stage 4: corpus_completeness_agent  → completeness report + wave_next_scope.json
      ├── coverage < 95%  → feedback loop: wave_next_scope.json → Stage 1 (max 5 loops)
      └── coverage ≥ 95%  → advance
    Stage 5: rule_db_publisher_agent    → manifest rebuild → API push → git tag → Artifactory
    Stage 6: plugin_ui_developer_agent  → React pages + routes + nav + tests (skippable with --no-ui)
    Stage 7: plugin_test_agent          → unit + integration + E2E + UI component + Playwright tests

/init pipeline:
  brd_agent (brd_analyzer → brd_interviewer → brd_writer)
    ├→ requirements_brd_reconciler
    ├→ impl_guidelines_agent
    │    ├→ agent_factory
    │    └→ architecture_orchestrator
    │         ├→ c4_diagram_agent
    │         ├→ sequence_diagram_agent
    │         ├→ deployment_diagram_agent
    │         └→ adr_agent
    └→ product_manager (manual, post-init)

/discuss pipeline (NEW — runs before /plan):
  phase_assumptions_analyzer (deep codebase + BRD analysis)
    └→ decision_researcher (parallel, one per open question)
  Output: DISCUSSION.md, decisions.jsonl → consumed by /plan

/map pipeline (NEW — standalone codebase knowledge):
  codebase_mapper (parallel: tech, architecture, quality, concerns)
  Output: agent_state/codebase/*.md → consumed by all planning agents

/plan pipeline:
  project_planner
    ├→ spec_writer (parallel, one per component)
    ├→ ux_designer → wireframe_generator
    │    └→ design_quality_reviewer
    ├→ spec_verifier
    │    └→ brd_spec_reconciler
    ├→ plan_goal_verifier (NEW — goal-backward verification)
    └→ adr_agent (if architectural decisions detected)

/develop pipeline:
  backend_audit_agent / ui_audit_agent (Step 1)
    → database_agent → migration_agent (Wave 1)
    → backend_developer → api_developer (Wave 2)
    → [ui_developer if UI phase] (Wave 3)
    → code_reviewer_I → code_reviewer_II → security_reviewer (Step 5, sequential)
    → tenant_isolation_verifier (Step 5, parallel with reviewers)
    → code_quality_verifier (Step 5, parallel with reviewers)
    → spec_impl_reconciler → spec_test_reconciler (Step 5)
    → acceptance_test_agent (Step 5, after all reviewers)
    → documentation_agent (Step 6b, non-blocking)

/test pipeline:
  test_runner (unit/integration)
  e2e_orchestrator (--e2e flag)
  performance_agent (--performance flag)
  system_test_agent (--system flag)
  manual_test_agent (--manual flag)

/review pipeline:
  code_reviewer_I → code_reviewer_II → security_reviewer
  dependency_scanner (parallel)

/optimize pipeline:
  code_optimizer + ui_code_optimizer (parallel)

/deploy pipeline:
  deployment_agent
  ci_cd_agent (first deployment)
  observability_agent (staging/prod)

debate team (on-demand, any pipeline):
  debate_moderator
    → debate_researcher (parallel, one per option)
    → debate_advocate (parallel, HIGH impact only)
    → debate_arbitrator

/product-workflows pipeline (NEW — product workflow intelligence):
  product_doc_researcher (official docs, KB, training, forums)
    ├→ product_video_researcher (YouTube demos, conference talks, webinars)
    ├→ product_api_researcher (REST/GraphQL/SDK/CLI, automation gaps)
    └→ capability_flow_mapper (parallel, one per capability)
         └→ workflow_synthesizer (assembly: overview, personas, dependency graph)
```

---

## Pipeline Mapping

| Command | Agents Used (in order) |
|---|---|
| `/rules-plugin` | rule_pipeline_orchestrator → market_research_agent → rule_developer_agent → rule_fp_optimizer_agent → corpus_completeness_agent (↺ loop) → rule_db_publisher_agent → plugin_ui_developer_agent → plugin_test_agent |
| `/research` | 6 parallel research agents -> synthesis -> human review |
| `/init` | brd_agent -> requirements_brd_reconciler -> impl_guidelines_agent -> agent_factory -> architecture_orchestrator (c4 + sequence + deploy + adr) |
| `/discuss` | phase_assumptions_analyzer -> decision_researcher (parallel, one per question) |
| `/map` | codebase_mapper (parallel: tech + architecture + quality + concerns) |
| `/plan` | project_planner -> spec_writer (parallel) -> ux_designer -> design_quality_reviewer -> spec_verifier -> brd_spec_reconciler -> plan_goal_verifier -> adr_agent |
| `/develop` | backend_audit_agent -> database_agent -> migration_agent -> backend_developer -> api_developer -> [ui_developer] -> code_reviewer_I -> code_reviewer_II -> security_reviewer -> tenant_isolation_verifier -> code_quality_verifier -> spec_impl_reconciler -> spec_test_reconciler -> acceptance_test_agent -> documentation_agent |
| `/test` | test_runner, e2e_orchestrator, performance_agent, system_test_agent, manual_test_agent (flag-dependent) |
| `/review` | code_reviewer_I -> code_reviewer_II -> security_reviewer + dependency_scanner |
| `/optimize` | code_optimizer + ui_code_optimizer (parallel) |
| `/deploy` | deployment_agent + ci_cd_agent + observability_agent |
| `/accept` | acceptance_test_agent (global, all phases) -> pipeline_completeness_agent (holistic chain audit) |
| `/pause` | No agents — captures session state to agent_state/sessions/ |
| `/resume` | No agents — restores session state and routes to appropriate command |
| `/workstream` | No agents — manages parallel workstream branches and state |
| `/health` | No agents — diagnoses agent_state/ integrity and repairs issues |
| `/forensics` | No agents — post-mortem analysis of failed pipeline runs |
| `/product-workflows` | product_doc_researcher -> product_video_researcher + product_api_researcher (parallel) -> capability_flow_mapper (parallel per capability) -> workflow_synthesizer |
| debate (on-demand) | debate_moderator -> debate_researcher(s) -> debate_advocate(s) -> debate_arbitrator |

---

## Agent Counts

| Location | Count |
|---|---|
| Core agents (`.claude/agents/core/`) | 66 |
| Generation templates (`.claude/agents/templates/`) | 8 |
| Generated agents (`.claude/agents/generated/`) | 0 in repo — populated at `/init` by `agent_factory` (gitignored) |
| **Total agents (repo)** | **74** |

| Category | Count |
|---|---|
| Plugin Rule Development | **8** (rule_pipeline_orchestrator, market_research_agent, rule_developer_agent, rule_fp_optimizer_agent, corpus_completeness_agent, rule_db_publisher_agent, plugin_ui_developer_agent, plugin_test_agent) |
| Requirements | 7 |
| Product Workflow Intelligence | 5 |
| Planning | 6 |
| Design | 8 (incl. `eagle_diagram_agent` — 10,000-ft strategic overview) |
| Implementation (generated) | 4 |
| Testing | 6 |
| Review & Security | 10 (incl. `breaking_change_reviewer`, `migration_safety_reviewer`, `threat_model_agent` STRIDE, `accessibility_auditor` WCAG-AA) |
| Reconciliation | 6 |
| Decision Support | 5 (incl. `solution_selector` — candidate-selection winner) |
| Infrastructure | 4 (incl. `reliability_agent` — SLO/error-budget/runbooks) |
| Quality & Optimization | 5 |
| Documentation & Demo | 4 |

| Model | Count |
|---|---|
| opus | 16 (+2: market_research_agent, rule_developer_agent) |
| sonnet | 51 (+6: rule_pipeline_orchestrator, rule_fp_optimizer_agent, corpus_completeness_agent, rule_db_publisher_agent, plugin_ui_developer_agent, plugin_test_agent) |
| haiku | 3 |
