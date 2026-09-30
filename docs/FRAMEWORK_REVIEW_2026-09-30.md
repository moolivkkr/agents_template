# Framework review: orchestration breaks, how we compare, and a graph for tokens

Date: 2026-09-30. Scope: the startup-agents framework (69 core agents, 10 templates, 44 commands,
~239 skill-pack files, 4 hooks) against the Claude Code SDLC frameworks on GitHub, plus a trace of
our own orchestration and a design for representing code and project artifacts as a graph.

**Method.** Five research agents ran in parallel:

| Agent | What it covered |
|---|---|
| A | Spec-driven frameworks |
| B | Orchestration and unattended-run frameworks |
| C | Code graphs |
| D | Claude Code platform features |
| E | Our own orchestration, traced end to end |

Nine more profilers read the source of about 35 frameworks from local, read-only clones. None of
that code was executed.

**Sources.**
- Star counts: the GitHub API on 2026-09-30.
- Platform facts: the Claude Code docs fetched the same day, plus the installed Claude Code
  binary (v2.1.285) where the docs are silent.
- Internal findings: read line by line, and where marked **[R]**, reproduced. Target-project figures
  come from read-only analysis of 7 real projects that use the framework.
- The detailed reports stay outside this public repo, at `~/.claude/research/2026-09-30/`, because
  they quote file paths from private projects.

**Evidence limits.**
- Token figures are estimates from file sizes (bytes/4), calibrated on real projects. No per-agent
  transcript breakdown was available.
- Vendor benchmark numbers are labelled as such.
- Items not verified are listed in §8.

---

## Bottom line

1. **Our weakest point is keeping a run alive, not the design.** Every mature unattended framework
   keeps its control loop **in code** and gives each unit of work a fresh session, with timeouts,
   budgets, stuck detection and an external supervisor that restarts on crashes and API errors.
   Examples: GSD-2/gsd-pi, bmad-loop, Spec Kit 1.0 workflows, gsd-path, and the Ralph runners.
   Our `/autonomous` is one long turn held open by a Stop hook, and that hook has three confirmed
   bugs (§1-A).
2. **The gate that proves every agent ran can block clean phases and misses forged ones.** The
   evidence format is the problem, not the idea.
   - The markdown fallback counts "non-blocking" and severity legends as blockers. It would block
     17 of 21 clean reports on a real project [R].
   - `"report":"null"` is written as a string, which blocks every phase that has an agent with no
     report [R].
   - The honesty check keys on a manifest field nothing writes.
   - Gate output goes to stdout, which the model never sees when the hook blocks.
3. **The canonical `/develop` path has drifted from the documented one.**
   - The orchestrator never runs the optimizers, `documentation_agent`, `ui_audit_agent`, the
     readiness gate or API contract validation.
   - `database_agent` never enters the roster.
   - About 15 hand-offs are silently broken; one example is `/discuss` output never reaching `/plan`.
   - All 111 of our tests pass anyway, because they check structure, not behaviour.
4. **Tokens go mostly to documents, not code.**
   - A standard web phase loads about **2.0M first-read tokens across 22 agent spawns**.
   - About **73%** of that is agents told to read the whole `specs/` directory, the implementation
     guidelines (required by 53 agents) and the BRD (33 agents).
   - `phase_context.md`, built to replace those reads, is declared by only 5 agents.
5. **A deterministic graph we build ourselves is the right token lever.** It links requirements →
   specs → test-case IDs → tests → code → reports.
   - A prototype indexed a real 1,210-file project in 1.4 s.
   - It cut a unit-test agent's work list from about 210k tokens to about 1.9k.
   - It exposed 274 test-case IDs hidden inside range notation, which every one of our 45 grep scans
     misses, and a gate that passed with 60 of 377 IDs annotated.
   - For code structure, the language-server plugins (already installed) plus an optional code-graph
     CLI are enough. Third-party MCP memory services are not needed.
