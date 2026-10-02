---
command: develop-orchestrator
description: "Wave-by-wave orchestration for /develop. The PARENT session follows this script, spawning separate agents per wave. This prevents the single-agent problem where reviews get dropped."
arguments:
  - name: phase
    required: false
    description: "Phase number. Omit to auto-detect."
  - name: auto
    required: false
    default: false
    description: "Autonomous mode (set by /autonomous or an active run.json): escalations auto-resolve with the recommended option and are logged; no user prompts."
---

# /develop Orchestrator — Wave-by-Wave Execution

> **Auto mode.** `--auto` is set, OR `agent_state/autonomous/run.json` has `"status":"running"` (this
> command was invoked by `/autonomous`). In auto mode, never wait for the user: every "surface to
> user" / "escalate to user" / STOP-for-input point below instead auto-resolves with the recommended
> option, is logged to `agent_state/autonomous/auto-resolved.jsonl` (full question, options, choice,
> rationale, category; `"category":"security","security_flag":true` for security topics), and is
> carried forward to the next human checkpoint. The exception is a security decision with no
> hardened default, which sets `run.json` `status` to `awaiting_human`. The closing "▶ Next: …" line
> is for standalone use only; under `/autonomous`, return control to it without ending the turn.

**This command runs in the parent session itself, not in a subagent.**

The parent reads this script and executes each wave as a separate Agent tool call, verifying outputs between waves. This is the structural enforcement that prevents review/acceptance steps from being dropped.

---

## Auto-Checkpoint Protocol (inspired by agentmemory hook patterns)

Between EVERY wave boundary, the parent session automatically captures a lightweight checkpoint. This eliminates the need for explicit `/pause` — if context resets mid-pipeline, `/resume` can reconstruct state from the last checkpoint.

**Checkpoint format:** `agent_state/phases/${PHASE}/checkpoints/wave-${N}.json`

```json
{
  "ts": "<ISO timestamp>",
  "phase": N,
  "wave_completed": N,
  "wave_next": N+1,
  "git_sha": "<short SHA>",
  "artifacts_produced": ["<paths written this wave>"],
  "findings_summary": "<1-2 lines from wave output>",
  "tests_passing": true|false|null,
  "blocking_issues": []
}
```

**Write checkpoint AFTER each wave verification passes:**
```bash
mkdir -p "agent_state/phases/${PHASE}/checkpoints"
cat > "agent_state/phases/${PHASE}/checkpoints/wave-${WAVE_NUM}.json" << EOF
{
  "ts": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "phase": ${PHASE},
  "wave_completed": ${WAVE_NUM},
  "wave_next": $((WAVE_NUM + 1)),
  "git_sha": "$(git rev-parse --short HEAD)",
  "artifacts_produced": [<list files created this wave>],
  "findings_summary": "<extract from agent result>",
  "tests_passing": null,
  "blocking_issues": []
}
EOF
```

**On `/resume` detection:** If `checkpoints/wave-N.json` exists but `wave-$((N+1)).json` does not, resume from Wave N+1 without re-running earlier waves.

**Key difference from agentmemory:** These are deterministic structural checkpoints (known paths, known schema), not semantic observations. No retrieval search needed — the resume logic reads the latest checkpoint file directly.

---

## Resume Summary at Every Wave Boundary

After writing each wave checkpoint, refresh `checkpoints/compact-context.md` before starting the next wave. It is the self-contained record a session needs to continue the phase after Claude Code compacts the conversation or after `/resume` in a new session, so it must stand on its own: after a compaction, the orchestrator reads only this file and `phase_context.md` to know what happened and what comes next.

Don't pause, wrap up, or skip work because the conversation is getting long. The main session runs with a 1M-token context window, and Claude Code compacts automatically as it nears the limit; the summary below is what carries the phase across that. (Only the user can run `/compact`; there is no need to ask for it.)

   ```bash
   mkdir -p "agent_state/phases/${PHASE}/checkpoints"
   cat > "agent_state/phases/${PHASE}/checkpoints/compact-context.md" << EOF
   # Compact Context — Phase ${PHASE} (post-Wave ${WAVE_NUM})
   Generated: $(date -u +%Y-%m-%dT%H:%M:%SZ)
   Reason: wave-boundary resume summary

   ## RESUME INSTRUCTIONS
   If this session was compacted or restarted, read THIS file + docs/design/phases/${PHASE}/phase_context.md.
   Then continue directly to Wave $((WAVE_NUM + 1)) of the develop-orchestrator.
   Do NOT re-run Waves 1-${WAVE_NUM}. Do NOT re-read files already summarized below.

   ## Phase Goal
   <1 line from phase_context.md>

   ## Completed Waves
   - Wave 1 (Orient + Audit): <summary> — artifacts: [agent_state/phases/${PHASE}/audit_report.md]
   - Wave 2 (Implement): <summary> — artifacts: [<list source files>]
   ...repeat for each completed wave, pulling from checkpoint JSONs...

   ## Key Decisions Made This Session
   - <architectural decisions, pattern choices, deviations from spec>
   - <e.g., "Used repository pattern with interface DI per IMPL_GUIDELINES">

   ## Blocking Issues
   - <none, or list with severity>

   ## Current State
   - Git SHA: $(git rev-parse --short HEAD)
   - Tests: <passing/failing/not-yet-run>
   - Files modified this session: $(git diff --name-only HEAD~${WAVE_NUM} HEAD 2>/dev/null | wc -l | tr -d ' ') files

   ## Next Steps
   - Wave $((WAVE_NUM + 1)): <what this wave does — copy from orchestrator>
   - Remaining waves after that: <list>
   EOF
   ```

**After a compaction or a resumed session**, read `compact-context.md` first, then `phase_context.md`, and continue with the wave its Next Steps names. Don't re-run completed waves or re-read files it already summarizes.

## Wave 0: SCALE THE WORKFLOW DEPTH

Before Wave 1, classify phase complexity and scale how many waves run — do not pay full
six-wave ceremony for a typo fix. See `~/.claude/skills/core/scale-adaptive-depth.md`.

| Class | Signals | Waves to run |
|-------|---------|--------------|
| **trivial** | 1 file, no shared layer, copy/typo | scoped edit + test only (skip audit/TRD/review waves) |
| **small** | ≤2 components, no shared layer | Waves 2, 3, 6 (light) |
| **standard** | multi-component or brownfield | full Waves 1–6 (default) |
| **platform** | shared layer, new subsystem, many FR-* | full 1–6 + decision pass (DECISIONS.md; ADR files and diagrams only if the docs policy has them on) |

Complexity also drives model routing (`model-routing.md`); this drives *workflow depth*. Upgrades
allowed mid-run (escalate if a "small" phase turns out to touch a shared layer); never silently
downgrade. Record the chosen class in the Wave-0 checkpoint.

### Wave 0b — Write the Expected Agent Roster (execution guarantee)

**This is the structural fix for "did every agent actually run?"** The parent computes the roster of
agents this phase MUST execute (derived from the scale class + project shape) and writes it to
`agent_state/phases/${PHASE}/roster.json`. Wave 6 (and the `verify-gate.sh` hook) diffs this roster
against what actually completed (`execution.jsonl`) and BLOCKS the gate if any `required` agent has no
`completed` entry. This turns "we hope the reviewers ran" into "we proved they ran."

**Contract — `roster.required` MUST use the REAL agent names, verbatim, exactly as each agent logs
itself into `execution.jsonl` (the `"agent"` field).** Never use generic slot labels like
`wave1_audit` or `e2e_or_ui_test_agent` — the completeness diff is a straight set-membership check
(`roster.required ⊆ {agents with a completed line}`), and slot labels live in a different namespace
than the logged agent names, so they would false-block or silently pass. The roster schema is a flat
`required` array of names, aligned with `.claude/hooks/verify-gate.sh`:

```json
{"phase": N, "required": ["<agent-name>", ...]}
```

**Derive the roster from the set of agents this phase will actually spawn** (so `required` ⊇ the
gate's required-report set — no drift). Base list for a STANDARD phase, using the real names each
Wave spawns:

```bash
mkdir -p "agent_state/phases/${PHASE}"
# Base STANDARD roster — REAL agent names (must match the "agent" field each writes to execution.jsonl).
# Tailor per scale class + project shape:
#  - trivial/small: keep only the agents whose waves you actually run.
#  - not multi-tenant: DROP tenant_isolation_verifier from the array (record the skip in the manifest).
#  - no web UI: use e2e_orchestrator (not ui_test_agent); DROP ui_developer/ui_test_agent/design_quality_reviewer.
#  - web UI: ADD ui_developer, ui_test_agent, accessibility_auditor (WCAG-AA against the built UI),
#    and design_quality_reviewer if used, to the array.
#  - React Native mobile app (agent_registry.json tech_profile.mobile.enabled = true) and the phase
#    touches mobile screens: ADD mobile_developer, mobile_test_agent, mobile_e2e_orchestrator,
#    mobile_platform_auditor. All four are required whenever a mobile screen changed: device flows on BOTH iOS and Android are
#    the only proof a native app works. (Web e2e_orchestrator never covers native screens.)
#  - web UI or mobile screens changed: ADD ui_standards_auditor (built pages vs design standards and
#    each page's Stitch baseline, whole app; see /ui-audit).
#  - touches auth/PII/trust-boundary: ADD threat_model_agent (design-time STRIDE; usually run in /plan
#    but list it here if the phase itself introduces the security-relevant surface).
#  - adds/changes a service with an NFR-PERF-*/availability target: ADD reliability_agent.
#  - declares schema changes (new/changed tables in the specs or a data-model section): ADD database_agent
#    (Wave 2A.1 schema design — it is NOT in the base list, so without this rule 2A.1 never ran).
#  - has DB migrations: ADD migration_agent AND migration_safety_reviewer (adversarial migration review).
#  - project has deploy/k8s/app.env (lab cluster): ADD deploy_dev AND deploy_qa. They are not spawned
#    agents: scripts/k8s/deploy.sh logs them (PHASE set) in Wave 3.5 and again in Wave 5v, and the gate
#    requires both, bound to the current code commit.
#  - the phase has NFR-PERF-* targets in scope: ADD performance_agent (Wave 4 Track D, a gated load test
#    on qa). With an availability/SLO target also ADD reliability_agent (Track D code checks).
#  - changes a cross-phase contract (API/type/event/column consumed by an earlier phase): ADD breaking_change_reviewer.
#  - platform: ADD adr_agent (decisions to docs/DECISIONS.md; spawn it with MODE: ledger-only unless
#    `docs-policy.py is-on adr_files`). ADD architecture_orchestrator ONLY if
#    `python3 .claude/hooks/docs-policy.py is-on architecture_diagrams` exits 0 (off in the lean docs
#    profile — the diagrams are optional; record the skip in skipped_agents[]).
#  - PHASE_PLAN.md says `Mode: as-built` (/plan --as-built): DROP the implementation agents that have no
#    gap work (record each in skipped_agents[] with reason "as-built baseline"); keep every test,
#    review, reconcile and acceptance agent. The phase's job is the test + acceptance baseline.
#  - candidate-selection will run this phase (Wave 2 mode N>=2 — PLATFORM / high-complexity /
#    prev-failure / --candidates=N): ADD solution_selector. It is a REQUIRED agent whenever N>=2, so
#    its completed line + candidate_selection.md report are proven by the Wave-6 roster check. When
#    N==1 (single implementation), OMIT it (record candidate_selection:skipped in the manifest).
REQUIRED='["backend_audit_agent","backend_developer","api_developer","unit_test_agent","integration_test_agent","e2e_orchestrator","test_runner","code_reviewer_I","code_reviewer_II","security_reviewer","dependency_scanner","code_quality_verifier","spec_impl_reconciler","spec_test_reconciler","acceptance_test_agent","tenant_isolation_verifier"]'
python3 - "$REQUIRED" "${PHASE}" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" > "agent_state/phases/${PHASE}/roster.json" << 'PY'
import json, sys
required = json.loads(sys.argv[1])
print(json.dumps({"phase": int(sys.argv[2]), "generated": sys.argv[3], "required": required}, indent=2))
PY
```

**Every wave that spawns an agent must append a completion line to the execution log** so Wave 6 (and
`verify-gate.sh`) can verify it. `${AGENT_NAME}` MUST be the same real name that appears in
`roster.required`, and `report` MUST be the relative path to that agent's primary output (or `null`
if it produces none). After each agent returns successfully:
```bash
mkdir -p "agent_state/phases/${PHASE}"
# jq builds the line so a missing report is JSON null (a quoted "null" string, as older templates
# wrote, made verify-gate look for a file named "null"). REPORT_PATH must be a FILE, never a directory.
jq -nc --arg a "${AGENT_NAME}" --argjson p "${PHASE}" --arg r "${REPORT_PATH:-}" --arg ts "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  '{agent:$a, phase:$p, status:"completed", report:(if $r == "" then null else $r end), ts:$ts}' \
  >> "agent_state/phases/${PHASE}/execution.jsonl"
```

If you deliberately skip an agent (e.g. not multi-tenant, trivial phase), **omit it from
`roster.required`** and record the skip + reason in the phase manifest (`skipped_agents[]`) — an
explicit, documented omission is auditable; leaving it `required` and never running it is the exact
bug this roster exists to catch. (`test_runner`, `spec_test_reconciler` and — unless the manifest
records `acceptance.not_applicable` with a reason — `acceptance_test_agent` can't be skipped in an
implementation phase: `verify-gate.sh` enforces them as a floor.)

