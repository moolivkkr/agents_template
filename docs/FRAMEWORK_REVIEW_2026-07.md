# Framework Ultra-Deep Review — 2026-07-07

Six parallel deep-dive agents reviewed the framework across four internal seams (orchestration,
agent roster, skills, enforcement) and two external tracks (SOTA multi-agent frameworks; deterministic
verification + memory patterns). This doc records the findings, what was fixed in this pass, and the
remaining backlog.

**Verdict: B+ / A−.** More deliberately engineered around real multi-agent failure modes than any
public SDLC framework benchmarked. External research: *"I did not find a public SDLC agent framework
with a code-enforced roster + report + gate-honesty contract like yours."* Weaknesses were (1) a
cluster of silent-failure bugs where prose-computed values were referenced as shell state, (2) two
orchestrators drifted apart, and (3) "deterministic" claims that were actually model-executed prose.

---

## What was genuinely strong (preserved)

- `verify-gate.sh` — a real Stop + PostToolUse hook that makes a forged `gate.passed` un-committable.
- Separate named reviewers + self-correction ban — supported by the reflection literature.
- Tier-0 `(subject,relation)` deterministic fact supersession — *more* rigorous than Mem0/Letta.
- Backend/skills coverage — 88 archetype files across 5 languages (the review brief's "thin" premise
  was inverted; the real coverage gap is `infrastructure/`, 6 files).
- Roster execution gate + TC-* traceability — map 1:1 onto the MAST failure taxonomy.

---

## P0 — correctness bugs (FIXED, commit bc20163)

Cross-confirmed by multiple review agents; each was a silent-failure path.

| # | Bug | Fix |
|---|-----|-----|
| 1 | `--force_gate` and `verify-gate.sh` contradicted — a forced gate was hard-blocked (exit 2), making the documented override unreachable | Hook now honors a well-formed `gate.forced` (downgrades finding-blockers to a loud WARN), while still hard-blocking a structurally incomplete roster |
| 2 | Roster required-report check used a `"status":"required"` object grep that can never match the flat-array roster schema → tenant_isolation report silently dropped | jq membership test in both develop.md + develop-orchestrator.md |
| 3 | `e2e_test_agent` was a required roster name with no agent file (gate does exact-name membership) | → `e2e_orchestrator` (the real agent) in roster, Wave 3c, solution_selector downstream |
| 4 | Candidate-selection complexity trigger read `${RAW_SCORE}` from an unset shell var (always 0 = dead code) | Reads `.raw_score` from complexity.json; `raw_score` added to the schema in scale-adaptive-depth.md |
| 5 | `autonomous.md` bypassed the canonical orchestrator (implicit), and referenced non-existent `phase_verifier` | Explicit MANDATORY orchestrator note per phase; `phase_verifier` → `plan_goal_verifier` |
| 6 | `ui_developer` template referenced a dead skill path (`backend/archetypes/shared-backend-patterns.md`) | → `core/shared-backend-patterns.md` |
| 7 | 8 stale, git-tracked, divergent `generated/*.tmpl.md` copies (agent_factory could ship stale agents) | `git rm` + gitignored the dir (populated at `/init`) + `.gitkeep` |
| 8 | INVENTORY.md said 58 core agents (actual 63); omitted 4 agents | Regenerated: count fixed, 4 agents added to detail + category tables |

Also: the two divergent gate implementations (develop.md inline vs develop-orchestrator Wave 6) both
carried the copy-pasted bug #2 — both fixed. (Full collapse to a single gate remains P2.)

---

## P1 — make enforcement real (FIXED, commit 391d63f)

The enforcement review's core finding: the framework has one genuinely deterministic mechanism
(`verify-gate.sh`), guarding a chain of *model-authored* evidence. Two of the most-claimed
"deterministic" guarantees were actually model-executed prose. Now code:

1. **Mandatory roster FLOOR** (verify-gate.sh check a2). Closes the #1 bypass: a model-authored thin
   roster that drops `security_reviewer` passed the completeness check trivially. Now any phase with
   an implementation agent MUST carry the review floor (code_reviewer_I/II, security_reviewer,
   code_quality_verifier), enforced from roster composition — not overridable by `--force_gate`.
2. **`remember.sh`** — real deterministic bi-temporal supersession (id assignment, exact-key status
   flip, atomic append). `/remember` no longer hand-edits markdown. Also strips the template's
   pedagogical `<!-- example -->` so it can't become a phantom fact.
3. **`inject-project-facts.sh` made comment-aware** — a latent bug: the SessionStart hook parsed the
   commented example as a real active fact and injected a phantom F-001 into every session.

**Regression tests** (`tests/`, run via `tests/run-all.sh`): 14 assertions guarding verify-gate (9)
and remember (5). Wire into CI / pre-commit so weakening a guarantee fails the build — the CODE form
of eval task T-004.

---

## Remaining backlog (NOT yet done)

### P2 — SOTA-backed upgrades (evidence-ranked)
- **verify-gate.sh should RUN the tests/lint/typecheck itself**, not audit a markdown report claiming
  they passed. Judged the single biggest available win (SWE-bench/AgentForge/ReVeal all execution-ground).
- **In-flight process verification (PRMs)** inside long waves — a taxonomy-guided "still on-spec?"
  check lifted SWE-bench Verified +10.6pts *and shortened* trajectories (arXiv 2509.02360).
- **Schema-force agent reports to JSON** validated by jq at PostToolUse — kills the brittle grep/awk
  parsing; constrained decoding raises compliance ~35%→~100%.
- **EARS notation for acceptance criteria** ("WHEN [condition] THE SYSTEM SHALL [behavior]") — cheapest
  high-impact win; every FR-* becomes directly testable and 1:1-mappable to a TC-* (from Amazon Kiro).
- **Procedural-memory tier** — `/consolidate` should promote recurring lessons into enforced
  hooks/skills, not more prose (the missing CoALA quadrant).
- **Collapse the two gate implementations** into one (delete develop.md's duplicated gate bash).

### P3 — coverage gaps
- Add `reliability_agent` (SLO/error-budget) and `threat_model_agent` (STRIDE) — the roster deploys to
  prod with no reliability owner and no design-time security.
- Add `accessibility_auditor` (axe/WCAG-AA against built UI).
- Deepen `infrastructure/` skills (cloud primitives, secrets, caching, auth-flow) — the real frontier,
  not more languages.
- Wire in or retire ~10 orphaned skills (e.g. `external-service-mocks.md`, `query-optimization.md`).
- Consolidate the diagram tier (eagle→c4) and parameterize the 6 near-identical reconcilers.

### Standing caution
mini-SWE-agent (~100 lines) scores >74% on SWE-bench Verified. Scaffold complexity has diminishing
returns — use `/eval --compare` to confirm each wave earns its keep.