6. **We lead the field on verification depth.** Keep these:
   - the roster gate with a review floor;
   - five bidirectional reconcilers;
   - EARS-to-test-case traceability;
   - the independent test re-run;
   - deploy and health check before acceptance;
   - iOS/Android device testing;
   - Stitch design baselines;
   - security decisions that are never auto-resolved permissively.

   None of the frameworks studied has all of these.

---

## 1. Breaks found in our framework (verified)

Severity: **B** blocks or silently breaks the canonical path; **W** degrades it. Full list (27 B /
30 W) with file:line in report E.

### A. Unattended runs (`/autonomous`, hooks)

| # | Sev | Break | Evidence | Fix | Effort |
|---|---|---|---|---|---|
| A1 | B | `$1` in bash helpers inside command bodies is rewritten by Claude Code's argument substitution when a command gets 2+ args. `/autonomous` calls `develop-orchestrator --phase=N --auto`, so `in_roster`/`report_path` receive `--auto`. Affects `develop-orchestrator.md`, `develop.md`, `health.md`, `reconcile.md`, `worklog.md`. | Docs: `$N` = `$ARGUMENTS[N]`; binary regex `/\$(\d+)(?!\w)/g` applies inside code blocks | Use `${1}`; add a test guard | S |
| A2 | B | `autonomous-continue.sh` ignores the Stop input's `background_tasks`; the parent ends its turn while wave agents run in the background, and the run is marked `stalled`. | Stop input docs list `background_tasks`/`session_crons` "to distinguish done from waiting" | Exit 0 when either is non-empty | S |
| A3 | B | Progress = `run.json.updated`, bumped once per step; several turns inside one `/develop` step trip the stall. | `autonomous.md` writes run.json per step; waves write only checkpoints | Fingerprint progress from run.json, wave checkpoints, `execution.jsonl` line count, git HEAD | S |
| A4 | W | No session binding: a second session in the repo is blocked and spends the real run's nudges. | Anthropic's ralph-loop plugin binds to `session_id` | Bind the run to the first session; ignore others | S |
| A5 | B | API errors end the turn through `StopFailure`, not `Stop`; run stays `running` with nothing to resume it. | StopFailure docs (`rate_limit`, `overloaded`, `billing_error`, …) | StopFailure hook records the error; supervisor resumes (P1) | S |
| A6 | W | After compaction, invoked commands return truncated (5k each, 25k total, oldest first); `autonomous.md` is invoked first, so its driver rules can vanish. | Skills docs, compaction section | SessionStart(`compact`/`resume`) hook re-injects run state + next step | S |
| A7 | info | The 8-consecutive Stop-block cap counts blocks **without tool use**; a progressing run resets it. Not a limit for us, but `stop_hook_active` must not be used as an early exit (it stays true for the rest of the user turn). | Hooks docs + binary | Document; don't add a `stop_hook_active` guard | — |

### B. Gate and evidence spine

