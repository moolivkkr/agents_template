# Competitive Analysis: SDLC Agent Frameworks

> Generated: 2026-05-19 | Sources: Superpowers, GSD-1, GSD-2, BMAD Method, spec-kit, awesome-AI-driven-development

---

## 1. Framework Comparison Matrix

| Capability | **startup-agents** | **Superpowers** | **spec-kit** | **BMAD** | **GSD-1** | **GSD-2** |
|---|---|---|---|---|---|---|
| **Orchestration** | Pipeline DAG with phase gates | Linear + parallel subagents | Sequential 7-step | Pull-based skill invocation | LLM reads workflow markdown | Programmatic state machine |
| **Template system** | `{{VAR}}` replacement in `.tmpl.md` | None (pure markdown) | 4-tier cascade resolution | 3-tier TOML cascade | Markdown templates | Prompt builder pipeline |
| **Quality gates** | Phase gate with manifest | HARD-GATE prompt pattern | Clarification + analyze gates | Readiness checker + adversarial review | 4-level artifact verification | 6-plane invariant pipeline |
| **Code review** | Style → Architecture → Security | 2-stage: spec compliance → quality | N/A (spec-focused) | 3-layer parallel adversarial | Post-wave verification | Per-unit verification |
| **Context management** | `phase_context.md` (6-8K compact) | Curated per-subagent | Artifact traceability chain | Micro-file step loading (one at a time) | 1M adaptive enrichment | DB-authoritative + projections |
| **Customization** | Per-project agent generation | Skill selection | 4-tier template override | 3-tier TOML with merge semantics | Multi-runtime hooks | Plugin extensions |
| **Memory/state** | `agent_state/` + manifests | None (ephemeral) | Artifact chain | Decision log + sprint YAML | `.planning/` files | SQLite database |
| **Anti-hallucination** | Contract artifacts + reconcilers | Anti-rationalization tables | Clarification gates | Evidence grading (Confirmed/Deduced/Hypothesized) | Prompt injection scanning | Drift reconciliation |
| **Verification** | 3 reconciliation agents | Standalone verification skill | Consistency analysis | Implementation readiness gate | 4-level (Existence→Substance→Wiring→DataFlow) | Pre-dispatch 6-plane invariants |
| **Optimization** | Code optimizer + UI optimizer | N/A | N/A | N/A | N/A | N/A |
| **Session persistence** | Manifest handoff between phases | None | Artifact files | Decision log + frontmatter | STATE.md + context monitor | SQLite + crash recovery |
| **CI/CD integration** | `/deploy` command | None | GitHub Issues integration | None | None | Headless mode with exit codes |
| **Agent count** | 43 core + 8 templates | 14 skills | 7 commands | 30+ skills | 33 agents + 86 commands | 3 agents (Scout/Researcher/Worker) |

---

## 2. Prioritized Improvements

### P0 — Critical (Directly addresses known pain points)

#### P0-1: Anti-Rationalization Tables (from Superpowers)
**Problem:** Agents skip steps by reasoning their way to an exception ("this is simple enough to skip review").
**Solution:** Add a "Red Flags" table to every discipline-enforcing agent listing specific rationalizations the LLM might generate, paired with the correct response.
**Impact:** Prevents the #1 cause of agent non-compliance — not rule-ignoring but loophole-reasoning.
**Apply to:** code_reviewer_I, code_reviewer_II, security_reviewer, spec_impl_reconciler, acceptance_test_agent, code_optimizer, develop.md, review.md

#### P0-2: Two-Stage Review — Spec Compliance THEN Code Quality (from Superpowers)
**Problem:** Current review combines "did you build the right thing" with "did you build it well." Clean code that implements the wrong spec passes.
**Solution:** Add a "spec compliance" pass BEFORE code_reviewer_I that independently verifies implementation matches spec. Uses explicit distrust: "The implementer finished suspiciously quickly. Their report may be incomplete."
**Impact:** Catches spec deviations before they reach acceptance tests.

#### P0-3: Four-Level Artifact Verification (from GSD-1)
**Problem:** Current reconciler only checks "does it exist and match the spec." Doesn't catch hollow implementations (file exists but is a stub) or orphaned artifacts (file exists but nothing imports it).
**Solution:** Upgrade spec_impl_reconciler to 4-level verification:
1. **Existence** — file/function exists
2. **Substantiveness** — contains real implementation, not stubs or TODOs
3. **Wiring** — imported and used by other code (not orphaned)
4. **Data Flow** — real data flows through the connection (not dead path)
**Impact:** Catches the exact failure mode of AI-generated code: files that look complete but aren't connected.