### Wave 0c — Commands, base commit, evidence directories

```bash
# 0. Framework hooks the gate and the evidence steps need (projects created before 2026-09-30 lack them).
for h in verify-gate.sh junit-to-sidecar.py tc-inventory.py sdlc-graph.py commands-table.py acceptance-map.py docs-policy.py debate-status.py remember.sh stitch-state.py stitch-capture.mjs stitch-fidelity.py; do
  [ -f ".claude/hooks/$h" ] || { mkdir -p .claude/hooks && cp "$HOME/.claude/hooks/startup/$h" .claude/hooks/ && chmod +x ".claude/hooks/$h"; } \
    || echo "⛔ BLOCKED: .claude/hooks/$h missing and not staged in ~/.claude/hooks/startup (run ./install.sh from the framework repo)"
done
P="agent_state/phases/${PHASE}"; mkdir -p "$P/junit" "$P/reports" agent_state/config
# Older projects' settings.json predates the spawn-depth cap: say so (the user decides; don't edit settings here)
jq -e '.env.CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH' .claude/settings.json >/dev/null 2>&1 \
  || echo "⚠ .claude/settings.json has no env.CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH (2): nesting is capped at Claude Code's default of 3, so a wave agent that spawns debate_moderator itself won't be stopped. Re-run new-project.sh or add it."
# Decisions raised during /plan, /discuss or /design are made before any code is written
# (child-returns.md § "Before a command finishes"): dispatch every topic this lists, then re-check.
python3 .claude/hooks/debate-status.py --phase "${PHASE}" --check \
  || echo "⛔ Open debates above: run debate_moderator for each (and relaunch requesters) before Wave 2"
# 1. The project's real commands (IMPLEMENTATION_GUIDELINES §Commands and versions) as JSON. Every agent,
#    test_runner and the gate's execution check (verify-gate.sh (e)) run exactly these — nobody guesses.
python3 .claude/hooks/commands-table.py docs/IMPLEMENTATION_GUIDELINES.md --out agent_state/config/verify-commands.json \
  || echo "⛔ BLOCKED: IMPLEMENTATION_GUIDELINES has no usable '## Commands and versions' table (skills/core/commands-and-versions.md) — add it before Wave 2"
# 2. The commit this phase starts from: test-weakening diff (tc-inventory.py --diff-base) and scope for reviewers.
[ -f "$P/base_sha" ] || git rev-parse HEAD > "$P/base_sha"
# 3. Spec TC priorities for the results converters.
python3 .claude/hooks/tc-inventory.py --phase "${PHASE}" --spec-only --out "$P/tc_priorities.json"
# 4. The project graph (agent_state/graph/): agents' work lists (`context`), reviewers' `diff-context`, the TC gate.
#    Queries refresh it incrementally; the gate rebuilds it in full. If it can't build, agents fall back and say so.
python3 .claude/hooks/sdlc-graph.py build >/dev/null \
  || echo "⚠ sdlc-graph build failed: agents fall back to reading specs/ whole (they must say so in their reports)"
```

Evidence rules for every test tier are in `~/.claude/skills/testing/test-results-sidecar.md`: JUnit XML
under `$P/junit/`, converted by `.claude/hooks/junit-to-sidecar.py`, **committed code only**. The gate
rejects evidence that doesn't match the current code commit.

---

## Ground-Truth Injection on Every Spawn

**Step detail on demand.** The full procedure for each /develop step lives in its own file under `~/.claude/skills/core/develop-steps/` (index in `~/.claude/commands/startup/develop.md`). When a wave agent needs more than the prompt below gives it, add the matching path(s) to its prompt - for example `step-2-implementation.md` for Wave 2, `step-3-tests.md` for Wave 3, `step-6-phase-gate.md` for the gate - so it reads only its own step instead of the whole pipeline.

Every `Agent prompt:` in this orchestrator MUST begin with the ground-truth injection line so
Tier 0 facts reach every subagent (subagents do not inherit the conversation). Prepend verbatim:

```
GROUND TRUTH: First read docs/PROJECT_FACTS.md (Tier 0 facts) AND docs/DECISIONS.md (Tier 0.5
settled decisions). They list retired/renamed components, hard constraints, environment facts, and
prior decisions with rationale, and they OVERRIDE any conflicting assumption in this prompt or your
training. If this task touches anything marked RETIRED/superseded/reversed there, stop and flag it
instead of proceeding. Do not re-litigate an active decision without new evidence.
```

The wave prompts below omit this line only for brevity — you must add it to each. See
`~/.claude/skills/core/shared-context-protocol.md`.

## Spawning agents and reading what they return

Follow `~/.claude/skills/core/child-returns.md` for every spawn in this orchestrator. In short:
- **Wait for every agent you spawn** before verifying its wave. Where the Agent tool offers
  `run_in_background`, pass `false` and put a wave's independent agents in one message. In an
  interactive session with fork mode on, the parameter doesn't exist, so wait for each completion.
- **Act on the first line of each return:**
  - `NEEDS_INPUT`: ask the user, or under `--auto` record a default.
  - `NEEDS_DECISION <topic>`: run `debate_moderator`, then relaunch the agent with the decision.
  - A progress note: re-spawn the agent, at most twice.
- **Escalating yourself:** when this orchestrator needs a decision (an architectural failure in a
  fix loop, a replan cap), write `agent_state/debates/<topic>.request.json` yourself, with
  `from_agent: develop-orchestrator`, and then run the debate the same way.
- **Run non-blocking requests at the end of the wave that raised them.**

The project settings cap nesting at two levels (`CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH=2`):
- this session → `debate_moderator` → researchers, advocates and arbitrators is the deepest a debate goes
- a wave agent never spawns the moderator itself

## Wave 1: ORIENT + AUDIT

Spawn `backend_audit_agent` (and `ui_audit_agent` in parallel for UI phases), prepending the GROUND TRUTH line:

```
Agent prompt (subagent_type: backend_audit_agent): "[GROUND TRUTH line] You are running Wave 1 (Orient + Audit) for Phase ${PHASE}.
WORKING DIRECTORY: ${PROJECT_DIR}
Read: docs/PROJECT_FACTS.md (ground truth), docs/design/phases/${PHASE}/phase_context.md, IMPLEMENTATION_GUIDELINES.md
Produce: agent_state/phases/${PHASE}/audit_report.md
Identify gaps, existing code, what needs to be built.
If the audit finds a component that is dead/retired, propose a /remember fact (confidence: reported)."
```

**Verify before proceeding:**
```bash
test -f agent_state/phases/${PHASE}/audit_report.md || echo "⛔ BLOCKED: audit_report.md missing"
```

**Auto-checkpoint:** Write `checkpoints/wave-1.json` with `artifacts_produced: ["audit_report.md"]`.

---

## Wave 2: IMPLEMENT

**Two modes.** Default = a **single** implementation (Wave 2A). Hard/high-value phases run
**candidate-selection** (Wave 2B): N independent implementations + a selector picks the winner. Decide
the mode FIRST, then run exactly one branch below.

### Wave 2 Mode Decision (candidate-selection gate)

Run candidate-selection ONLY when a trigger fires — it costs ≈N× the Wave-2 tokens, so it is OPT-IN,
not the default (see `~/.claude/skills/core/candidate-selection.md` §When it triggers). Evaluate:

```bash
# N = 1 means "single implementation" (default). N in [2,3] turns on candidate-selection.
N=1; TRIGGER=""
CLASS=$(python3 -c "import json;print(json.load(open('agent_state/phases/${PHASE}/complexity.json')).get('complexity_class',''))" 2>/dev/null || echo "")
# raw_score is the model-routing complexity score (see model-routing.md). It is PERSISTED into
# complexity.json by Wave 0 / scale-adaptive-depth; read it from there (default 0 if absent) — do
# NOT reference an unset shell var (the old `${RAW_SCORE:-0}` was always 0, so this trigger was dead).
RAW_SCORE=$(python3 -c "import json;print(int(json.load(open('agent_state/phases/${PHASE}/complexity.json')).get('raw_score',0)))" 2>/dev/null || echo 0)
PREV_FB="agent_state/phases/$((PHASE-1))/reports/collective_feedback.md"

if [ -n "${ARG_CANDIDATES:-}" ]; then                     # explicit --candidates=N (clamped 2..3)
  N=$(( ARG_CANDIDATES < 2 ? 1 : (ARG_CANDIDATES > 3 ? 3 : ARG_CANDIDATES) )); TRIGGER="flag"
elif [ "$CLASS" = "platform" ]; then                      # scale-class PLATFORM
  N=2; TRIGGER="platform"
elif [ "${RAW_SCORE:-0}" -gt 60 ]; then                   # high model-routing complexity (>60)
  N=2; TRIGGER="complexity"
elif [ -f "$PREV_FB" ] && grep -qiE "phase ${PHASE}|<this-component>" "$PREV_FB" 2>/dev/null; then
  N=2; TRIGGER="prev-failure"                             # prev-phase failure touched this component
fi
echo "Wave 2 mode: N=${N} ${TRIGGER:+(trigger=$TRIGGER)}"
```

If `N == 1` → run **Wave 2A**. If `N >= 2` → run **Wave 2B** (and add `solution_selector` to the
roster — see below). For TRIVIAL/SMALL/STANDARD classes with no trigger, `N` stays 1 and the manifest
records `candidate_selection: skipped (class=${CLASS}, no trigger)`.

### Wave 2A — Single Implementation (default)

Spawn the generated implementation agents **by role name** (`subagent_type` = the role; the generated
file in `.claude/agents/generated/` carries that `name:`), so each loads its own skill packs. Their
hard `upstream` dependencies force this order: each step consumes the previous step's output.

```
Wave 2A (sequenced — each step waits for the previous; skip a step whose agent is not in the roster):
  2A.1  database_agent     → docs/design/database.md            (schema design)
  2A.2  migration_agent    → migrations/                        (needs 2A.1's schema)
  2A.3  backend_developer  → impl/backend_progress.md           (services/repositories on the schema)
  2A.4  api_developer      → impl/api_progress.md + specs/api-contracts.md   (handlers + the contract every UI/mobile test mocks from)
  2A.5  ui_developer       → impl/ui_progress.md + ui_developer/manifest.json   (needs 2A.4's api-contracts.md; the manifest lists screens, routes, testIDs — ui_test_agent's input)
  2A.6  mobile_developer   → impl/mobile_progress.md + mobile_developer/manifest.json  (React Native; needs 2A.4; may run in parallel with 2A.5)
```

Each spawn prompt (prepend the GROUND TRUTH line):
```
Agent prompt (subagent_type: <role>): "[GROUND TRUTH] You are <role> running Wave 2 step 2A.<n> for Phase ${PHASE}.
Read FIRST: agent_state/phases/${PHASE}/audit_report.md (+ audit_report_ui.md for ui_developer/mobile_developer)
(what already exists: extend it, don't rebuild it)
and agent_state/codebase/ (conventions). Then the phase specs in docs/design/phases/${PHASE}/specs/,
IMPLEMENTATION_GUIDELINES.md (incl. §Runtime contract and §Commands and versions), and the outputs of
the earlier 2A steps listed above.
RULES (each one is checked later by a named reviewer or the gate):
  - Existing code: read before you edit, follow its conventions, keep diffs minimal, never reformat or
    rewrite code outside your task.
  - Ownership: write only your layer (your agent file's Ownership section). Needs in another layer go in
    your progress file for its owner.
  - Contract: every HTTP response uses ~/.claude/skills/api/response-envelope.md — no other shape.
  - Security: ~/.claude/skills/security/secure-coding.md — authorize every handler (deny by default,
    object-level ownership), validate at the boundary, parameterized queries only, no secrets in
    code/logs/errors, fail closed unless APP_ENV is local|dev|test, threat-model mitigations in scope.
  - Runtime contract (IMPLEMENTATION_GUIDELINES §Runtime contract): entry points, health/readiness,
    config from env, numeric non-root user, graceful shutdown.
  - No stubs, TODOs, placeholder returns or fake implementations; interfaces not concrete types;
    literal Unicode; document every spec deviation.
BUILD GATE: before logging completion, run build, typecheck, lint and the unit tests of the packages you
touched using agent_state/config/verify-commands.json, and paste each command's exit code into your
progress file. Any non-zero exit means you are not done.
Implement your layer. Commit after each logical unit. Log your completion line to execution.jsonl."
```

**Parent build gate after EACH 2A step** — the next step never starts on a broken build:
```bash
V=agent_state/config/verify-commands.json
for k in build typecheck lint; do
  CMD="$(jq -r --arg k "$k" '.commands[$k] // empty' "$V")"; [ -n "$CMD" ] || continue
  PHASE="${PHASE}" bash -o pipefail -c "$CMD" >"agent_state/phases/${PHASE}/junit/2A-$k.log" 2>&1 \
    || { echo "⛔ BLOCKED after 2A.<n>: $k failed (exit $?) — respawn the same role with the log; do not start the next step"; tail -20 "agent_state/phases/${PHASE}/junit/2A-$k.log"; }
done
```

### Wave 2-UI pre-check — approved, current Stitch baseline (BEFORE 2A.5 / 2A.6)