| # | Sev | Break | Evidence | Fix | Effort |
|---|---|---|---|---|---|
| B1 | B | `verify-gate.sh` markdown fallback false-blocks: counts "non-blocking", severity tables, legends; `total: 0` matches prose. Only 3 of 79 agents write JSON sidecars. | [R] 17 of 21 real clean reports blocked | Mandatory `<report>.json` sidecar `{verdict, blocking, warning, info, total, passed, failed}` for every roster agent; markdown fallback WARN-only | M |
| B2 | B | Completion line writes the string `"null"`; `e2e_orchestrator` and 4 others log a directory as their report. | [R] `develop-orchestrator.md:199`, `e2e_orchestrator.md:155` | Emit JSON null via `jq`; point reports at files | S |
| B3 | B | verify-gate writes only to stdout; exit-2 hooks show the model stderr only, so blocks carry no reason. | Hooks docs | stderr / JSON `decision:block` | S |
| B4 | B | Nothing writes the manifest's `.gate.passed`; the Stop sweep and the honesty check never run. The manifest write is a Bash `mv`, which the `Write\|Edit` PostToolUse matcher never sees. | 6 of 6 gated manifests on a real project lack it | Wave 6 writes a `.gate` object; the sweep also triggers on the `gate.passed` file; add `Bash` to the matcher | S |
| B5 | B | The orchestrator keeps its own regex gate. `total.*:\s*0\b` matches "Failed: 0". `grep BLOCKING` matches every reconciler report, because reconcilers are told to classify BLOCKING vs DEFERRED. | [R] | Delete; Wave 6 = `verify-gate.sh N` + graph TC gate | S |
| B6 | B | `test_runner`'s sidecar has no totals, so failing tests pass the gate. `/accept`'s regression calls an undefined function, and `\| tee` masks the exit code. | [R] | Sidecar totals; ship the helper; `pipefail` | S |
| B7 | W | Roster evidence is self-reported: agents write their own `completed` lines. | SubagentStop hook exposes `agent_type` | SubagentStop hook writes the ledger; the gate trusts only that | M |

### C. Canonical pipeline and hand-offs

| # | Sev | Break | Fix | Effort |
|---|---|---|---|---|
| C1 | B | `develop-orchestrator` never runs `code_optimizer`, `ui_code_optimizer`, `documentation_agent`, `ui_audit_agent`, the readiness gate or API contract validation, though `develop.md` calls them mandatory. | Decide per step: wire into a wave or retire; make `develop.md` a thin entry | M |
| C2 | B | `database_agent` never enters the roster, so Wave 2A.1 is always skipped. | Add when the phase declares schema changes | S |
| C3 | B | `e2e_workflows_unlocked` has no producer; e2e has nothing to run. | Read PHASE_PLAN §E2E Workflows; Wave 6 copies to manifest | S |
| C4 | B | `/discuss` writes `agent_state/phases/N/DISCUSSION.md`; `project_planner` reads `docs/design/phases/N/…`. | Fix the path | S |
| C5 | B | `/map --incremental` freezes after the first gate (post-gate step rewrites `.last-mapped` without re-mapping). | Separate `mapped_sha` from `validated_sha` | S |
| C6 | B | `/init` runs `impl_guidelines_agent` in parallel with the BRD it requires; re-running `/init` wipes `PROJECT_FACTS.md`. | Sequence; guard with `[ -f ]` | S |
| C7 | B | Test-case inventory is range-blind, phase-blind and priority-blind across 45 grep sites; manifest schema regex rejects `TC-E2E-*`. | Graph TC inventory + one deterministic TC gate (§4) | M |
| C8 | W | IMPLEMENTATION_GUIDELINES has three incompatible section layouts; ~10 consumers read "§3 Component Inventory", which the agent never writes. | One heading set, matched by name | S |

### D. State and operations

| # | Sev | Break | Fix | Effort |
|---|---|---|---|---|
| D1 | B | `remember.sh:91` uses bash-4 `${k,,}`; on macOS bash 3.2 a missing `--fact` records a blank fact that supersedes the real one [R]. | `tr` lowercase + explicit exit + test | S |
| D2 | B | `/reset-phase` can't archive (moves a dir into itself); stale `execution.jsonl` lets the roster gate pass on the previous attempt. | Archive the whole phase dir, or add `run_id` | S |
| D3 | B | `/health --fix` truncates `execution.jsonl`, destroying roster evidence. | Never truncate | S |
| D4 | B | `/rollback` can never run: nothing records the previous deploy. | `/deploy` records SHA, image, migrations; tag | S |
| D5 | W | ~40 `grep -P` recipes in commands work only inside Claude Code's shell (its `grep` is a shell function); macOS `/usr/bin/grep` rejects `-P`. Hooks and tests are clean. | Switch to `grep -E` over time | S |

---

## 2. How we compare