#### P0-4: Analysis Paralysis Guard (from GSD-1)
**Problem:** Agents get stuck in read-loops, exploring the codebase endlessly without writing code.
**Solution:** If 5+ consecutive Read/Grep/Glob calls occur without an Edit/Write/Bash action, force the agent to either state its blocker or write code.
**Impact:** Trivial to implement, high impact. Saves context tokens wasted on unproductive exploration.

---

### P1 — High Impact (Architectural improvements)

#### P1-1: Implementation Readiness Gate (from BMAD)
**Problem:** `/develop` can start even if specs are incomplete or misaligned with BRD.
**Solution:** Add a mandatory pre-implementation gate to `/develop` Step 1 that validates: specs exist, phase_context.md is complete, BRD↔spec reconciliation passed, and all interface contracts are defined.
**Impact:** Prevents wasted implementation cycles when specs are incomplete.

#### P1-2: Clarification Gates in BRD Pipeline (from spec-kit)
**Problem:** Ambiguity in requirements propagates all the way to code, causing implementation rework.
**Solution:** Add mandatory ambiguity resolution between BRD analysis and writing. The `brd_interviewer` already asks questions — formalize this as a gate that blocks writing until critical ambiguities are resolved.
**Impact:** Front-loads ambiguity resolution, prevents costly rework.

#### P1-3: Progressive Planning — Sketch-Then-Refine (from GSD-2)
**Problem:** Planning all phases upfront produces stale specs. By Phase 3, the codebase has diverged from Phase 3's plan.
**Solution:** Plan current phase in full detail. Future phases as sketches (title, goal, risk, dependencies, rough scope). When a phase is about to start, refine its sketch into a full plan using the current codebase state.
**Impact:** Eliminates stale plans. Research backing: "95% per-step reliability over 20 steps = 36% success."

#### P1-4: Context Monitor Hook (from GSD-1)
**Problem:** Context window exhaustion is silent — the agent degrades without warning.
**Solution:** Hook that monitors remaining context. At 35% → warning. At 25% → critical, auto-record session state for resume.
**Impact:** Prevents silent degradation in long-running `/develop` sessions.

---

### P2 — Medium Impact (Operational improvements)

#### P2-1: Decision Log Pattern (from BMAD)
**Problem:** Decisions made in session 3 are invisible in session 7. Why was X chosen over Y?
**Solution:** `.decision-log.md` as canonical audit trail. Every architectural decision, requirement interpretation, or deviation recorded with context.
**Impact:** Persistent memory across sessions for WHY decisions were made.

#### P2-2: Evidence-Graded Investigation (from BMAD)
**Problem:** Debug/audit agents present all findings with equal confidence. Users can't distinguish fact from inference.
**Solution:** Three-tier evidence classification: Confirmed (directly observed with file:line), Deduced (logical chain shown), Hypothesized (plausible, stating confirmation conditions).
**Impact:** Better signal-to-noise in agent reports.

#### P2-3: Mid-Execution Escalation (from GSD-2)
**Problem:** Binary choice between "guess and hope" and "stop everything." No middle ground for uncertainty.
**Solution:** Structured escalation with options, tradeoffs, a recommendation, and `continueWithDefault: true`. Surfaces question to user while proceeding with best guess.
**Impact:** Unblocks autonomous execution while preserving user oversight.

#### P2-4: Workflow Size Budgets (from GSD-1)
**Problem:** Agent/command files grow without bounds, consuming more context tokens.
**Solution:** Enforce line limits per agent type. When exceeded, must decompose into references/templates.
**Impact:** Prevents prompt bloat, keeps agent context focused.

---

### P3 — Nice to Have

#### P3-1: Stakes Calibration (from BMAD)
**Problem:** Same rigor for a weekend project and an enterprise launch.
**Solution:** Single probe ("hobby / internal / launch") that calibrates entire pipeline rigor.

#### P3-2: Headless/CI Mode (from GSD-2)
**Problem:** Can't run phases in CI/CD pipelines.
**Solution:** `--headless` flag with structured JSON output and meaningful exit codes.