Google Stitch is the core designer (`~/.claude/skills/ui/stitch-design.md`). When
`docs/design/stitch.json` exists, no UI or mobile screen is implemented until every screen this phase
touches has an **approved render at its latest revision** whose stored files still match their hashes:
```bash
if [ -f docs/design/stitch.json ]; then
  python3 .claude/hooks/stitch-state.py validate --check-files \
    && python3 .claude/hooks/stitch-state.py ready --phase "${PHASE}" \
    || echo "⛔ BLOCKED before 2A.5/2A.6: a screen this phase touches has no approved, current Stitch render — run /design --phase=${PHASE} (or /stitch request <key> \"<change>\") and approve it first"
fi
```
- `ready --phase N` reads `docs/design/phases/N/stitch-baseline.md` (written by `/design`). A missing
  file means the phase was never designed in Stitch: run `/design` first.
- `pending_approval` → the approval loop (owner; `design_quality_reviewer` under `--auto`).
- `DEFERRED` (Stitch was unavailable during an `/autonomous` run) is not a blocker: the screen is built
  from the wireframe and stays queued; the gate reports it as a WARNING.
- A UI change discovered during the phase that isn't in the approved render goes to Stitch first
  (`/stitch request`), never straight into code.

Both UI roles get these extra RULES in their spawn prompt:
```
STITCH (when docs/design/stitch.json exists): build each screen against BOTH its approved render
(docs/design/stitch/<key>/screenshot.png + screen.html: layout, spacing, hierarchy, density) and its
wireframe pair (bindings, the 4 states, testIDs, TC IDs). Use the project's components and tokens;
never paste Stitch's HTML or Tailwind classes. Each manifest screen names "stitch_screen" and
"stitch_rev". Every deliberate difference from the render goes in your manifest's
stitch_deviations[] ({id: DEV-<phase>-<nnn>, screen, what, why}); an unrecorded difference is drift.
```

> **Mobile app code (2A.6):** `mobile_developer` builds the React Native screens from the screen specs,
> with the spec's testIDs, a typed client generated from `data-contracts.md`, and both platforms built.
> Its manifest (screens, testIDs, deep links, permissions) is the surface `mobile_test_agent` and
> `mobile_platform_auditor` work from. 2A.5 and 2A.6 are independent and may run in parallel.

### Wave 2B — Candidate Selection (conditional — hard phases only)

Full protocol: `~/.claude/skills/core/candidate-selection.md`. This REPLACES Wave 2A's single
implementation for this phase; it does NOT replace Wave 3/4/6 — the winner runs them as usual.

**1. Create N isolated worktrees (one per candidate) off the current HEAD:**
```bash
BASE="$(git rev-parse --short HEAD)"
WT_ROOT="agent_state/phases/${PHASE}/candidates"; mkdir -p "$WT_ROOT"
for i in $(seq 1 "${N}"); do
  git worktree add -b "cand/phase-${PHASE}/c${i}" "${WT_ROOT}/c${i}" "$BASE"
done
git worktree list
```

**2. Spawn N candidate implementers IN PARALLEL**, each in its OWN worktree with a DISTINCT starting
strategy for diversity (round-robin: c1=interface-first, c2=test-first, c3=data-model-first). Each MUST
write its own tests. Prepend the GROUND TRUTH line to each:
```
Agent prompt (subagent_type: general-purpose — deliberately generic; the adopt pass in step 5b brings the role artifacts back): "[GROUND TRUTH] You are candidate implementer c${i} for Phase ${PHASE}.
WORKING DIRECTORY: ${PROJECT_DIR}/agent_state/phases/${PHASE}/candidates/c${i}  (your OWN git worktree — commit ONLY here)
STARTING STRATEGY: ${STRATEGY}  (interface-first | test-first | data-model-first)
Read the SAME specs as Wave 2A: docs/design/phases/${PHASE}/specs/ + IMPLEMENTATION_GUIDELINES.md.
Implement ALL in-scope components AND write your own tests (unit + this surface's TC-* IDs).
The Wave 2A RULES and BUILD GATE apply (read them above). Do NOT read/merge from sibling candidate worktrees. Commit in THIS worktree only.
Return: files created + one line on how your strategy shaped the design."
```

**3. Model-test voting (Signal A) — build the cross-test matrix** before the selector runs. Run each
candidate's own suite, and cross-run comparable suites (same public interface / same TC-* IDs) against
the sibling implementations. Write `agent_state/phases/${PHASE}/candidates/cross_test_matrix.md` (own
pass + cross pass rate per candidate; mark non-comparable pairs `N/A` — never fake a PASS).

**4. Spawn `solution_selector` (Signal B + combine):**
```
Agent prompt (subagent_type: solution_selector): "[GROUND TRUTH] You are solution_selector for Phase ${PHASE}.
Read ~/.claude/skills/core/candidate-selection.md, docs/design/phases/${PHASE}/specs/,
and agent_state/phases/${PHASE}/candidates/cross_test_matrix.md.
Score EACH candidate on the fixed rubric (R1 coverage, R2 test, R3 quality, R4 arch, R5 risk).
Combine 0.5*cross_test + 0.5*rubric. Disqualify any candidate that fails its own tests or uses a
RETIRED component. Execution overrides preference. Produce a winner + rationale + a specific graft list.
Write agent_state/phases/${PHASE}/reports/candidate_selection.md and log a completed line to execution.jsonl."
```

**5. Rejoin — merge the winner, graft, discard losers** (per skill §How the winner rejoins):
```bash
WINNER=$(grep -oE 'WINNER: c[0-9]+' "agent_state/phases/${PHASE}/reports/candidate_selection.md" | grep -oE 'c[0-9]+' | head -1)
git merge --no-ff "cand/phase-${PHASE}/${WINNER}" -m "phase ${PHASE}: adopt candidate ${WINNER} (selected — see candidate_selection.md)"
# Grafts named in candidate_selection.md are HUNKS, applied during the step-5b adopt pass (never a blind merge of a loser); then:
for i in $(seq 1 "${N}"); do
  C="c${i}"
  git worktree remove --force "agent_state/phases/${PHASE}/candidates/${C}" 2>/dev/null || true
  [ "$C" = "$WINNER" ] || git branch -D "cand/phase-${PHASE}/${C}" 2>/dev/null || true
done
git worktree prune
```

**5b. Adopt pass — the winner must leave the same artifacts as Wave 2A.** Candidates are generic
implementers, so the role agents' outputs don't exist yet. Spawn each role in the roster, in 2A order,
with `subagent_type: <role>` and this task: "Adopt the merged candidate code for your layer: do NOT
rewrite it. Fix only what violates your agent file's rules; publish your artifacts (api_developer:
specs/api-contracts.md; ui_developer/mobile_developer: their manifest.json; migration_agent: the
migration registry); run your BUILD GATE; log your completion line." The roster's role agents then
complete honestly instead of being satisfied by fabricated lines.

**6. Log the decision** to `execution.jsonl`:
```bash
echo "{\"ts\":\"$(date -u +%Y-%m-%dT%H:%M:%SZ)\",\"event\":\"candidate_selection\",\"phase\":${PHASE},\"n\":${N},\"trigger\":\"${TRIGGER}\",\"winner\":\"${WINNER}\",\"report\":\"agent_state/phases/${PHASE}/reports/candidate_selection.md\"}" >> "agent_state/phases/${PHASE}/execution.jsonl"
```

After rejoin, **continue to Wave 3 on the winner** (merged working tree). The gate is unchanged.

**Verify before proceeding:**
```bash
# Wave 2 committed code (Wave 2A: on HEAD; Wave 2B: after the winner merge). Any language — counted from
# the phase's base commit, not HEAD~1, so a multi-commit wave or a Python/Java/Rust tree is seen too.
CHANGED="$(git diff --name-only "$(cat agent_state/phases/${PHASE}/base_sha)"..HEAD -- . ':(exclude)agent_state' ':(exclude)docs')"
echo "$CHANGED" | head -20
[ -n "$CHANGED" ] || echo "⛔ BLOCKED: Wave 2 committed no code since base_sha — the role agents' completion lines are not evidence"
# If Wave 2B ran: the selector report must exist and name a winner, and no dangling candidate worktrees remain.
if [ "${N:-1}" -ge 2 ]; then
  test -f "agent_state/phases/${PHASE}/reports/candidate_selection.md" || echo "⛔ BLOCKED: candidate_selection.md missing — solution_selector did not complete"
  git worktree list | grep -q "phases/${PHASE}/candidates/" && echo "⚠ dangling candidate worktree — run git worktree prune"
fi
```

**Auto-checkpoint:** Write `checkpoints/wave-2.json` with `artifacts_produced: [<new source files>]` and, if Wave 2B ran, `candidate_selection: {n: N, trigger: "<trigger>", winner: "cN"}`.

---

## Wave 3: TEST (SEPARATE AGENTS PER TIER)

**CRITICAL: Spawn SEPARATE agents for each test tier.** A single agent cannot reliably write unit + integration + E2E tests — it exhausts context on the first tier and silently drops the rest. This was proven in dlp_composer where a single test agent produced unit tests but ZERO integration, ZERO E2E, ZERO component tests.