### Where we lead (keep, don't regress)

| Capability | Us | Closest peer |
|---|---|---|
| Proof every required agent ran, with a mandatory review floor | `verify-gate.sh` roster + floor, in code | gsd-core judges completion from disk/git; others trust the agent |
| Bidirectional reconciliation across requirements, BRD, specs, code and tests | 5 reconciler agents | Spec Kit `/converge` (spec↔tasks); MoAI SPEC linter |
| Test-case IDs traced from EARS clauses to test annotations | Yes (needs the graph to be correct, C7) | None at this depth |
| Independent test re-run cross-checking the writers' claims | Wave 3v `test_runner` | GSD-2 cross-checks claimed exit codes against real runs |
| Deploy + health before acceptance; iOS/Android device testing; Stitch page baselines | Yes | None |
| Security decisions never auto-resolved permissively | Yes | bmad-loop (CRITICAL vs PREFERENCE) is closest |
| Tiered memory with lesson-to-rule promotion | Yes | Compound Engineering's learnings store (better retrieval, see below) |

### Where we trail

| Technique | Best implementation seen | Us |
|---|---|---|
| **Control loop in code, fresh session per unit** | GSD-2/gsd-pi TS loop + rule table (`auto/loop.ts`, `auto-dispatch.ts`); gsd-path `claude -p` per task with child timeout and token budget; Spec Kit 1.0 workflow engine (`claude -p` per step, `state.json`, `workflow resume`); bmad-loop Python engine | One turn + Stop hook |
| **Supervision: timeouts, budgets, stuck detection** | GSD-2 soft/idle/hard timers (20/10/30 min), steer-then-skip, dollar ceiling; gsd-pi liveness backstop (fingerprints what each guard read, trips on the 2nd repeat, survives restarts — its ADR says the older detector wedged "roughly once a day"); bmad-loop failure-typed stalls (won't nudge a session stuck on a permission prompt) | Nudge counter only |
| **Headless contract** | GSD-2: exit codes 0/1/10/11, auto-restart ×3 with backoff, pre-supplied answers file, LLM-free status query | None |
| **Completion recorded by code, not self-report** | gsd-pi typed `gsd_task_complete` tool into SQLite; Superpowers `task-done` writes only if the test command exits 0; gsd-core judges from SUMMARY + scoped commits | Agents write their own ledger lines |
| **Test-first proven, not requested** | gsd-core: git check for a RED commit + a classifier that accepts only a genuine assertion failure (rejects zero tests, load errors, unexpected green) | Only `/hotfix` is test-first; `/develop` writes tests after code |
| **Bounded fix loops that skip rather than stall** | cc-sdd: 2 review rejections → debugger → 2 rounds → mark blocked, continue; Superpowers: fresh implementer on a stronger model after round 3 | Max-3 retry prose |
| **"Rulings, not stalls"** | Superpowers: only 4 stop classes halt; every other decision is a ledgered ruling with "cost if wrong" | Auto-resolved log (close), no stop-class taxonomy |
| **Delta specs for brownfield** | OpenSpec ADDED/MODIFIED/REMOVED/RENAMED merged transactionally into living specs; refuses to drop scenarios | Specs rewritten per phase |
| **Diverse, deterministic review** | BMAD reviewers given different inputs on purpose (diff-only, plan-skeptic, "would a test fail?", intent auditor fed the verbatim request); CE merges findings in code, same-model agreement never raises confidence | Named reviewers, same inputs |
| **Learning retrieval** | Compound Engineering: one learning per run with `applies_when`/`retire_when`, grep-retrieved top-5 at plan and review time | Lessons files, retrieval by prose |
| **Worktree parallelism** | Spec Kitty lanes grouped by file ownership; GSD-2 per-milestone worker leases | Candidate selection only |

---

## 3. The landscape (stars: GitHub API, 2026-09-30)

| Framework | Stars | Best idea to borrow | Trust notes |
|---|---|---|---|
| obra/superpowers | 293k | Test-gated completion ledger; rulings not stalls; bounded fix ladder | TDD by prompt only; telemetry logo from an external site |
| github/spec-kit (v1.0, 2026-08) | 139k | Workflow engine: `claude -p` per step, state + resume, pre-answerable gates; `/converge` | No step timeout; autonomy extras are community add-ons |
| ruvnet/ruflo (claude-flow) | 73.5k | Autopilot continuation generated in code | Headline SWE-bench/cost claims unverified |
| colbymchenry/codegraph | 72.4k | SQLite code graph with `callers/impact/affected --json` CLI | Telemetry on by default; installer edits `~/.claude` files — use the CLI only |
| Fission-AI/OpenSpec | 70.7k | Delta specs; CLI decides next step and returns JSON; typed errors instead of prompts | No subagents or review loop |
| gsd-build/get-shit-done | 64.4k (archived 2026-05) | — | Archived; `$GSD` token rug-pull recorded by its successor |
| bmad-code-org/BMAD-METHOD | 53.6k | Frozen intent block; diverse reviewers; revert-and-replan review routing | v7 removed sprint planning; fast-moving |
| codebase-memory-mcp | 45.5k | Fallback code graph, no telemetry | Authors' paper: ~10× fewer tokens but answer quality 0.92 → 0.83 |
| wshobson/agents | 40.1k | Large agent catalog | Catalog, not a pipeline |
| Yeachan-Heo/oh-my-claudecode | 39.4k | Stop-hook exemption for pending background work; session isolation | — |
| anthropics/claude-plugins-official | 37.2k | ralph-loop session binding; code-review confidence filter (drops < 80) | First-party |
| EveryInc compound-engineering | ~25k | Learnings store; deterministic review merge; spend caps | Sends diffs to other model providers by default |
| eyaltoledano/claude-task-master | 28.1k | Deterministic next-task selection; complexity-driven splitting | MIT + Commons Clause; loop runs with permissions skipped |
| snarktank/ralph, frankbria/ralph-claude-code | 21.9k / 9.6k | External loop that classifies each failure; circuit breaker | Hard failures can loop to the hourly budget |
| open-gsd gsd-core | 10k | Deterministic RED-evidence TDD gate; disk/git completion; PreToolUse guards | Maintainer-gated; updates checked each session |
| gsd-pi / gsd-path | — | Liveness backstop; headless contract; per-task `claude -p` driver | Postinstall downloads binaries; provider defaults to bypassing permissions |
| bmad-loop | 144 | Failure-typed stall handling; verify commands after every unit; token caps | Young |

**Supply-chain rule.** Borrow techniques; don't install these frameworks' installers, hooks or
unpinned `npx @latest` loops into your projects.

---

## 4. Graph design for tokens and correctness

### Where tokens go today (standard web phase, estimate)

| Item | First-read tokens |
|---|---|
| 22 agent spawns | ~2.0M |
| …of which whole `specs/` dir, IMPLEMENTATION_GUIDELINES, BRD | ~73% |
| Skill packs | ~374k |
| Parent live context across the phase | 150–230k (orchestrator file alone 17.5k) |
| `/plan` + `/design` | ~0.9M |

Early-loaded tokens are re-sent as cache reads on every later turn, so they cost the most.

### Design: `sdlc-graph` (framework-owned) + language servers for code

- **Artifact and traceability layer (build ourselves; no tool does this).**
  - Node types: requirements, phase, spec sections, test-case IDs (phase-namespaced, ranges expanded), endpoints, types, screens and Stitch pages, tables, test files, roster and execution entries, and reports.
  - Built deterministically from files we already produce.
  - Stored in SQLite, with a JSONL export, under `agent_state/graph/`.
- **Code layer, in rungs.**
  1. Regex extractors now.
  2. `go list` + gopls, the TypeScript compiler API, Python `ast` and tree-sitter per stack.
  3. Optional: pilot CodeGraph through its CLI, with telemetry off and without its installer.

  For precise lookups and type errors, agents use the Anthropic language-server plugins, which are
  already installed here.
- **Interface: a budgeted CLI, not MCP.** CodeGraph measured subagents using its MCP tool in about 1
  of 9 runs unless instructed; a CLI in the prompt is reliable. Commands:
  - `tc`, `context --agent <role>`, `diff-context`
  - `impact`, `consumers`, `trace`
  - `orphans`, `unlocked`, `gate`, `repomap`
- **Freshness.**
  - Incremental updates from git diff, with per-symbol hashes.
  - Full rebuild at every phase gate. CodeGraph's own drift figure under incremental sync is 1.3%.

**Who switches (median phase on a real project):**
- **Wave 3 test agents:** read the whole `specs/` dir today; with the graph, `context --agent` gives
  their work list in ~1.9k tokens, and they then open only the named sections (~81k → ~15–25k each).
- **Reviewers:** use `diff-context` (~83k → ~30k each).
- **Reconcilers and the TC gate:** use `tc --phase N` (~75–100k → ~3–8k), and the inventory becomes
  correct.
- **`breaking_change_reviewer`:** uses `consumers --changed-since`.
- **`e2e_orchestrator`:** uses `unlocked`, which fixes C3.
- **The parent at Waves 5–6:** uses `gate --summary`.
- **`/map`:** gets its structure from the graph, and the LLM writes only judgment.

**Expected savings.**
- Report E estimates −40 to 50% of first-read tokens per phase, counting spawn loads only.
- Report C estimates −8 to 20% of total tokens per `/develop` phase, counting everything, including
  the main session and output.
- These are different measures, not a contradiction. Both are estimates; the A/B plan in report E §7
  measures them on a frozen real phase with seeded defects.

**Prototype results.**
- On a real 1,210-file project the graph built in 1.4 s.
- It caught the range-hidden and cross-phase false passes.
- It reproduced the reconciler's coverage numbers within one.
- Known weakness: name-based call resolution conflates same-named methods. Rung 2 fixes this.

---

## 5. Recommended execution substrate for `/autonomous`

- **Now (after the S fixes):**
  - Keep the in-session Stop hook as the inner loop.
  - Run `/startup:autonomous` as a background session (`claude --bg`), which Claude Code's own
    supervisor restarts on a crash.
  - Set auto mode and auto-continue-after-usage-limit in **user** settings; project settings ignore
    `defaultMode: auto`.
- **Next: a thin external supervisor** (`scripts/startup-autonomous-run.sh`).
  - It runs `claude -p "/startup:autonomous --resume" --permission-mode auto --permission-prompts none --output-format stream-json`.
  - It reads `run.json` on exit: restart with backoff, stop at `awaiting_human` (exit 10), and
    enforce `max_cost_usd` / `max_hours` / `max_restarts`.
  - It sends local notifications only.
- **Target.**
  - The driver owns `run.json` and runs one fresh `claude -p` per step. The session boundary is
    configurable and A/B-tested with `/startup:eval`, because Anthropic's March 2026 guidance
    reports that continuous sessions also work on current models.
  - The `/develop` Wave 3/4 fan-out runs as a saved Workflow with schema-validated agent results.
  - Agent teams aren't used for the core: they're experimental, can't restore on resume, and don't
    spawn in `-p`.

---

## 6. Plan

**P0-now — verified small fixes (S, ~1 day)**
1. A1 `$1` → `${1}` + test guard.
2. A2–A4 hook: background-task exemption, progress fingerprint, session binding, JSON block reason.
3. A5 `StopFailure` hook.
4. A6 SessionStart re-orientation.
5. B2 JSON null + file reports.
6. B3 gate output to stderr.
7. B4 `.gate` object + sweep on the file + Bash matcher.
8. B5 delete orchestrator regex gates.
9. B6 test totals + `/accept` regression.
10. D1 `remember.sh`.
11. D2 reset-phase.
12. D3 health truncation.
13. C2, C4, C5, C6 path and sequence fixes.

**P0-next (M, ~1–2 weeks)**
- Evidence v2 sidecars for every roster agent, with verify-gate reading them (B1).
- SubagentStop-written execution ledger (B7).
- `sdlc-graph` artifact graph + deterministic TC gate (C7).
- Decide the orchestrator's missing steps (C1).
- One IMPLEMENTATION_GUIDELINES layout (C8).
- `e2e_workflows_unlocked` producer (C3).
- `/deploy` records for `/rollback` (D4).

**P1 (weeks 3–6)**
- Outer supervisor with budgets, exit codes and restart.
- Liveness backstop with fingerprints.
- Typed escalation / rulings ledger.
- Test-first RED-evidence gate run by `test_runner`.
- Bounded fix ladder that skips and continues.
- Precise code graph rungs + `impact`/`consumers`/`diff-context` in reviewers.
- Context diet:
  - W2–W4 read `phase_context.md` + graph packs instead of the whole specs/BRD/guidelines;
  - split `develop-orchestrator` into a skill folder with one file per wave;
  - skill packs into 8–12 umbrella Skills.
- Package as a `startup` plugin (commands, skills, hooks), keeping agents outside until bare-name
  resolution is verified.

**P2**
- Saved Workflow for the `/develop` fan-out.
- Fresh session per phase (A/B).
- Delta specs for brownfield changes.
- Diverse-input reviewers + deterministic finding merge.
- Learnings store with `applies_when`/`retire_when`.
- Worktree lanes for independent phases.
- `/eval` with token accounting.

---

## 7. Corrections to earlier reviews

- **FRAMEWORK_REVIEW_2026-09 (yesterday):**
  - Serena is GPL-3.0 (29.9k stars), not MIT (~25k).
  - CodeGraph's numbers are vendor figures from one architecture question per repo, and its file
    watcher runs only inside its MCP server.
  - arXiv 2601.08773 is small: one author, Java only, 45 questions.
  - The "RepoMap best at 8k" result (2607.24882) holds by ~1.5% and measures Aider's tool, not ours.
  - F7 ("no language servers") is out of date: gopls, pyright and typescript-language-server are
    installed and enabled.
- **GSD:** the upstream repo was archived on 2026-06-26, not in May. Its successor records the
  maintainer going silent around 2026-04-01 and a `$GSD` token rug-pull around 2026-05-22.
- **May `competitive-analysis.md`:** out of date on Spec Kit (1.0 workflow engine) and BMAD (v7,
  bmad-loop).
- **This session:** `grep -P` works only inside Claude Code's shell, not system-wide as I said on
  2026-09-29.

## 8. Not verified

- Whether plugin agents still resolve by bare name. The plugin-packaging decision depends on it.
- Where SubagentStart hook context is delivered.
- `Skill(startup:*)` permission syntax.
- Behaviour of `\$1` with no arguments.
- Whether the 10k-character hook output cap applies to stderr.
- Whether the Agent SDK can use a personal subscription.
- A claim in the Ralph docs that headless `claude -p` billing is moving to API credits. Check this
  before building the target driver.
- ruflo's SWE-bench and cost figures; oh-my-claudecode's token-savings figures.
- All token savings in §4 are estimates until the A/B run.

## Detailed reports (local, not committed)

`~/.claude/research/2026-09-30/`:
- `A_spec_frameworks.md`, `B_orchestration_frameworks.md`, `C_code_graph.md`, `D_claude_code_platform.md`, `E_internal_analysis.md`
- `profiles/`: source-level profiles of about 20 frameworks
- `prototypes/`: `sdlc_graph.py`, `tracegraph_proto.py`, `measure_tokens.py`
