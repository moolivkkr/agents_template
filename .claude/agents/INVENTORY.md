# Agent Inventory

Complete index of all agents in the SDLC pipeline.

---

## Quick Reference: Which Agent for Which Task?

| I need to... | Use this agent | Invoked by |
|---|---|---|
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

---

## Agent Categories

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

### Planning & Specs

| Agent | Model | Input | Output | Notes |
|---|---|---|---|---|
| `project_planner` | sonnet | BRD, guidelines, prev manifest | PHASE_PLAN.md, phase_context.md | Defines scope, exit criteria, waves |
| `spec_writer` | sonnet | PHASE_PLAN.md, BRD | docs/design/phases/N/specs/*.md | One TRD per component/flow |
| `spec_verifier` | sonnet | BRD, PHASE_PLAN, specs | VERIFICATION_REPORT.md | Quality gate for specs completeness |

### Design

| Agent | Model | Input | Output | Notes |
|---|---|---|---|---|
| `architecture_orchestrator` | opus | BRD, guidelines | docs/architecture/ | Spawns 4 subagents in parallel |
| `c4_diagram_agent` | sonnet | BRD, guidelines | docs/architecture/c4-diagram.md | Subagent of architecture_orchestrator |
| `sequence_diagram_agent` | sonnet | BRD, guidelines | docs/architecture/sequence-diagrams.md | Subagent of architecture_orchestrator |
| `deployment_diagram_agent` | sonnet | guidelines | docs/architecture/deployment-diagram.md | Subagent of architecture_orchestrator |
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

### Decision Support

| Agent | Model | Input | Output | Notes |
|---|---|---|---|---|
| `debate_moderator` | sonnet | debate_request JSON | verdict JSON + transcript | Orchestrates debate team |
| `debate_researcher` | sonnet | assigned option | research evidence | Subagent: one per option |
| `debate_advocate` | opus | assigned option + all research | argument | Subagent: argues FOR an option |
| `debate_arbitrator` | opus | all arguments | verdict + scores | Subagent: final decision-maker |

### Infrastructure & Deployment

| Agent | Model | Input | Output | Notes |
|---|---|---|---|---|
| `deployment_agent` | sonnet | guidelines | deployment artifacts | Docker, orchestration, health checks |
| `ci_cd_agent` | sonnet | guidelines | CI/CD pipeline config | First deployment only |
| `observability_agent` | sonnet | guidelines | observability validation | First staging/prod deployment |

### Quality & Optimization

| Agent | Model | Input | Output | Notes |
|---|---|---|---|---|
| `backend_audit_agent` | sonnet | phase_context, specs | audit_report.md | Pre-implementation gap analysis |
| `ui_audit_agent` | sonnet | PHASE_PLAN, specs | UI audit report | Pre-implementation UI gap analysis |
| `code_optimizer` | sonnet | guidelines | optimization report | Dead code removal, perf optimization |
| `ui_code_optimizer` | sonnet | guidelines | UI optimization report | Bundle size, render performance |

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

/plan pipeline:
  project_planner
    ├→ spec_writer (parallel, one per component)
    ├→ ux_designer → wireframe_generator
    │    └→ design_quality_reviewer
    ├→ spec_verifier
    │    └→ brd_spec_reconciler
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
```

---

## Pipeline Mapping

| Command | Agents Used (in order) |
|---|---|
| `/init` | brd_agent -> requirements_brd_reconciler -> impl_guidelines_agent -> agent_factory -> architecture_orchestrator (c4 + sequence + deploy + adr) |
| `/plan` | project_planner -> spec_writer (parallel) -> ux_designer -> design_quality_reviewer -> spec_verifier -> brd_spec_reconciler -> adr_agent |
| `/develop` | backend_audit_agent -> database_agent -> migration_agent -> backend_developer -> api_developer -> [ui_developer] -> code_reviewer_I -> code_reviewer_II -> security_reviewer -> tenant_isolation_verifier -> code_quality_verifier -> spec_impl_reconciler -> spec_test_reconciler -> acceptance_test_agent -> documentation_agent |
| `/test` | test_runner, e2e_orchestrator, performance_agent, system_test_agent, manual_test_agent (flag-dependent) |
| `/review` | code_reviewer_I -> code_reviewer_II -> security_reviewer + dependency_scanner |
| `/optimize` | code_optimizer + ui_code_optimizer (parallel) |
| `/deploy` | deployment_agent + ci_cd_agent + observability_agent |
| `/accept` | acceptance_test_agent (global, all phases) |
| debate (on-demand) | debate_moderator -> debate_researcher(s) -> debate_advocate(s) -> debate_arbitrator |

---

## Agent Counts

| Location | Count |
|---|---|
| Core agents (`.claude/agents/core/`) | 48 |
| Generated templates (`.claude/agents/generated/`) | 4 |
| **Total** | **52** |

| Category | Count |
|---|---|
| Requirements | 7 |
| Planning | 3 |
| Design | 7 |
| Implementation (generated) | 4 |
| Testing | 6 |
| Review & Security | 6 |
| Reconciliation | 5 |
| Decision Support | 4 |
| Infrastructure | 3 |
| Quality & Optimization | 4 |
| Documentation & Demo | 4 |

| Model | Count |
|---|---|
| opus | 10 |
| sonnet | 39 |
| haiku | 3 |