**Spawn each tier by ROLE name** (`subagent_type: <role>`). The generated agents in
`.claude/agents/generated/` carry the bare role as their `name:`, so the spawn loads that agent's own
skill packs (the stack's test framework, mock tool, Playwright/Maestro, traceability). A generic
"write tests" prompt loads none of them. Prepend the GROUND TRUTH line to every prompt.

### Order — every test runs against the build the gate certifies

```
Wave 3a unit_test_agent ─┐  (parallel; no running app needed)
Wave 3b integration_test_agent ─┘
      ↓
Wave 3.5 DEPLOY — k8s: dev → promote the same digests to qa · compose: up · CLI: build   ⇒ APP_BASE_URL
      ↓
Wave 3c ui_test_agent → e2e_orchestrator (web) | e2e_orchestrator (non-web) ─┐ against APP_BASE_URL
Wave 3d mobile_test_agent → mobile_e2e_orchestrator                          ─┘ (parallel)
      ↓
Wave 3v test_runner — independent re-run of every tier at the committed code
```

Browser and device tests never run against a dev server or a leftover stack. They run after Wave 3.5,
against `APP_BASE_URL`, which is the **qa** namespace on lab-cluster projects: byte-identical to what
dev verified.

### Which tracks run

| Project shape (from `agent_registry.json` tech_profile) | Tracks |
|---|---|
| Backend only / CLI / library | 3a, 3b, 3c-pipeline, then 3v |
| Web UI (`frontend.enabled`) | 3a, 3b, 3c-web (`ui_test_agent` + `e2e_orchestrator`), then 3v |
| React Native mobile (`mobile.enabled`) and the phase touched mobile screens | add 3d (`mobile_test_agent` → `mobile_e2e_orchestrator`) |
| Web + mobile | all of the above |

### Evidence every test agent leaves (the gate reads nothing else)

Every test-agent prompt below includes this block verbatim:

```
EVIDENCE (skills/testing/test-results-sidecar.md):
  1. Commit your tests (evidence binds to the code commit; uncommitted code can't be evidence).
  2. Run the tier with the command in agent_state/config/verify-commands.json (commands."test:<tier>"),
     JUnit XML to agent_state/phases/${PHASE}/junit/<tier>.xml. No retries to green; flaky = failing.
  3. python3 .claude/hooks/junit-to-sidecar.py --tier <tier> --command "<cmd>" --exit-code $RC \
       --env <local|dev|qa> --base-url "${APP_BASE_URL}" --priorities agent_state/phases/${PHASE}/tc_priorities.json \
       --out agent_state/phases/${PHASE}/reports/<report>.json agent_state/phases/${PHASE}/junit/<tier>.xml
  4. TC IDs go in test NAMES (titles, t.Run names, parametrize ids, flow names): comments don't count.
  5. Log completion with report = agent_state/phases/${PHASE}/reports/<report>.md (the .json beside it is the evidence).
```

### Wave 3a — Unit Tests  (`subagent_type: unit_test_agent`)

```
Agent prompt (subagent_type: unit_test_agent): "[GROUND TRUTH] You are unit_test_agent running Wave 3a for Phase ${PHASE}.
Get your work list: python3 .claude/hooks/sdlc-graph.py context --agent unit_test_agent --phase ${PHASE}
(phase_context.md, the unit rows still to do, the spec sections to read); read only those slices.
Derive each test's expected values from the SPEC (acceptance criteria, contracts, edge cases), not
from the implementation: a test that restates the code proves nothing. For every behaviour, include
at least one negative/boundary case. Mock only true external boundaries.
[EVIDENCE block] report: unit_tests"
```

### Wave 3b — Integration Tests  (`subagent_type: integration_test_agent`)

```
Agent prompt (subagent_type: integration_test_agent): "[GROUND TRUTH] You are integration_test_agent running Wave 3b for Phase ${PHASE}.
Get your work list: python3 .claude/hooks/sdlc-graph.py context --agent integration_test_agent --phase ${PHASE}
(phase_context.md, the integration rows still to do, spec/contract sections, endpoints with handler spans).
Against REAL dependencies (Testcontainers / the stack's versions from §Commands and versions):
repository CRUD, cache behaviour, the response envelope for every endpoint
(~/.claude/skills/api/response-envelope.md §What tests assert), the abuse-case matrix
(testing/test-case-generation.md §Abuse cases: object/tenant authz, function authz, mass
assignment, token tampering, injection, rate limits), every TC-SEC-* from the threat model, and failure
modes (dependency down or slow → the documented error/timeout, no hang).
[EVIDENCE block] report: integration_tests"
```

## Wave 3.5: DEPLOY + HEALTH CHECK (before any browser or device test)

**Browser, device and acceptance tests run against a LIVE app.** This wave builds and deploys what was
committed, and produces the `APP_BASE_URL` every later tier uses. Without it, tests pass against a
dev server or a stale stack from an earlier session. That was the state of the pipeline before the
2026-09-30 board review (TEST-09, OPS-02).

### Determine project type

Read `docs/IMPLEMENTATION_GUIDELINES.md` to determine the deployment strategy:

| Project Type | Deploy Strategy | Health Check |
|---|---|---|
| **Has `deploy/k8s/app.env`** (lab cluster) | `scripts/k8s/deploy.sh dev`, then `scripts/k8s/deploy.sh qa` (promotes dev's digests) | The script's own verdict: smoke + digest parity; `HEALTHY` in `agent_state/deploy/last-deploy-status.json` |
| Web API + UI | `docker compose up -d --build` | `curl -sf http://localhost:PORT/healthz` (runtime contract; `/readyz` for readiness) |
| CLI tool | The `build` row of `verify-commands.json` (any language) | Build exits 0; the e2e tier (3c) then runs the built binary |
| Library/SDK | The `build` row of `verify-commands.json` | Build exits 0 (no runtime to health check) |
| WASM module | Build native + WASM targets | Both binaries exist |
| React Native app (in addition to its backend row) | Build release binaries: iOS simulator `.app` + Android emulator `.apk` (commands from IMPLEMENTATION_GUIDELINES §Mobile) | Each installs on a booted device and cold-launches to its first screen with no native crash/red screen, and the first screen's API call reaches the backend (see `~/.claude/skills/frameworks/react-native.md` §Health check). `mobile_e2e_orchestrator` Step 1–3 does exactly this. |

### Execute local deploy

```bash
echo "Wave 3.5: Local Deploy + Health Check"

# Build and migrate commands come from agent_state/config/verify-commands.json (the guidelines'
# "Commands and versions" table), never from a guess about the language.
V=agent_state/config/verify-commands.json

# Kubernetes lab cluster (skill: infrastructure/lima-k8s-lab.md): dev is built from this tree, qa gets
# dev's exact digests. Every later test tier (3c e2e, 3d mobile, Wave 4 acceptance) targets QA.
if [ -f "deploy/k8s/app.env" ]; then
  HEALTHY=false
  if PHASE="${PHASE}" scripts/k8s/deploy.sh dev && PHASE="${PHASE}" scripts/k8s/deploy.sh qa; then HEALTHY=true; fi
  . deploy/k8s/app.env
  export APP_BASE_URL="http://${APP}-qa.localhost:${INGRESS_PORT}"     # every later test tier targets qa
  echo "  deploy: $(python3 -c 'import json; d=json.load(open("agent_state/deploy/last-deploy-status.json")); print(d["target"], d["status"], d.get("failing",""))')"
  # UNHEALTHY → read the script's log lines (it names the failing pod/job and reason), fix, re-run.
  # If a namespace is missing the script says so: that is a human step (app-namespaces.sh), BLOCK.

# For containerized projects:
elif [ -f "docker-compose.yml" ] || [ -f "compose.yml" ]; then
  echo "  Building and deploying containers..."
  # No pipe here: `| tail` would replace a failed build's exit code with 0 and start the stale image.
  docker compose build --no-cache > "agent_state/phases/${PHASE}/junit/3.5-build.log" 2>&1 \
    || { echo "  BUILD FAILED — see agent_state/phases/${PHASE}/junit/3.5-build.log"; tail -20 "agent_state/phases/${PHASE}/junit/3.5-build.log"; }
  docker compose up -d 2>&1

  # Run pending migrations with the table's migrate row (written to run against this stack).
  MIGRATE="$(jq -r '.commands.migrate // empty' "$V")"
  if [ -n "$MIGRATE" ]; then
    echo "  Running migrations..."
    PHASE="${PHASE}" bash -o pipefail -c "$MIGRATE" || echo "  MIGRATIONS FAILED (exit $?)"
  fi

  # Health check with retry (up to 60s)
  echo "  Health checking..."
  export APP_BASE_URL="http://localhost:${APP_PORT:-8080}"
  HEALTH_URL="${APP_BASE_URL}/healthz"   # the runtime contract's liveness path (IMPLEMENTATION_GUIDELINES §Runtime contract)
  HEALTHY=false
  for i in $(seq 1 12); do
    if curl -sf "$HEALTH_URL" > /dev/null 2>&1; then
      HEALTHY=true
      break
    fi
    sleep 5
  done

  if [ "$HEALTHY" = true ]; then
    echo "  App healthy at $HEALTH_URL"
  else
    echo "  UNHEALTHY after 60s — checking logs..."
    docker compose logs --tail 30 2>&1
    echo "  Attempting restart..."
    docker compose restart 2>&1
    sleep 10
    curl -sf "$HEALTH_URL" > /dev/null 2>&1 || echo "  STILL UNHEALTHY after restart"
  fi

# For CLI tools and libraries, in any language: the table's build row.
else
  HEALTHY=false
  BUILD="$(jq -r '.commands.build // empty' "$V")"
  if [ -z "$BUILD" ]; then
    echo "  No build row in $V — add one to the Commands and versions table"
  elif PHASE="${PHASE}" bash -o pipefail -c "$BUILD" > "agent_state/phases/${PHASE}/junit/3.5-build.log" 2>&1; then
    HEALTHY=true
  else
    echo "  Build failed — see agent_state/phases/${PHASE}/junit/3.5-build.log"
  fi
fi
```

### Verification gate

```bash
# For the k8s lab cluster: dev AND qa must be HEALTHY (the script's verdict)
if [ -f "deploy/k8s/app.env" ] && [ "$HEALTHY" != true ]; then
  echo "BLOCKED: dev/qa deploy not HEALTHY — see agent_state/deploy/last-deploy-status.json"
fi
# For web apps: health endpoint must respond
if [ ! -f "deploy/k8s/app.env" ] && { [ -f "docker-compose.yml" ] || [ -f "compose.yml" ]; }; then
  if [ "$HEALTHY" != true ]; then
    echo "BLOCKED: App not healthy — acceptance tests will fail against a dead service"
    echo "  Fix the deployment before proceeding to Wave 4"
    # In --auto mode: attempt auto-fix (check logs, restart, max 2 cycles)
    # After 2 cycles: force-proceed with WARNING logged to manifest
  fi
fi

# For CLI tools and libraries: the build must pass
if [ ! -f "deploy/k8s/app.env" ] && [ ! -f "docker-compose.yml" ] && [ ! -f "compose.yml" ] && [ "$HEALTHY" != true ]; then
  echo "BLOCKED: build failed — E2E/acceptance tests need a working binary or package"
fi
```

**Auto-checkpoint — this is how the URL reaches every test agent:** write `checkpoints/wave-3.5.json` with `app_base_url: "$APP_BASE_URL"` (the parent substitutes it literally into every Wave 3c/3d/3v/4-B/4-D prompt), and `deploy_status: healthy|unhealthy|not_applicable`, `deploy_type: k8s|docker|cli|library|mobile` (k8s adds `app_base_url` = the qa URL and `digests` from `agent_state/deploy/qa/history.jsonl`), and for mobile `mobile_binaries: {ios: built|failed|blocked, android: built|failed|blocked}`.

### Wave 3c — E2E Tests (project-type-aware, after Wave 3.5)

**Web UI — TWO separate agents:**

```
Agent prompt (subagent_type: ui_test_agent): "[GROUND TRUTH] You are ui_test_agent running Wave 3c-web for Phase ${PHASE}.
BASE URL: ${APP_BASE_URL}. Read docs/design/phases/${PHASE}/specs/api-contracts.md and
agent_state/phases/${PHASE}/ui_developer/manifest.json FIRST.
Write component tests for every implemented screen (4 states: loading/error/empty/data) with mocks
generated from the envelope types (never hand-shaped), responsive assertions, the XSS-RENDER and
SESSION-STORAGE abuse rows, and the Playwright specs for every TC-E2E-* in scope (baseURL = BASE URL).
Run the component tier. [EVIDENCE block] report: ui_test_results"

Agent prompt (subagent_type: e2e_orchestrator): "[GROUND TRUTH] You are e2e_orchestrator running Wave 3c-web for Phase ${PHASE}, AFTER ui_test_agent.
BASE URL: ${APP_BASE_URL} (verify GET <BASE URL>/healthz is 200 first; if not, verdict BLOCKED).
Scope = every TC-E2E-* in this phase's spec inventory plus all earlier phases' committed e2e specs
(regression): python3 .claude/hooks/sdlc-graph.py unlocked --phase ${PHASE}. Never invent scenarios. Run once with retries 0; a pass-on-retry is FLAKY (a failure).
Write screenshots/traces for failures. [EVIDENCE block] report: e2e_results"
```

**CLI tool, library, or non-web backend — pipeline E2E:**
```
Agent prompt (subagent_type: e2e_orchestrator): "[GROUND TRUTH] You are e2e_orchestrator running Wave 3c-pipeline for Phase ${PHASE}.
Read phase_context.md and the specs' TC-* IDs with tier: e2e. Write and run process-level tests of the
full product flow: real inputs → processing → output verification; multi-step pipelines; malformed
input → graceful error; WASM parity where applicable. Not browser tests.
[EVIDENCE block] report: e2e_results"
```

### Wave 3d — Mobile (React Native, iOS + Android) — only when mobile screens changed

Full strategy: `~/.claude/skills/testing/mobile-testing-strategy.md`.

```
Agent prompt (subagent_type: mobile_test_agent): "[GROUND TRUTH] You are mobile_test_agent running Wave 3d for Phase ${PHASE}.
Read api-contracts.md FIRST, then the mobile TC-M* inventory and IMPLEMENTATION_GUIDELINES §Mobile.
Write Jest + RNTL component tests (4 states per screen), MSW-mocked integration tests (handlers typed
from the envelope), and device flows for every unlocked FR-* workflow and applicable platform
behaviour. Flow file names start with their TC ID. Every flow runs on BOTH iOS and Android. Run the
Node tiers. [EVIDENCE block] report: mobile_test_results (+ mobile_test_agent/manifest.json)"

Agent prompt (subagent_type: mobile_e2e_orchestrator): "[GROUND TRUTH] You are mobile_e2e_orchestrator running Wave 3d for Phase ${PHASE}, AFTER mobile_test_agent.
BACKEND: ${APP_BASE_URL} (iOS simulator uses it as is; the Android emulator reaches the Mac's loopback
as 10.0.2.2 — rewrite the host, keep the port and Host header). Build release binaries, boot the device
matrix, run every flow in the manifest plus earlier phases' flows, per platform and slot. A platform
that could not run is BLOCKED with a reason, never PASS. [EVIDENCE block] report: mobile_e2e_results
(per-platform JUnit merged; cases carry the platform in their name)"
```

### Wave 3v — Independent verification  (`subagent_type: test_runner`)

The writers ran their own suites, so their numbers are self-graded. `test_runner` re-runs **every** tier
the phase has (unit, integration, UI component, browser e2e against `APP_BASE_URL`, RN Jest) from a clean
process, using only `verify-commands.json`. Device flows stay with `mobile_e2e_orchestrator`, whose
per-platform JUnit is already runner evidence.

```
Agent prompt (subagent_type: test_runner): "[GROUND TRUTH] You are test_runner running Wave 3v for Phase ${PHASE}.
BASE URL: ${APP_BASE_URL}. Using ONLY agent_state/config/verify-commands.json, run every test:* command
that applies (Go with -count=1 so nothing is cached). Convert each JUnit with junit-to-sidecar.py.
Write reports/test_results.json (tier: all — every case from every tier) and REFRESH each writer's tier
sidecar from your own run (reports/unit_tests.json, integration_tests.json, ui_test_results.json,
e2e_results.json, mobile_test_results.json) so the gate reads runner output, not self-reports.
Fill the Writer-vs-Independent table; any mismatch in totals or failures is BLOCKING.
Produce: agent_state/phases/${PHASE}/reports/test_results.md + test_results.json"
```

### Wave 3 Verification (every scheduled track must pass)

```bash
R="agent_state/phases/${PHASE}/reports"
in_roster() { jq -e --arg a "${1}" '.required | index($a)' "agent_state/phases/${PHASE}/roster.json" >/dev/null 2>&1; }
SIDE="unit_tests integration_tests e2e_results test_results"
in_roster ui_test_agent           && SIDE="$SIDE ui_test_results"
in_roster mobile_test_agent       && SIDE="$SIDE mobile_test_results"
in_roster mobile_e2e_orchestrator && SIDE="$SIDE mobile_e2e_results"
for S in $SIDE; do
  F="$R/$S.json"
  if [ ! -f "$F" ]; then echo "⛔ BLOCKED: $S.json missing — its agent did not run or wrote no evidence"; continue; fi
  jq -e '.schema == "sdlc.test-results/v1" and .verdict == "PASS" and .total > 0 and .failed == 0 and (.flaky // 0) == 0' "$F" >/dev/null \
    || echo "⛔ BLOCKED: $S — $(jq -r '"verdict \(.verdict), total \(.total), failed \(.failed), flaky \(.flaky // 0)"' "$F")"
done
# Mobile: both platforms must have run (a BLOCKED platform needs a recorded decision)
if in_roster mobile_e2e_orchestrator; then
  for P in ios android; do
    jq -e --arg p "$P" '[.cases[] | select(.name | ascii_downcase | contains($p))] | length > 0' "$R/mobile_e2e_results.json" >/dev/null 2>&1 \
      || echo "⛔ BLOCKED: mobile ${P} device tier did not run (see mobile_e2e_results.md)"
  done
fi
```
The same rules run again, deterministically, in `verify-gate.sh` at Wave 6.

**Auto-checkpoint:** write `checkpoints/wave-3.json` with `tests_passing: true|false`, `code_sha`, and `artifacts_produced`.

### Test Failure Recovery Guardrails

When tests fail and the test agent or a subsequent fix agent attempts auto-remediation, these guardrails are **absolute constraints** — they cannot be overridden by any agent:

**NEVER do these to make tests pass** (the test-diff check `tc-inventory.py --diff-base` flags each one
at the gate). A legitimate change to a test that existed before the phase carries its why and when on one
line directly above it: `// TEST-CHANGE <YYYY-MM-DD> phase <N>: <why> (spec: <ref> | moved: <where>)`.
A changed assertion must cite `spec:` or `moved:`; a deleted test file is recorded in
`agent_state/phases/${PHASE}/test-changes.json` (`test-case-traceability.md` §Changing an existing test):
- Delete, `.skip`, or comment out an existing test assertion or test function
- Reduce test coverage threshold to pass a gate
- Downgrade a dependency version to fix a build (may reintroduce CVEs)
- Modify test expectations to match buggy behavior instead of fixing the bug
- Remove a test file to reduce failure count
- Add `// @ts-ignore`, `//nolint`, or equivalent to suppress test-adjacent type errors
- Add retries, longer sleeps or looser assertions to turn a flaky test green (flaky = failing)
- Add `.only`, `.skip`, `t.Skip`, `@pytest.mark.skip`, `xit` or quarantine without an issue + expiry

**Confidence-based escalation:**
- If root cause is clear (missing import, typo, wrong return type, obvious logic error) → auto-fix
- If root cause is unclear after reading the full failure output → escalate to user (in **auto mode**: pick the most conservative option, log it to auto-resolved.jsonl, and continue): "Test failure in [component] — root cause unclear. Options: [A] [B] [C]"
- Maximum 3 auto-fix attempts per failing test → then escalate (do NOT loop indefinitely)

**CI log sanitization (before feeding test output to any agent):**
Strip these patterns from test/build output before including in any agent prompt:
- Environment variables (`KEY=value`, `export VAR=`)
- Connection strings (`postgres://`, `redis://`, `mongodb://`, `mysql://`)
- Token-like strings (`sk-*`, `ghp_*`, `gho_*`, `Bearer *`, `token=*`)
- File paths containing `/secrets/`, `/.env`, `/credentials`, `/private/`
- Stack traces that include home directory paths (`/Users/`, `/home/`)

---

## Wave 4: REVIEW + RECONCILE + ACCEPTANCE (parallel tracks)

**Keep review split across separate agents.** A single "code quality review" agent
exhausts context on the first dimension and silently drops the rest — this is the *exact*
single-agent failure mode Wave 3 rails against for tests, and it is how security review, both
reconcilers, and the dependency scan get dropped from a run. Spawn each reviewer/reconciler as a
SEPARATE, NAMED agent. Every agent below maps 1:1 to an entry in the Wave-0 roster and every one
must produce its named report; Wave 6 blocks if any is missing.

Spawn Track A (reviewers, parallel), Track C (reconcilers, parallel with A), Track B (acceptance) and
Track D (reliability/performance, when in the roster) — all concurrently where independent. First
record the commit the reviewers see, so Wave 5v can re-review exactly what changed after them:
`git rev-parse HEAD > agent_state/phases/${PHASE}/wave4_sha`.

### Track A — Code Review (SEPARATE agents per dimension, parallel)

```
Wave 4 Track A (parallel):
  ├─ Agent: code_reviewer_I          → reports/code_review_I.md        (style, idioms, naming)
  ├─ Agent: code_reviewer_II         → reports/code_review_II.md       (architecture, layer boundaries)
  ├─ Agent: security_reviewer        → reports/security_review.md      (OWASP + project constraints)
  ├─ Agent: tenant_isolation_verifier → reports/tenant_isolation.md    (only if multi-tenant; see IMPL_GUIDELINES)
  ├─ Agent: dependency_scanner       → reports/dependency_scan.md      (CVEs, licenses, outdated)
  ├─ Agent: code_quality_verifier    → reports/quality_gate.md         (TODOs, stubs, secrets, dead code)
  ├─ Agent: accessibility_auditor    → reports/accessibility_audit.md  (only if web UI; WCAG 2.2 AA against the BUILT UI at BASE URL ${APP_BASE_URL})
  ├─ Agent: mobile_platform_auditor  → reports/mobile_platform_audit.md (only if mobile screens changed; iOS + Android)
  ├─ Agent: ui_standards_auditor     → reports/ui_standards_audit.md   (web/mobile UI phases; every page vs standards + Stitch baseline)
  ├─ Agent: migration_safety_reviewer → reports/migration_safety.md    (only if the phase adds migrations)
  └─ Agent: breaking_change_reviewer → reports/breaking_change_review.md (only if a cross-phase contract changed)
```

Spawn every Track A agent with `subagent_type: <agent name>` so it loads its own checks and skill
packs. `code_reviewer_II` runs in parallel with `code_reviewer_I`; if I's report already exists when II
finishes its own pass, II de-duplicates against it (a soft `runs_after`, not a hard wait).

> `accessibility_auditor` runs only for web-UI phases and tests the BUILT UI (axe/keyboard/contrast/
> ARIA) — distinct from the design-time `design_quality_reviewer`. It requires the app running (Wave
> 3.5). If the phase has no UI, record it as `skipped:not_applicable` in the roster.

Each spawn prompt (prepend the GROUND TRUTH line):
```
Agent prompt (subagent_type: <agent_name>): "[GROUND TRUTH] You are <agent_name> running Wave 4 Track A for Phase ${PHASE}.
Review ALL source changed/added in this phase against IMPLEMENTATION_GUIDELINES and the phase specs.
Map it first: python3 .claude/hooks/sdlc-graph.py diff-context --phase ${PHASE} (changed symbols with spans,
endpoints/tables touched, governing spec sections) and read the spec sections it lists, not the whole specs/
directory (unless it is unavailable — then say so). breaking_change_reviewer also runs
python3 .claude/hooks/sdlc-graph.py consumers --changed-since <previous phase's gate commit>.
Use the Unified Severity Model (~/.claude/skills/core/code-quality.md): BLOCKING | WARNING | INFO.
Every finding MUST cite file:line. Produce your named report at the exact path above.
Definition of Done: report written, every BLOCKING finding has file:line + a fix recommendation,
and the report ends with a one-line COUNT summary: 'BLOCKING:N WARNING:N INFO:N'."
```

> `tenant_isolation_verifier` runs only when the project is multi-tenant (SaaS tenancy model in
> IMPLEMENTATION_GUIDELINES). If not applicable, record it as `skipped:not_applicable` in the roster
> — that is an explicit skip, not a silent drop.

### Track C — Reconciliation (SEPARATE agents, parallel with Track A)

These were previously omitted from the orchestrator entirely (they lived only in develop.md and so
never ran under wave execution). They are now mandatory Wave-4 agents.

```
Wave 4 Track C (parallel):
  ├─ Agent: spec_impl_reconciler  → reconciliation/phase-N/specs_vs_impl.md  (spec ↔ code: MISSING / EXTRA / DRIFT)
  └─ Agent: spec_test_reconciler  → reconciliation/phase-N/specs_vs_tests.md (spec ↔ tests: TC-* coverage %, deferred IDs)
```

Reconciliation reports live in `agent_state/reconciliation/phase-${PHASE}/` (not `reports/`), because
`/plan`, `/test`, `/recon` and `pipeline_completeness_agent` all read them there. Every check below
resolves report paths through `report_path` (redefined in each bash block — the parent runs every block in a fresh shell):
```bash
report_path() { case "${1}" in
  specs_vs_impl.md|specs_vs_tests.md|test_case_inventory.md|brd_vs_specs.md) echo "agent_state/reconciliation/phase-${PHASE}/${1}" ;;
  *) echo "agent_state/phases/${PHASE}/reports/${1}" ;;
esac; }
```

Each spawn prompt (prepend GROUND TRUTH):
```
Agent prompt (subagent_type: <reconciler>): "[GROUND TRUTH] You are <reconciler> running Wave 4 Track C for Phase ${PHASE}.
spec_test_reconciler: FIRST run the deterministic TC gate — it is your evidence, your prose explains it:
  python3 .claude/hooks/sdlc-graph.py gate --phase ${PHASE} --tc-only --results agent_state/phases/${PHASE}/reports/test_results.json [+ every other results sidecar that exists: acceptance_report.json, performance_results.json, e2e_results.json, mobile_e2e_results.json] \
    --diff-base $(cat agent_state/phases/${PHASE}/base_sha) --out agent_state/reconciliation/phase-${PHASE}/specs_vs_tests.json
  (tc-inventory.py with the same flags only if the graph is unavailable — say so in the report)
  (an ID counts only when a test NAMED with it ran and passed; skipped/comment-only/duplicate IDs and
  unacknowledged test weakening fail it). Then write specs_vs_tests.md around that JSON.
Perform bidirectional reconciliation. Report every MISSING (spec item with no code/test) and every
EXTRA (code/test with no spec). Classify each: BLOCKING (in-scope FR-* unbuilt/untested) vs
DEFERRED (explicitly out-of-scope, list the ID). Produce your named report.
Definition of Done: coverage % computed, BLOCKING list explicit, deferred IDs enumerated, and the
report ends with the one-line count 'BLOCKING:N WARNING:N INFO:N' (the gate reads only that line)."
```

### Track B — Acceptance Tests

**Pre-step (before spawning Track B): requirement changes reach the tests.** The acceptance scope of a
phase is every FR delivered so far plus this phase's, so a BRD change since an earlier gate (a
`product_manager` change request, `/recon --fix=docs --apply`, a hand edit) is handled here, not
discovered at release:
```bash
python3 .claude/hooks/acceptance-map.py --phase ${PHASE} --diff-base "$(cat agent_state/phases/${PHASE}/base_sha)" \
  --out agent_state/phases/${PHASE}/reports/acceptance_map.json || true
jq -r '(.delta.add[] | "\(.fr) \(.status) phases=\(.phases|join(",")) \(.detail)"),
       (.delta.update[] | "\(.fr) CHANGED phases=\(.phases|join(",")) \(.detail)"),
       (.delta.retire_rows[] | "retire row \(.id) (\(.reason))"),
       (.delta.retire_tests[] | "retire test \(.id) (\(.reason))")' agent_state/phases/${PHASE}/reports/acceptance_map.json
jq -r '.delta.retire_needs_decision[] | "needs decision: \(.kind) \(.id) (phase \(.owner // "?")) \(.reason)"' \
  agent_state/phases/${PHASE}/reports/acceptance_map.json   # NOT this phase's: never removed here
```
**This phase never removes another phase's acceptance rows or tests.** The `retire` lines are only
Phase ${PHASE}'s own: rows in its spec, test IDs from its block, or FRs its PHASE_PLAN names. The
"needs decision" lines belong to other phases: copy them into the phase report under "Acceptance
removals awaiting their owning phase", and never pass them to an agent. They don't block this gate.
`--diff-base` makes the map (and so the gate) block on any TC-ACC row or test this phase deleted but
doesn't own.
If any FR or `retire row` line prints, spawn `spec_writer` (subagent_type: spec_writer) with
`MODE: acceptance-amend`, `WORKING_PHASE: ${PHASE}` and those lines. It rewrites those FRs' TC-ACC rows to the current BRD text
in the phase that owns each FR (this phase for NEW/PARTIAL rows of this phase's FRs), and deletes this
phase's retired rows. Wait for it, then pass the printed FR and `retire` lines (not the "needs
decision" ones) to Track B as `CHANGED_FRS`. Nothing printed → `CHANGED_FRS: none`. This phase's own
retire items block its gate, like missing tests.

```
Agent prompt (subagent_type: acceptance_test_agent): "[GROUND TRUTH] You are acceptance_test_agent running Wave 4 Track B for Phase ${PHASE}.
CHANGED_FRS: <the pre-step list, or none> — update (or add, or retire) the tests for these FRs' amended
TC-ACC rows, whatever phase wrote them, and delete ONLY the tests on 'retire' lines (test-changes.json
entry). WORKING_PHASE is ${PHASE}: never delete, skip or weaken another phase's acceptance test. For
another phase's CHANGED FR you add and update only. Each changed pre-existing test gets its TEST-CHANGE
comment citing spec: the row.
After the run, merge the requirement map into your sidecar (every FR delivered so far + this phase's):
  python3 .claude/hooks/acceptance-map.py --phase ${PHASE} --diff-base \"$(cat agent_state/phases/${PHASE}/base_sha)\" \
    --results agent_state/phases/${PHASE}/reports/acceptance_report.json \
    --merge-into agent_state/phases/${PHASE}/reports/acceptance_report.json --out agent_state/phases/${PHASE}/reports/acceptance_map.json
  (a Must/Should FR with no TC-ACC row, a SHALL with no row, a changed FR, a failing FR, this phase's
  own leftover retire items, and any row/test this phase removed but doesn't own become UNTESTED cases
  the gate blocks on).
BASE URL: ${APP_BASE_URL} (qa on lab-cluster projects). PREREQUISITE: GET <BASE URL>/healthz returns 200
(CLI: the built binary answers --version). If not, verdict BLOCKED — never fake PASS.
Every FR-* acceptance criterion in scope, per persona, as COMMITTED runnable specs under
tests/acceptance/ (Playwright/API tests named 'TC-ACC-nnn …'; device flows for RN-delivered FRs on
BOTH platforms) — never ad-hoc curl. Also verify API contracts against the envelope and that traces
exist for each flow.
[EVIDENCE block] report: acceptance_report — cases carry priority (HIGH for any FR marked MUST)
and verdict PASS|FAIL|BLOCKED|UNTESTED per use case; any HIGH/MEDIUM case not PASS blocks the gate."
```

### Track D — Reliability + performance (only the agents the roster lists)

```
Agent prompt (subagent_type: reliability_agent): "[GROUND TRUTH] You are reliability_agent running Wave 4 Track D for Phase ${PHASE}.
Check the CODE changed this phase (git diff $(cat agent_state/phases/${PHASE}/base_sha)..HEAD) against
your Checks 3, 4 and 6 and the phase SLOs: timeouts on every outbound call/query, retries only on
idempotent operations with backoff+jitter, readiness vs liveness semantics, graceful shutdown with
drain, bounded pools against the DB connection budget, metric label cardinality.
Report every violation with file:line. Produce reports/reliability_review.md ending with 'BLOCKING:N WARNING:N INFO:N'."

Agent prompt (subagent_type: system_test_agent): "[GROUND TRUTH] You are system_test_agent running Wave 4 Track D for Phase ${PHASE} (only when the phase has an availability SLO, or the roster lists it).
BASE URL: ${APP_BASE_URL} (qa). Run your readiness-semantics, rolling-restart, pod-kill and DB-restart checks and the exit-criteria trace.
Produce reports/system_test_results.md + system_test_results.json (sdlc.test-results/v1)."

Agent prompt (subagent_type: performance_agent): "[GROUND TRUTH] You are performance_agent running Wave 4 Track D for Phase ${PHASE}.
BASE URL: ${APP_BASE_URL} (qa). RUN (don't recommend) an open-model load test (k6 constant-arrival-rate)
for every NFR-PERF-* in scope at its target rate, with thresholds = the NFR targets. Warm up first,
and record p50/p95/p99, error rate and saturation. Each NFR becomes a case (priority HIGH) that PASSes only
if its threshold held. Produce reports/performance_results.md + performance_results.json (sdlc.test-results/v1)."
```

### Wave 4 Verification — every named report must exist AND carry a verdict

```bash
WAVE4_BLOCKED=false
report_path() { case "${1}" in specs_vs_impl.md|specs_vs_tests.md|test_case_inventory.md|brd_vs_specs.md) echo "agent_state/reconciliation/phase-${PHASE}/${1}" ;; *) echo "agent_state/phases/${PHASE}/reports/${1}" ;; esac; }  # each bash block runs in a fresh shell
# Reviewers + reconcilers + acceptance. Skip tenant_isolation if roster marked it not_applicable.
REQUIRED_W4="code_review_I.md code_review_II.md security_review.md dependency_scan.md \
             quality_gate.md specs_vs_impl.md specs_vs_tests.md acceptance_report.md"
# Roster is a FLAT array of real agent names ({"required":[...]}). Each conditional reviewer is
# present iff Wave 0b added it; its report is then required. Membership, not a "status" object grep
# (the old grep never matched the flat schema → report silently dropped).
in_roster() { jq -e --arg a "${1}" '.required | index($a)' "agent_state/phases/${PHASE}/roster.json" >/dev/null 2>&1; }
in_roster tenant_isolation_verifier && REQUIRED_W4="$REQUIRED_W4 tenant_isolation.md"
in_roster accessibility_auditor     && REQUIRED_W4="$REQUIRED_W4 accessibility_audit.md"
in_roster mobile_platform_auditor   && REQUIRED_W4="$REQUIRED_W4 mobile_platform_audit.md"
in_roster ui_standards_auditor      && REQUIRED_W4="$REQUIRED_W4 ui_standards_audit.md"
in_roster migration_safety_reviewer && REQUIRED_W4="$REQUIRED_W4 migration_safety.md"
in_roster breaking_change_reviewer  && REQUIRED_W4="$REQUIRED_W4 breaking_change_review.md"
in_roster reliability_agent         && REQUIRED_W4="$REQUIRED_W4 reliability_review.md"
in_roster performance_agent         && REQUIRED_W4="$REQUIRED_W4 performance_results.md"
in_roster system_test_agent         && REQUIRED_W4="$REQUIRED_W4 system_test_results.md"
for R in $REQUIRED_W4; do
  F="$(report_path "$R")"
  if [ ! -f "$F" ]; then
    echo "⛔ BLOCKED: Wave 4 report ${R} missing — its agent was not spawned or did not complete"
    WAVE4_BLOCKED=true
  elif [ ! -s "$F" ] || [ "$(wc -l < "$F")" -lt 3 ]; then
    echo "⛔ BLOCKED: ${R} is empty/stub — the review did not actually run"
    WAVE4_BLOCKED=true
  fi
done
[ "$WAVE4_BLOCKED" = true ] && echo "⛔ DO NOT PROCEED — re-spawn the missing Wave-4 agents."
```

### Wave 4s — Stitch deviations and sync-back (UI phases with docs/design/stitch.json)

`ui_standards_auditor` resolves every `stitch_deviations[]` entry in the phase's UI manifests
(stitch-design.md §7) and records each with `stitch-state.py deviation`:
- **fixed (drift)** → a code finding for `ui_developer` / `mobile_developer` in the fix loop below; the
  screen returns to `conformant` on re-audit.
- **accepted** → the screen becomes `sync_back_pending`. After the review loop, the **parent** runs
  `/stitch sync-back` (the MCP calls are the parent's): an as-built `edit_screens` prompt, re-fetch,
  approval (owner interactively; `design_quality_reviewer` under `--auto`, listed for the owner), then
  `deviation --synced-rev`, and `ux_designer` re-normalizes the wireframe.
Stitch unavailable: interactive → `NEEDS_INPUT` "connect Stitch"; `--auto` → the sync-back stays
queued and the gate blocks on `sync_back_pending` (an accepted deviation must reach Stitch before the
phase passes; record it as a forced-gate blocker only with the owner's approval).
```bash
# screens waiting for /stitch sync-back (must be empty before Wave 5v)
[ -f docs/design/stitch.json ] \
  && jq -r '.screens | to_entries[] | select(.value.status=="sync_back_pending") | .key' docs/design/stitch.json
```

### Track A/C Fix → Re-Review Loop (do NOT defer all fixes to Wave 5)

BLOCKING findings from a reviewer/reconciler must be fixed and **re-verified by re-running only that
same agent** — not merely re-tested. This is the closed loop from `review.md`; without it a reviewer
finding is "addressed" without proof.

```
For each report with BLOCKING findings:
  0. ui_standards_audit.md: run /ui-audit Steps 2–3 on its findings. The PARENT executes
     ui_standards_stitch_requests.json (Stitch design gaps and missing baselines, then ux_designer,
     then the design gate), and code drift goes to ui_developer / mobile_developer. Unapproved
     reconstructed baselines are carried forward, not code-fixed.
  1. Spawn the OWNING ROLE agent for the files involved (subagent_type: api_developer for handlers,
     backend_developer for services, migration_agent for migrations, ui_developer/mobile_developer for
     screens, the tier's test agent for tests) with the findings, the Test Failure Recovery
     Guardrails and the Wave 2A RULES + BUILD GATE. Never a generic "fix it" agent: it has no skill
     packs and no guardrails (board review DEV-08).
  2. Re-spawn ONLY the reviewer/reconciler that raised them. Code changed, so the test evidence is
     now stale; Wave 5v refreshes it before the gate (the gate rejects stale evidence).
  3. Repeat max 2 rounds per report. If still BLOCKING after 2 rounds → carry to Wave 5 as a
     classified failure, or, if architectural, raise a debate yourself (child-returns.md § Escalating yourself).
Anti-rationalization: "the fix looks right, no need to re-run" is WRONG — always re-run the agent.
```

**Don't start Wave 5 until every required Wave-4 report exists and its BLOCKING count is
0 (or the item is explicitly carried forward with a reason).**

---

## Wave 5: COLLECTIVE FEEDBACK + ITERATE (with Adaptive Replanning)

> **Skill references:** `~/.claude/skills/core/adaptive-replan.md` (failure classification → minimum re-test SCOPE) and `~/.claude/skills/core/dual-ledger-replan.md` (Task/Progress ledgers → WHEN to replan vs keep iterating vs escalate). They compose: the ledger decides *whether* to keep going; the classification decides *what* to re-run.

**Maintain the dual ledgers across iterations.** The PARENT keeps `agent_state/phases/${PHASE}/ledger.md`:
- **Task Ledger** — `facts[]` (verified only), `assumptions[]` (guesses, kept explicitly separate — never present a guess as a fact), `plan[]`.
- **Progress Ledger** (per iteration) — step, assignee, done?, new-fact-this-cycle?, loop_count.

**Stall rule:** if `loop_count > 2` with no new fact (or the same failing action repeats without progress) → STALL → REPLAN: write the failure mode, evict the falsified assumption, rewrite `plan[]` (usually re-classify), and escalate after the tier's retry cap (`sdlc-config.json`) to `debate_moderator` or the human. A verified, broadly-true assumption may be promoted to a Tier 0 fact via `/remember`.

The PARENT session (not an agent) builds the feedback document. Start from the one-screen summary,
`python3 .claude/hooks/sdlc-graph.py gate --phase ${PHASE} --summary` (TC gate + roster + evidence
sidecars + reconciler counts, every blocker on one line), then open only the reports it names. If it is
unavailable, read all Wave 3+4 reports:

1. Read `unit_tests.md` — any failures?
2. Read `integration_tests.md` — any failures?
3. Read `e2e_results.md` (and `ui_test_results.md`, `mobile_test_results.md`, `mobile_e2e_results.md`, `test_results.md` when present) — any failures, per-platform failures, FLAKY flows, or writer-vs-independent count discrepancies?
4. Read the review reports — `code_review_I.md`, `code_review_II.md`, `security_review.md`,
   `dependency_scan.md`, `quality_gate.md` — any BLOCKING/HIGH/CRITICAL findings?
5. Read `acceptance_report.md` — any FAIL/PARTIAL?

Build: `agent_state/phases/${PHASE}/reports/collective_feedback.md`

### Adaptive Replanning (failure-aware fix routing)

Before spawning the fix agent, **classify each failure** using the adaptive replan protocol:

| Category | Signal | Re-Test Scope |
|---|---|---|
| LOGIC | Unit assertion failed | unit + integration |
| WIRING | Integration 404/500 | integration + E2E |
| CONTRACT | Shape mismatch, CONTRACT_VIOLATION | E2E + acceptance |
| SCHEMA | Migration/constraint error | ALL tiers |
| UI | Component render failure | UI + E2E |
| CONFIG | Health check fail, connection refused | integration + E2E + acceptance |
| FLAKY | Failed, then passed on retry (counts as FAILING at the gate) | race/ordering triage of the flaky tests (shared state, time, unawaited async, racing selectors); re-run the tier 3× with -race / repeat; quarantine only with issue + expiry |
| MOBILE-PLATFORM | Fails on one platform only (iOS xor Android), permission/deep-link/lifecycle flow, native crash on launch | mobile component + device tier on BOTH platforms |
| MOBILE-BUILD | iOS/Android binary fails to build or install | Wave 3.5 mobile build + ALL mobile tiers |

If multiple categories → take the UNION of re-test scopes. If any is SCHEMA/CONFIG → ALL tiers.

Spawn the fix as the OWNING ROLE agent (see the Track A/C loop above) with the classification:
```
Agent prompt (subagent_type: <owning role>): "[GROUND TRUTH] Fix these items from collective feedback.
The Wave 2A RULES, BUILD GATE and the Test Failure Recovery Guardrails apply.

FAILURE CLASSIFICATION: ${CATEGORY}
ROOT CAUSE: ${ROOT_CAUSE_DESCRIPTION}
AFFECTED FILES: ${FILES_FROM_ERROR_OUTPUT}

Items to fix:
${FAILURE_LIST}

After fixing, re-run these tiers (minimum viable scope per adaptive-replan.md):
  ${REQUIRED_TIERS}

You may SKIP these tiers (not affected by this fix type):
  ${SKIPPABLE_TIERS}

IMPORTANT: After applying your fix, check git diff. If you touched files
outside the predicted scope, EXPAND your re-test to include ALL tiers.

Also check agent_state/patterns.md for known fixes matching this failure category.

Verify all required tiers pass before reporting completion."
```

### Re-run Protocol

The adaptive replan protocol determines which tiers to re-run. The **safety guarantee** remains:

- **Single-category fix:** Re-run classified tiers + one safety tier above
- **Multi-category or SCHEMA/CONFIG:** Re-run ALL tiers (no shortcuts)
- **Git diff expanded beyond predicted scope:** Re-run ALL tiers
- If acceptance failed in Wave 4 → re-run acceptance after code fixes regardless of category

Max 3 iteration cycles. If architectural issue → raise a debate yourself (`~/.claude/skills/core/child-returns.md` § Escalating yourself).

**Verify:**
```bash
test -f agent_state/phases/${PHASE}/reports/collective_feedback.md || echo "⛔ BLOCKED"

# Verify feedback document records which tiers were re-run
if ! grep -qiE '(re-run|rerun|re.ran).*(unit|integration|e2e|acceptance)' \
    agent_state/phases/${PHASE}/reports/collective_feedback.md 2>/dev/null; then
  if grep -qiE '(fix|fixed|resolved)' \
      agent_state/phases/${PHASE}/reports/collective_feedback.md 2>/dev/null; then
    echo "⚠ WARNING: Feedback shows fixes were applied but no test tier re-runs recorded"
  fi
fi
```

### Wave 5v — Final verification at the committed code (always, right before Wave 6)

Every fix after Wave 3 changed code the evidence describes. The gate rejects evidence whose `code_sha`
isn't the current code commit, so refresh it once here, after the last fix:

```bash
P="agent_state/phases/${PHASE}"
git add -A -- . ':(exclude)agent_state' && git commit -qm "phase ${PHASE}: fixes before final verification" || true
CODE_SHA="$(git log -1 --format=%H -- . ':(exclude)agent_state' ':(exclude)docs' ':(exclude).claude' ':(exclude)deploy/k8s/overlays')"
STALE="$(for f in "$P"/reports/*.json agent_state/reconciliation/phase-${PHASE}/*.json; do
  [ -f "$f" ] && jq -e '.schema == "sdlc.test-results/v1"' "$f" >/dev/null 2>&1 \
    && [ "$(jq -r '.code_sha // ""' "$f")" != "$CODE_SHA" ] && echo "$f"; done)"
echo "stale evidence:"; echo "${STALE:-  none}"
```

When anything is stale, in this order:
1. **Redeploy.** On k8s run `PHASE=${PHASE} scripts/k8s/deploy.sh dev && PHASE=${PHASE} scripts/k8s/deploy.sh qa`,
   which gives fresh `deploy_dev`/`deploy_qa` evidence. On compose, rebuild and restart.
2. **Re-run the tests.** Spawn `test_runner` (subagent_type: test_runner): every tier at `CODE_SHA`,
   refreshing each tier sidecar (the Wave 3v prompt).
3. **Re-run the runtime tiers if the code under them changed.** Re-spawn `mobile_e2e_orchestrator`
   if mobile code changed, and `acceptance_test_agent` if any code changed since its run.
4. **Re-run the inventory LAST, unconditionally,** after steps 2–3 (and after Track B/D acceptance and
   performance have their final sidecars). Re-spawn `spec_test_reconciler` with EVERY results sidecar:
   `sdlc-graph.py gate --tc-only --results reports/test_results.json reports/acceptance_report.json reports/performance_results.json reports/e2e_results.json [reports/mobile_e2e_results.json …] --diff-base …`.
   Otherwise the gate reads a Wave 4 inventory in which acceptance/performance rows are still UNTESTED.
5. **Re-review security** (SEC-07) when code changed after Wave 4. Re-spawn `security_reviewer`
   (subagent_type: security_reviewer) scoped to
   `git diff $(cat $P/wave4_sha)..HEAD -- . ':(exclude)agent_state'`, then re-run its fix loop if it
   finds anything.

Then Wave 6. If Wave 6 routes failures back to Wave 5, Wave 5v runs again: the gate never sees
evidence from before the last fix.

---

## Wave 6: GATE

The PARENT session runs the gate check using the **Gate Verification Protocol**
(`~/.claude/skills/core/gate-verification.md`) — evidence-based, graded, cross-checked. The
binary "file exists + non-zero count" check below is only Layer 0; it is necessary but NOT
sufficient. The parent MUST also run Layer 1 (independent file:line re-verification — never
trust the subagent's report), Layer 2 (numeric `gate_score ≥ 0.90`), and Layer 3 (cross-model
refutation of high-stakes claims) before writing `gate.passed`.

**Order:** Layer 0 (below) → Layer 0c debate dispatch → Layer 0b roster + hook → Layer 1 re-verification → Layer 2
score → Layer 3 for security/tenant-isolation/"fixed" claims → write `gate_score.md` → only then
`gate.passed`.

0a. **What the hook enforces** (since the 2026-09-30 board review), so you don't re-implement it:
    - **Floor:** review floor, plus `test_runner`, `spec_test_reconciler` and `acceptance_test_agent`
      (and `deploy_dev`/`deploy_qa` on k8s projects) in every implementation phase.
    - **Test evidence:** every test agent's `sdlc.test-results/v1` sidecar must show verdict PASS,
      total > 0, 0 failed, 0 flaky, and no HIGH/MEDIUM case FAIL/BLOCKED/UNTESTED.
    - **Freshness:** evidence `code_sha` equals the current code commit, and the tree is clean.
    - **Commands:** `verify-commands.json` typecheck/lint/test really run.
    - **Security:** security findings can't be forced without per-finding acknowledgements.
    - **Stitch (check g):** with `docs/design/stitch.json`, every UI route in this phase's
      `ui_developer` / `mobile_developer` manifests has an approved/conformant Stitch screen at its
      latest revision whose render still matches its sha256; nothing is `pending_approval`,
      `sync_back_pending` or `drift`; every `stitch_deviations[]` entry is fixed or accepted + synced.
    - **TC inventory (check h):** `sdlc-graph.py gate --tc-only` — every HIGH/MEDIUM TC ID has a test named
      with it that ran and passed (results mode, every sidecar in reports/), no duplicate/malformed IDs,
      range-defined IDs included, no unacknowledged test weakening since `base_sha`. It is the only TC gate.

0b. **Agent-roster completeness (execution guarantee) — run FIRST, via the shared hook.** The single
    source of truth for this check is `.claude/hooks/verify-gate.sh`. It passes iff (1) every
    `roster.required` name has a `status:"completed"` line, (2) every completed line's non-null
    `report` file exists and is non-stub (no `total: 0` / `SKIPPED` in test reports; no unresolved
    `BLOCKING`), and (3) no `failed` line lacks a later `completed`. Run it and honor its exit code —
    do NOT re-implement a divergent copy here:
    ```bash
    bash .claude/hooks/verify-gate.sh "${PHASE}" || {
      echo "⛔ GATE BLOCKED by verify-gate.sh — see output above."
      echo "   Re-spawn any missing/failed agents (roster.required vs execution.jsonl) before gating."
      exit 1
    }
    ```
    If the hook is somehow unavailable, fall back to this equivalent membership check (the hook is
    authoritative — reconcile back to it if they ever diverge):
    ```bash
    ROSTER="agent_state/phases/${PHASE}/roster.json"
    EXEC="agent_state/phases/${PHASE}/execution.jsonl"
    python3 - "$ROSTER" "$EXEC" << 'PY'
    import json, sys, os
    roster = json.load(open(sys.argv[1]))
    required = roster.get("required", [])
    completed = set()
    if os.path.exists(sys.argv[2]):
        for line in open(sys.argv[2]):
            line = line.strip()
            if not line: continue
            try:
                e = json.loads(line)
                if e.get("status") == "completed": completed.add(e.get("agent"))
            except Exception: pass
    missing = [a for a in required if a not in completed]
    if missing:
        print("⛔ GATE BLOCKED — required agents never completed:", ", ".join(missing))
        print("   Re-spawn them before the gate can pass. (roster.required vs execution.jsonl)")
        sys.exit(1)
    print("✓ Roster complete — every required agent has a completed execution entry.")
    PY
    ```

0c. **Debate dispatcher — no orphaned decisions. Run it before 0b**, because the hook in 0b blocks
    on any open debate. Every debate request for this phase needs a verdict before the gate, and
    `verify-gate.sh` check (f) blocks until it has one.
    `debate-status.py` is the only reader of `agent_state/debates/`, because file names were never
    reliable: the old glob here matched nothing the protocol wrote.
    ```bash
    python3 .claude/hooks/debate-status.py --phase "${PHASE}"
    python3 .claude/hooks/debate-status.py --phase "${PHASE}" --check \
      || echo "⛔ Pending or invalid debate(s) above: run debate_moderator for each before gating"
    ```
    - **Pending, blocking or not:** spawn one `debate_moderator` per request, in the foreground.
      Independent requests can share a message.
    - **Non-blocking request whose verdict differs from `default_taken`:** relaunch that agent with
      the decision, set `default_taken` to the verdict, then go back to Wave 5v (including the security
      re-review) before gating. The relaunch changed code after the final verification.
    - **Under `--auto`:** a decision you resolve with a default instead goes into `unresolved.json`
      and `known_issues[]`.
    - **Withdrawing:** a request that no longer applies gets `"status": "withdrawn"` and a
      `withdrawn_reason`. Never delete it.

1. Verify ALL required files exist AND contain real content (tests, reviews, reconciliation,
   acceptance). This list is the hard `REQUIRED_REPORTS` set — it now includes the review and
   reconciliation reports that were previously omitted (and therefore skippable):
   - audit_report.md ✓
   - unit_tests.md ✓ (non-zero test count)
   - integration_tests.md ✓ (non-zero test count)
   - e2e_results.md ✓ (non-zero test count)
   - code_review_I.md ✓ · code_review_II.md ✓ · security_review.md ✓
   - dependency_scan.md ✓ · quality_gate.md ✓
   - specs_vs_impl.md ✓ · specs_vs_tests.md ✓  (reconciliation, in agent_state/reconciliation/phase-N/ — BLOCKING findings must be 0)
   - tenant_isolation.md ✓ (CONDITIONAL — required only when multi-tenant; else roster omits
     tenant_isolation_verifier and the manifest records the skip)
   - acceptance_report.md ✓ (non-zero use case count)
   - collective_feedback.md ✓

   **Conditional reports (required only when the phase has the relevant surface — otherwise recorded
   `not_applicable` in the manifest, never silently omitted; this matches `/develop` Step 6):**
   - (SAST and secret scanning run inside `code_quality_verifier` → `quality_gate.md`, always; there is no separate sast_scan.md)
   - migration_safety.md — when the phase adds/changes DB migrations (migration_safety_reviewer)
   - breaking_change_review.md — when the phase changes a contract an earlier phase consumes (breaking_change_reviewer)
   - visual_validation.md — when `*.wireframe.html` files exist for this phase
   - ui_test_results.md — when `frontend.enabled = true` (ui_code_optimization.md only if `/optimize` ran; the optimizers are not part of /develop)
   - accessibility_audit.md — when `accessibility_auditor` is in the roster (web UI phases)
   - ui_standards_audit.md (+ .json) — when `ui_standards_auditor` is in the roster; `blocking` must be 0
     or each remaining item carried forward (e.g. a reconstructed baseline awaiting approval)
   - test_results.md + test_results.json — always (Wave 3v `test_runner`); `blocking` must be 0
   - mobile_test_results.md · mobile_e2e_results.md (+ .json) · mobile_platform_audit.md — when the
     mobile agents are in the roster. `mobile_e2e_results.json` must show BOTH iOS and Android run
     (`blocked: false`, non-zero runs, 0 failed). A platform that could not run blocks the gate unless
     `docs/DECISIONS.md` records an accepted exception for this phase.
   - candidate_selection.md — when Wave 2 ran candidate-selection (N≥2). `solution_selector` is then
     in `roster.required`, so the roster check (0b) already blocks if it didn't run; this report must
     name a winner and its `BLOCKING` count must be 0 (or carried forward with a reason).

   **Report presence (content is validated by `verify-gate.sh` in 0b, which reads each report's JSON
   sidecar or its final `BLOCKING:N WARNING:N INFO:N` line — do not re-implement content regexes
   here; the old ones matched "Failed: 0" as zero tests and every reconciler's "BLOCKING vs DEFERRED"
   wording as a blocker):**
   ```bash
   # Test reports: must exist (zero-test / failure checks live in verify-gate.sh).
   in_roster() { jq -e --arg a "${1}" '.required | index($a)' "agent_state/phases/${PHASE}/roster.json" >/dev/null 2>&1; }
   TEST_REPORTS="unit_tests.md integration_tests.md e2e_results.md test_results.md acceptance_report.md"
   in_roster ui_test_agent     && TEST_REPORTS="$TEST_REPORTS ui_test_results.md"
   in_roster mobile_test_agent && TEST_REPORTS="$TEST_REPORTS mobile_test_results.md mobile_e2e_results.md"
   for REPORT in $TEST_REPORTS; do
     FILE="agent_state/phases/${PHASE}/reports/${REPORT}"
     [ -f "$FILE" ] || echo "⛔ GATE BLOCKED: ${REPORT} missing"
   done
   report_path() { case "${1}" in specs_vs_impl.md|specs_vs_tests.md|test_case_inventory.md|brd_vs_specs.md) echo "agent_state/reconciliation/phase-${PHASE}/${1}" ;; *) echo "agent_state/phases/${PHASE}/reports/${1}" ;; esac; }  # each bash block runs in a fresh shell
   # Review + reconciliation reports: must exist and be non-stub.
   for REPORT in code_review_I.md code_review_II.md security_review.md dependency_scan.md \
                 quality_gate.md specs_vs_impl.md specs_vs_tests.md; do
     FILE="$(report_path "$REPORT")"
     if [ ! -f "$FILE" ]; then
       echo "⛔ GATE BLOCKED: ${REPORT} missing — a review/reconcile agent was skipped"
     elif [ "$(wc -l < "$FILE")" -lt 3 ]; then
       echo "⛔ GATE BLOCKED: ${REPORT} is a stub — the agent did not actually run"
     fi
   done
   # Reconciliation must have no unresolved BLOCKING findings — read from the report's count line.
   for REPORT in specs_vs_impl.md specs_vs_tests.md; do
     FILE="$(report_path "$REPORT")"
     [ -f "$FILE" ] || continue
     NB="$(grep -Eo 'BLOCKING:[[:space:]]*[0-9]+[[:space:]]+WARNING:' "$FILE" | tail -1 | grep -Eo '[0-9]+' | head -1)"
     if [ -z "$NB" ]; then
       echo "⛔ GATE BLOCKED: ${REPORT} has no final 'BLOCKING:N WARNING:N INFO:N' line — re-run the reconciler"
     elif [ "$NB" -gt 0 ]; then
       echo "⛔ GATE BLOCKED: ${REPORT} reports BLOCKING:${NB} — resolve or carry forward with reason"
     fi
   done
   ```

2. **Regression is Wave 5v's full re-run.** `test_runner` runs every tier of every phase's committed
   tests at the current code commit, and its sidecars are what `verify-gate.sh` checks. Change-impact
   analysis (below) only chooses what to run *earlier*, during fix loops, for speed; it never replaces
   the Wave 5v run (see `~/.claude/skills/core/change-impact-analysis.md`):

   ```bash
   # Determine regression scope based on what this phase changed
   CHANGED_FILES=$(git diff --name-only $(git log --format=%H -1 -- agent_state/phases/$((PHASE-1))/gate.passed 2>/dev/null || echo HEAD~20) HEAD)
   CHANGED_PACKAGES=$(echo "$CHANGED_FILES" | xargs -I{} dirname {} | sort -u)

   # Check if shared layers changed (schema, auth, middleware, config)
   SHARED_CHANGED=$(echo "$CHANGED_FILES" | grep -E '(migration|schema|middleware|auth|config|docker)' | head -1)

   if [ -n "$SHARED_CHANGED" ] || [ "$PHASE" -eq 1 ]; then
     echo "Shared layer changed or Phase 1 — running FULL regression"
     # Full regression: all tests, all phases
     # Read commands from IMPLEMENTATION_GUIDELINES
   else
     echo "Running change-impact regression (affected packages only)"
     # Targeted regression: only tests in/importing changed packages
     # + always run E2E (catches integration issues)
   fi
   ```

   **Safety rules:** Phase 1, forced gates, and shared-layer changes always trigger full regression. See `change-impact-analysis.md` for the complete algorithm.

3. Run Gate Verification Layers 1–3 (`gate-verification.md`). Write
   `agent_state/phases/${PHASE}/reports/gate_score.md` with the evidence table + numeric score.

4. Gate passes ONLY when: Layer 0 clean AND **roster complete (0b passed)** AND **no pending debate
   without a verdict (0c)** AND **no BLOCKING reconciliation findings** AND Layer 1 has zero unproven
   items AND `gate_score ≥ 0.90` AND no Layer 3 claim was refuted → write gate.passed + manifest.json
   + git tag. Also write the phase decision + worklog rollup (see Post-Gate).

   Record the gate in the manifest too (the verify-gate Stop sweep and `/health` read `.gate`), then
   re-run the hook on the final state — a gate.passed that the hook would block is not a pass:
   ```bash
   M="agent_state/phases/${PHASE}/manifest.json"; [ -f "$M" ] || echo '{}' > "$M"
   # e2e_workflows_unlocked (C3): PHASE_PLAN §E2E Workflows Unlocked, via the graph; [] if unavailable
   WF="$(python3 .claude/hooks/sdlc-graph.py --json --full unlocked --phase "${PHASE}" 2>/dev/null | jq -c '.manifest_field // []' 2>/dev/null)"; [ -n "$WF" ] || WF='[]'
   jq --argjson score "${GATE_SCORE:-0}" --arg ts "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
     --slurpfile mig <(cat agent_state/phases/${PHASE}/migration_agent/manifest.json 2>/dev/null || echo '{}') \
     --argjson wf "$WF" \
     '.gate = {passed: true, verified_by: "verify-gate.sh", roster_complete: true, gate_score: $score, ts: $ts}
      | .e2e_workflows_unlocked = $wf
      | .schema.migrations_created = ($mig[0].migrations_created // $mig[0].migrations // [])' \
     "$M" > "$M.tmp" && mv "$M.tmp" "$M"
   touch "agent_state/phases/${PHASE}/gate.passed"
   bash .claude/hooks/verify-gate.sh "${PHASE}" || { rm -f "agent_state/phases/${PHASE}/gate.passed"; echo "⛔ final verify-gate failed — gate NOT passed"; }
   ```

5. If any layer fails → DO NOT write gate.passed. Route failures back to Wave 5 with the specific
   unproven items / low-scoring dimensions named.

**Auto-checkpoint:** Write `checkpoints/wave-6.json` with `tests_passing: true`, `gate_score: <score>`, `artifacts_produced: ["gate.passed", "manifest.json", "reports/gate_score.md"]`.

---

## Post-Gate: CONSOLIDATE + LEARN (inspired by agentmemory's consolidation pipeline)

**Runs ONLY after gate.passed is written.** This step extracts reusable knowledge from the phase execution for future phases. It's the equivalent of agentmemory's `consolidate` → `crystallize` → `lessons` pipeline, but deterministic and structural.

The PARENT session (inline, no subagent) reads all phase artifacts and writes `agent_state/phases/${PHASE}/lessons.md`:

### 1. Extract Lessons

Read:
- `reports/collective_feedback.md` — what bugs were found and how they were fixed
- `reports/quality_gate.md` (+ `code_review_I.md`, `code_review_II.md`) — what patterns were flagged
- `execution.jsonl` — which agents failed/retried and why
- `checkpoints/` — how long each wave took

Write `agent_state/phases/${PHASE}/lessons.md` using the **structured lessons format** (see `~/.claude/skills/core/structured-lessons.md`):

```markdown
# Phase ${PHASE} Lessons Learned
Generated: <timestamp>
Phase goal: <from PHASE_PLAN.md>

## Entries

### L-${PHASE}-001
- **Category:** <testing|implementation|security|performance|infrastructure|agent_performance|planning|ux>
- **Tags:** <language, domain, pattern name — comma-separated>
- **Type:** <pattern_that_worked|issue_encountered|agent_issue|anti_pattern|recommendation>
- **Summary:** <one-line description>
- **Detail:** <2-3 lines with context>
- **Evidence:** <which report/file proves this>
- **Reuse:** <actionable instruction for future phases>

(repeat for each lesson extracted from reports)
```

Each entry is categorized and tagged so downstream agents can query by domain instead of loading the entire file.

**Then aggregate into the root lessons index — this closes a broken loop.** The retrieval recipes
in `memory-as-tools.md` read `agent_state/lessons.md` (repo root), but lessons are WRITTEN per-phase
to `agent_state/phases/N/lessons.md`. Without this step `memory_search` finds nothing. After writing
the per-phase file, append its entries to the root index so future phases actually see them:

```bash
ROOT="agent_state/lessons.md"
PHASE_LESSONS="agent_state/phases/${PHASE}/lessons.md"
if [ -f "$PHASE_LESSONS" ]; then
  if [ ! -f "$ROOT" ]; then
    printf '# Lessons (cross-phase index — appended after each phase gate)\n\n' > "$ROOT"
  fi
  {
    printf '\n<!-- ==== Phase %s (gated %s) ==== -->\n' "${PHASE}" "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    # Copy the ### L-* entries from the phase file into the root index (skip the phase header).
    awk '/^### L-/{p=1} p{print}' "$PHASE_LESSONS"
  } >> "$ROOT"
fi
```
`/consolidate` later dedups/compresses this root index (off the hot path). Keep the per-phase file as
the source; the root index is the queryable aggregate.

### 2. Update Cross-Phase Patterns (append-only, indexed)

> **Skill reference:** `~/.claude/skills/core/structured-lessons.md` — full indexed format with confidence levels.

If `agent_state/patterns.md` exists, append new patterns with structured indexing. If not, create it.

```markdown
# Accumulated Patterns (auto-updated after each phase gate)

## Index by Category
- testing: P-001, P-003
- implementation: P-002

## Index by Tag
- go: P-001, P-002
- react: P-003

## Entries

### P-001
- **Source:** Phase ${PHASE}, L-${PHASE}-001
- **Category:** <category>
- **Tags:** <tags>
- **Pattern:** <what to do>
- **Evidence:** <which phases validated this>
- **Confidence:** LOW | MEDIUM | HIGH | DEPRECATED
```

Confidence upgrades automatically: LOW after 1 phase → MEDIUM if no contradictions → HIGH after validation in 2+ phases. Patterns that cause issues get downgraded to DEPRECATED.

This file is read by `project_planner` when planning Phase N+1 — agents query the index by category/tag instead of loading all entries.

### 3. Confidence Metadata for Codebase Knowledge

If `agent_state/codebase/` exists, update `.last-mapped` with a confidence indicator:

```bash
# Keep `sha:` = the commit the knowledge base was MAPPED at. /map --incremental diffs sha..HEAD, so
# overwriting it with the post-phase HEAD (as this step used to) made every later incremental map
# see "no changes" and froze the KB after the first gate while labelling it high-confidence.
F=agent_state/codebase/.last-mapped
MAPPED="$(grep '^sha:' "$F" 2>/dev/null | head -1)"; MAPPED="${MAPPED:-sha:unknown}"
HEAD_SHA="$(git rev-parse --short HEAD)"
if [ "${MAPPED#sha:}" = "$HEAD_SHA" ]; then CONF=high; else CONF=stale; fi   # stale → run /map --incremental
{ echo "$MAPPED"; echo "confidence:$CONF"; echo "validated_sha:$HEAD_SHA"
  echo "validated_by:phase-${PHASE}-gate"; echo "ts:$(date -u +%Y-%m-%dT%H:%M:%SZ)"; } > "$F"
```

If the gate FAILS, confidence degrades:
```bash
echo "confidence:degraded" >> agent_state/codebase/.last-mapped
echo "reason:phase-${PHASE}-gate-failed" >> agent_state/codebase/.last-mapped
```

**Key insight from agentmemory:** Memory isn't just stored — it has a lifecycle. Knowledge that was validated by a passing gate is HIGH confidence. Knowledge that predates a failed gate is DEGRADED (the codebase changed in ways the mapping didn't predict). This drives the `/map --incremental` recommendation in `/health`.

### 4. Phase Summary + Worklog Rollup (activity consolidation)

Individual reports answer "what did agent X find"; nobody assembles "what happened this phase." Write
a per-phase narrative that rolls up every wave, then regenerate the consolidated project ledger so a
human or a NEW session has one place to read.

Steps 4a and 4b follow the docs policy (both on in the lean profile, since they are rebuilt from
artifacts rather than maintained by hand): skip 4a unless `python3 .claude/hooks/docs-policy.py is-on phase_summary`
exits 0, and 4b unless `python3 .claude/hooks/docs-policy.py is-on worklog` does. Step 4c always runs.

**4a. Write `agent_state/phases/${PHASE}/PHASE_SUMMARY.md`** — a wave-by-wave narrative assembled
from the reports each wave already produced (not new analysis, just consolidation):

```markdown
# Phase ${PHASE} Summary — <goal>
Gate: PASSED (score <N>) · <date> · <NN> agents · <duration>

## What was built (Wave 2)
- <components/routes/migrations from manifest.artifacts>

## Tests (Wave 3)
- unit <N> / integration <N> / e2e <N> — all passing; TC-* coverage <N>%

## Review + Reconcile (Wave 4)
- code_review_I/II: <blocking resolved>; security: <findings>; deps: <CVEs>
- spec↔impl: <MISSING/EXTRA resolved>; spec↔test: <coverage>

## Decisions made
- <ADR-NNN / debate verdicts — link to docs/DECISIONS.md D-NNN entries>

## Fixed this phase (Wave 5)
- <bugs found → fixed, with the failure classification>

## Deferred / carried forward
- <known_issues + carried_forward + deferred TC IDs, with severity>
```

**4b. Regenerate the consolidated ledger:** run `/worklog` (it reads manifest + PHASE_SUMMARY +
DECISIONS + execution.jsonl and rewrites `docs/WORKLOG.md`). Commit `docs/WORKLOG.md` and
`docs/DECISIONS.md` with the gate.

**4c. Promote phase decisions:** ensure every decision captured in
`agent_state/phases/${PHASE}/decision-log.md` that has lasting scope has a `D-NNN` entry in
`docs/DECISIONS.md` (debate/ADR agents do this automatically; sweep here for dev/reconciler
deviations that weren't promoted). This is what makes decisions survive into the next session.
Record each missing entry with `bash .claude/hooks/remember.sh decide … --source agent:<name> --confidence reported` —
the guard denies direct edits to the ledger.

Defaults applied without a debate are decisions too. Record each `agent_state/debates/unresolved.json`
entry for this phase that has no `D-NNN` yet:
- title ending `[provisional: auto-resolved]`
- `--source agent:develop-orchestrator`
- `--link agent_state/debates/unresolved.json#<topic>`: one link per default. `remember.sh` refuses a
  second active entry for the same link, so re-running this step can't record a default twice. A
  refusal means the entry already exists; skip it.
- the entry's `reason` as the rationale

Otherwise the next session never learns a default was taken, and decides it again (board review
2026-09-30-debate, ARCH-21).

### 5. Record the requirement → acceptance baseline

The gate proved every FR delivered so far passes its acceptance tests. Record what the BRD said when it
did, so a later change to an FR's text shows up as CHANGED (its tests checked the old wording):
```bash
python3 .claude/hooks/acceptance-map.py --phase ${PHASE} --results agent_state/phases/${PHASE}/reports/acceptance_report.json \
  --record --out agent_state/phases/${PHASE}/reports/acceptance_map.json
```
Commit `agent_state/accept/fr-baseline.json` with the gate. A non-zero exit means an FR is still CHANGED,
which the gate should already have blocked. Don't pass `--ack` here; that decision belongs to the human.