---

## 5. GSD Pattern Adoption Log (2026-05-21)

Patterns adopted from GSD g-stack review, implemented as 6 sprints:

| # | Pattern | Source | Implementation | Status |
|---|---------|--------|---------------|--------|
| GA-1 | **Discussion-before-planning** | GSD `gsd:discuss-phase` | `/discuss` command + `phase_assumptions_analyzer` + `decision_researcher` agents | ✅ IMPLEMENTED |
| GA-2 | **Session state persistence** | GSD `gsd:pause-work` / `gsd:resume-work` | `/pause` + `/resume` commands with `agent_state/sessions/` state files | ✅ IMPLEMENTED |
| GA-3 | **Persistent codebase knowledge** | GSD `gsd-codebase-mapper` | `/map` command + `codebase_mapper` agent with 4 parallel focus areas | ✅ IMPLEMENTED |
| GA-4 | **Goal-backward plan verification** | GSD `gsd-plan-checker` | `plan_goal_verifier` agent integrated into `/plan` Step 4b | ✅ IMPLEMENTED |
| GA-5 | **Parallel workstreams** | GSD `gsd:workstreams` | `/workstream` command (create, list, switch, status, complete, merge) | ✅ IMPLEMENTED |
| GA-6 | **Pipeline self-diagnosis** | GSD `gsd:health` / `gsd:forensics` | `/health` (integrity check + repair) + `/forensics` (post-mortem analysis) commands | ✅ IMPLEMENTED |
| GA-7 | **Evidence-graded assumptions** | GSD `gsd-assumptions-analyzer` + BMAD evidence grading | CONFIRMED/DEDUCED/HYPOTHESIZED classification in `phase_assumptions_analyzer` | ✅ IMPLEMENTED |

### Patterns NOT Adopted (with rationale)

| Pattern | Source | Why Skipped |
|---------|--------|-------------|
| `gsd:new-workspace` (worktree isolation) | GSD | Our phase-branch model achieves similar isolation |
| `gsd:set-profile` (model switching) | GSD | Our `settings.json` with per-agent model allocation is more granular |
| `gsd:profile-user` (behavioral profiling) | GSD | Auto-memory system is sufficient for user preferences |
| `gsd:review` (cross-AI peer review) | GSD | Novel but unclear ROI; our 4-layer review is comprehensive |
| `gsd:plant-seed` / `gsd:note` (idea capture) | GSD | Low priority; can be added later as /backlog command |
| `gsd:manager` (interactive command center) | GSD | Our /status + /workstream covers the use case |

---

## 3. Strengths We Have That Others Don't

| Our Strength | Who Lacks It |
|---|---|
| **Code optimization pipeline** (dead code + perf) | Everyone — unique to us |
| **UI↔API contract enforcement** | Superpowers, GSD, BMAD, spec-kit |
| **Phase-gated manifests** with carried-forward tracking | Superpowers, spec-kit |
| **Generated per-project agents** from templates | Superpowers, spec-kit, GSD-1 |
| **Skill pack system** (language + framework + DB) | Superpowers, spec-kit |
| **Reconciliation agents** (3 bidirectional checks) | Everyone except GSD-1 (which has 1) |
| **Tenant isolation verifier** | Everyone |
| **Acceptance test agent** with persona-based testing | Everyone except BMAD |

---

## 4. Key Architectural Insights

### From Superpowers: "LLMs don't violate rules by ignoring them — they violate rules by reasoning their way to an exception."
Anti-rationalization tables target the actual failure mode. Making rules louder doesn't help; closing the reasoning loopholes does.

### From GSD-2: "95% per-step reliability over 20 steps = 36% success."
Progressive planning addresses the compound reliability problem. Plan just-in-time, not all-at-once.

### From BMAD: "If you're naming features, picking MVP cuts, or proposing phases — you've crossed into authoring."
Requirements elicitation should be coaching (pulling vision from the user), not generation (LLM inventing requirements).

### From spec-kit: "Unit tests for English."
Natural language requirements can be validated programmatically — completeness, consistency, traceability.

### From GSD-1: "Existence → Substantiveness → Wiring → Data Flow."
Four levels of artifact verification catch the exact failure mode of AI-generated code.
