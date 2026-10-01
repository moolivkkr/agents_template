---
command: autonomous
description: "Run the full SDLC pipeline end-to-end with minimal human interaction. Auto-researches decisions, one human checkpoint before implementation, then fully autonomous develop + gate."
arguments:
  - name: confirm_each_phase
    required: false
    default: false
    description: "Pause for human review before EACH phase's /develop (default: only before Phase 1)"
  - name: resume
    required: false
    default: false
    description: "Resume from last checkpoint instead of starting fresh"
  - name: skip_init
    required: false
    default: false
    description: "Skip /init (use existing BRD + IMPL_GUIDELINES)"
  - name: max_phases
    required: false
    description: "Limit to N phases (default: all phases from BRD)"
---

# /autonomous — Full SDLC Pipeline (Minimal Human Interaction)

> **Spawning agents:** follow `~/.claude/skills/core/child-returns.md`. Wait for every agent you spawn before using its result, and act on its first line: `NEEDS_INPUT` (ask the user, or record a default under `--auto`), `NEEDS_DECISION <topic>` (run `debate_moderator`, then relaunch the agent with the decision), or a progress note (re-spawn it, at most twice).

Runs `/init` → `/plan` → `/develop` for all phases with auto-research for decisions and ONE human checkpoint before implementation begins.

```
Phase 0:  Environment pre-flight
Phase 1:  /init --auto (research all decisions)
Phase 1b: /map (persistent codebase knowledge base)
Phase 2:  /discuss --auto --phase=1 (surface assumptions)
Phase 2b: /plan --auto --phase=1 (PHASE_PLAN + specs + data-contracts)
Phase 2c: /design --phase=1 --auto (UI/mobile phases only; Stitch designs every screen, design_quality_reviewer approves, owner reviews at the checkpoint; Stitch absent → screens deferred + wireframe path)
Phase 3:  🛑 HUMAN CHECKPOINT (review all decisions + assumptions + UI designs)
Phase 4:  /develop --auto --phase=1 (includes Wave 3.5: local deploy + health check)
Phase 5:  Repeat discuss→plan→design→develop for remaining phases
Phase 5b: Local deploy (build + migrate + health check for final acceptance)
Phase 6:  /accept --auto (global acceptance + pipeline completeness)
Phase 7:  Final report + /health check
```

---

## How this command runs — READ FIRST (this is what keeps the run from stopping)

`/autonomous` is ONE continuous turn that executes many other commands. Runs used to stall
between steps for three reasons, and the rules below remove each one.

**1. Sub-commands are executed by you, not typed by the user.** Every "run `/x --flag`" below means:
invoke the Skill tool with `skill: "startup:x"` and `args: "--flag ..."` (inside the framework repo
itself the name has no `startup:` prefix). If the Skill tool isn't available, Read
`~/.claude/commands/startup/x.md` and follow it inline. Never tell the user to run the next
command; that is the stall this command exists to remove.

**2. A sub-command's closing "▶ Next: /y" line is for standalone use.** When a sub-command
finishes, don't print its "Next" hint and end the turn. Update the run state (below) and continue
immediately with the next step of THIS file, in the same turn.

**3. The run state is enforced by a Stop hook.** Keep `agent_state/autonomous/run.json` current:
```json
{"active": true, "status": "running", "phase": 1, "step": "plan_complete", "next_step": "design",
 "updated": "<iso8601>", "started": "<iso8601>", "args": "<the /autonomous args>"}
```
Write it at Step 0 and after EVERY step: bump `updated`, and set `step` and `next_step` from the
step list in *Resume Mode*. `session_id` starts `null`; the Stop hook binds the run to the first
session that stops, and ignores stops from any other session (so a status check in a second
terminal can't interfere). While background agents are running, ending the turn is allowed — their
completion wakes the session. Progress is judged from run.json, wave checkpoints, execution.jsonl
and git state, so long steps with many turns are not mistaken for a stall. API errors are recorded
into `last_error` by a StopFailure hook (permanent errors set `paused`), and after compaction or
resume a SessionStart hook restates the run's position. While `status` is `running`, `.claude/hooks/autonomous-continue.sh`
blocks the turn from ending and tells you the next step. It yields only when `status` is one of:
- `awaiting_human` — the Step 3 checkpoint, `--confirm_each_phase`, a security escalation with no
  hardened default, or a **security gate finding awaiting per-finding approval** (Step 4, Gate failures);
- `paused` — with a `reason`: escalation limit exceeded, catastrophic failure, or the user said stop;
- `failed` — unrecoverable;
- `complete` — Step 7 done.

If the hook reports the run `stalled` (no progress across repeated stops), set `paused` with the
real reason rather than looping.

**Every sub-command runs in `--auto` mode.** Pass `--auto` where a command defines it. Every command
also treats an active `run.json` (status `running`) as `--auto`, even if the flag was lost. In auto
mode a sub-command never waits for the user. Its "surface to user" points become: auto-resolve with
the recommended option, log to `agent_state/autonomous/auto-resolved.jsonl`, and carry forward to
the next human checkpoint or the final report. The exceptions are security decisions with no
hardened default, and security findings that block a gate. Both set `awaiting_human`. Nothing in auto
mode approves, defers, skips or forces a security finding on the human's behalf.

**Long runs and context.** A full run can exceed one context window. Claude Code compacts
automatically; after compaction, re-read `run.json` + `checkpoint.json` and continue from
`next_step`. If the session itself ends, `/autonomous --resume` picks up from the same place.

---

## Step 0 — Environment Pre-Flight

Verify the development environment is ready BEFORE spending tokens on agents.

```bash
echo "🔍 Environment pre-flight check..."

# 1. Docker running
docker info > /dev/null 2>&1 || { echo "⛔ Docker not running"; exit 1; }

# 2. Required tools available (read from IMPLEMENTATION_GUIDELINES if exists)
for cmd in git node npm; do
  command -v $cmd > /dev/null 2>&1 || echo "⚠ $cmd not found in PATH"
done

# 3. Ports not occupied (common dev ports)
for port in 3000 5432 8080; do
  lsof -i :$port > /dev/null 2>&1 && echo "⚠ Port $port already in use"
done

# 4. requirements/ directory exists and is non-empty
if [ ! -d "requirements/" ] || [ -z "$(ls requirements/)" ]; then
  echo "⛔ requirements/ directory empty or missing. Add requirement documents first."
  exit 1
fi

# 5. Framework hooks present in THIS project (Stop hook keeps the run going; SessionStart injects facts)
if [ ! -x ".claude/hooks/autonomous-continue.sh" ] && [ -d "$HOME/.claude/hooks/startup" ]; then
  mkdir -p .claude/hooks && cp "$HOME/.claude/hooks/startup/"*.sh "$HOME/.claude/hooks/startup/"*.py "$HOME/.claude/hooks/startup/"*.mjs .claude/hooks/ && chmod +x .claude/hooks/*.sh .claude/hooks/*.py
  [ -f .claude/settings.json ] || cp "$HOME/.claude/hooks/startup/project-settings.json" .claude/settings.json
  echo "✅ Installed framework hooks into .claude/ (takes effect for Stop checks from the next turn)"
fi
[ -x ".claude/hooks/autonomous-continue.sh" ] || echo "⚠ autonomous-continue hook missing — run ./install.sh in the framework repo; continuing without it"

# 6. Start (or resume) the run state
mkdir -p agent_state/autonomous
NOW="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
if [ "${ARG_RESUME:-false}" != "true" ] || [ ! -f agent_state/autonomous/run.json ]; then
  jq -n --arg now "$NOW" '{active:true,status:"running",session_id:null,phase:0,step:"preflight_complete",next_step:"init",started:$now,updated:$now}' > agent_state/autonomous/run.json
fi

echo "✅ Pre-flight passed"
```

If ANY critical check fails: **STOP** with specific fix instructions. Don't waste tokens on a doomed run.

---

## Step 1 — Initialize (`/init --auto`)

**Skip if:** `--skip_init` flag AND `docs/BRD.md` + `docs/IMPLEMENTATION_GUIDELINES.md` exist

Run `/init` with auto-research protocol:
- `brd_interviewer`: researches all gaps using the 5-level ladder (docs → infer → web → default → flag)
- `impl_guidelines_agent`: researches tech decisions using same protocol
- All decisions logged to `agent_state/autonomous/decisions.md` with confidence levels

**Checkpoint:** Write `agent_state/autonomous/checkpoint.json`:
```json
{ "step": "init_complete", "timestamp": "...", "decisions_count": 24, "low_confidence": 3, "auto_resolved_count": 0, "auto_resolved_security_count": 0, "auto_resolved_log": "agent_state/autonomous/auto-resolved.jsonl" }
```

---

## Step 1b — Map Codebase (`/map`)

**Run once after /init.** Creates persistent codebase knowledge base consumed by all downstream agents.

If the project has existing code (any `*.go`, `*.ts`, `*.tsx`, `*.py` or `*.java` outside
`node_modules`), run `/map` (Skill `startup:map`) now. That step was previously only an `echo`,
so the codebase knowledge base was never built.

Produces: `agent_state/codebase/` (tech-stack.md, architecture.md, quality.md, concerns.md, SUMMARY.md)

**Greenfield projects:** Skip this step (nothing to map). The codebase mapper handles empty codebases gracefully.

**Checkpoint:** Write checkpoint with codebase mapping summary.

---

## Step 2 — Discuss + Plan Phase 1

### Step 2a — Discuss Phase 1 (`/discuss --auto --phase=1`)

Surface assumptions and research decisions BEFORE planning:
- `phase_assumptions_analyzer` reads BRD + codebase state → structured assumptions with evidence levels
- `decision_researcher` investigates each MEDIUM/LOW confidence assumption (parallel, one per question)
- All decisions auto-resolved with recommended defaults in `--auto` mode
- Decision log: `agent_state/phases/1/decisions.jsonl`

Output: `agent_state/phases/1/DISCUSSION.md` (consumed by `/plan`)

**Checkpoint:** Write checkpoint with assumption count and auto-resolved decision count.

### Step 2b — Plan Phase 1 (`/plan --auto --phase=1`)

Run `/plan` with auto scope assignment:
- `project_planner` auto-assigns FR-* to Phase 1 by dependency analysis (foundational requirements first)
- All specs, data contracts, UI specs produced
- Verification + reconciliation runs
- `plan_goal_verifier` runs goal-backward check — in `--auto` mode: BLOCK verdict triggers auto-fix (route gaps to spec_writer, max 1 cycle), then force-proceed with warnings logged

**plan_goal_verifier in auto mode:** If BLOCK persists after auto-fix cycle, downgrade to WARN and log to `agent_state/autonomous/auto-resolved.jsonl` with `"category": "architecture"`. Do NOT halt the pipeline — surface in the HUMAN CHECKPOINT instead.

**Checkpoint:** Write checkpoint with phase plan summary.

---

### Step 2c — UI Design Contract (UI / mobile phases) — AFTER /plan

**Runs after `/plan`, never before.** `/design` hard-stops without `PHASE_PLAN.md` and
`specs/data-contracts.md`, and only `/plan` produces them. The old order (design, then plan)
failed every UI phase with "run /plan first".

```bash
# UI phase = a web frontend or React Native app is enabled AND this phase's plan has UI scope
APPS_UI=$(jq -r '(.tech_profile.frontend.enabled // false) or (.tech_profile.mobile.enabled // false)' agent_state/agent_registry.json 2>/dev/null)
grep -qiE "screen|page|UI|interface|dashboard|form|component|mobile|app" "docs/design/phases/${PHASE}/PHASE_PLAN.md" 2>/dev/null && SCOPE_UI=true || SCOPE_UI=false
[ "$APPS_UI" = "true" ] && [ "$SCOPE_UI" = "true" ] && HAS_UI=0 || HAS_UI=1
```

**If frontend phase detected (`HAS_UI == 0`):**

Run `/design --phase=N --auto` to produce the UI design contract. Google Stitch is the designer by default (`~/.claude/skills/ui/stitch-design.md`); `/develop`'s `ui_developer` / `mobile_developer` build against the approved renders and the wireframes. The command:

1. `wireframe_generator` maps each screen to a page archetype (`specs/archetype-mapping.md`)
2. `ux_designer` produces the per-screen wireframe contract — `<screen>.wireframe.html` (self-contained visual reference, both themes + breakpoints, all 4 states) + `<screen>.wireframe.md` (component/API bindings against `data-contracts.md`, design tokens, accessibility, `TC-UI-*` inventory)
3. **Stitch first (default):** `/design` drives the Stitch MCP directly per `~/.claude/skills/ui/stitch-design.md`: reuse or create the product's Stitch project (`docs/design/stitch.json`; an app with existing pages and no project runs `/stitch import --auto` first, so every page gets a scored baseline), set up the house-style design system once, and generate (new) or edit (changed) each screen with `deviceType` (MOBILE for React Native, DESKTOP for web) and `designSystem`, polling rather than retrying. **Autonomous approval:** `design_quality_reviewer` approves each render in render-approval mode (`stitch-state.py approve <key> --by design_quality_reviewer`); a BLOCK fix list goes back to `edit_screens` (max 2 cycles). Every autonomously approved screen is on the **owner-review list** (`stitch-state.py review-list`); low-fidelity imports are never approved autonomously and wait for the owner. `ux_designer` then normalizes each approved render into the two-file wireframe contract
4. **`design_quality_reviewer` runs the BLOCKING 11-dimension design gate** (`DESIGN_REVIEW.md`) — `ui_developer` must not start until this is PASS/FLAG

**Stitch unavailable:** if the MCP is not connected, times out, or errors, `/design` records every in-scope screen as `no_baseline` with a `deferred` record and a queue entry (`stitch-state.py defer`), designs it on the wireframe path (`wireframe_generator` + `ux_designer`), and logs it to `agent_state/autonomous/auto-resolved.jsonl` (`"category":"ux"`). It never blocks on the external MCP; the phase gate reports the deferred screens as WARNINGs and the final report lists the queue for Stitch.

**`--auto` design gate:** in auto mode, a BLOCK verdict triggers `/design`'s own auto-fix loop (route gaps to `ux_designer`, max 2 cycles). If still BLOCK, `/design` downgrades to WARN, logs it, and surfaces it at the next HUMAN CHECKPOINT — the pipeline does not halt here.

**Checkpoint:** Write checkpoint with wireframe count, design-gate verdict, design source (stitch / deferred), the owner-review list and the Stitch queue.

---

## Step 3 — HUMAN CHECKPOINT (before any implementation)

**This is the ONE required human interaction in the entire pipeline.**

Present a structured review document:

```markdown
# 🛑 Pre-Implementation Review

## Project Summary
[1-paragraph from BRD executive summary]

## Decisions Made (auto-researched)
### ⚠ LOW Confidence — NEEDS YOUR INPUT (N items)
| # | Question | Auto-Answer | Evidence | Risk |
|---|----------|------------|----------|------|

### 📋 MEDIUM Confidence — Quick Review (N items)
| # | Question | Auto-Answer | Evidence |
|---|----------|------------|----------|

### ✅ HIGH Confidence — Auto-Approved (N items)
[collapsed table — expand to review]

## Phase 1 Scope
- FR-* requirements: [list]
- Components: [list]
- Data contracts: [N endpoints typed]
- UI specs: [N screens]

## UI Designs for Your Review (Google Stitch)
Approved autonomously by design_quality_reviewer — from `python3 .claude/hooks/stitch-state.py review-list`:
| Screen | Route | Approved | Render (open locally) |
|--------|-------|----------|-----------------------|
[one row per screen; low-fidelity imports (`import_low_fidelity`) listed separately — they wait for you]
Stitch queue (screens deferred because Stitch was unavailable): [keys, or "none"]
Reply "approve designs" to accept them all (`stitch-state.py owner-review <key> --decision accepted`),
or give a change per screen: it becomes `/stitch request <key> "<change>"` before implementation.

## Tech Stack
[from IMPLEMENTATION_GUIDELINES]

## Key Assumptions (from /discuss)
[from DISCUSSION.md — CONFIRMED/DEDUCED/HYPOTHESIZED with evidence]

### HYPOTHESIZED Assumptions — NEEDS YOUR INPUT (N items)
| # | Assumption | Evidence Level | Impact if Wrong |
|---|-----------|---------------|-----------------|

### DEDUCED Assumptions — Quick Review (N items)
| # | Assumption | Evidence Chain | Confidence |
|---|-----------|---------------|------------|

────────────────────────────────────────
To proceed: type "go" or "approve"
To modify: describe what to change
To stop: type "stop"
────────────────────────────────────────
```

Before presenting it, set `run.json` `status` to `awaiting_human` (`next_step: "develop"`). This is
the one place the run is planned to stop. The review must also state the **gate policy** the user is
approving:

*"In autonomous mode, a phase gate that still fails after 3 fix cycles is force-gated with full
logging. There are two exceptions, and each one pauses the run instead:*
- *a structurally incomplete roster (a required agent never ran);*
- *any security finding, from `security_reviewer`, `tenant_isolation_verifier` or
  `dependency_scanner`. The run shows you each finding and waits for your decision on that specific
  finding."*

Approving the checkpoint is the explicit user approval that `/develop --force_gate` requires **for
non-security blockers only**. Record it in `approved.json` as `"force_gate_policy":
"approved_non_security"`. It approves no security finding: none exists yet, and a blanket
pre-approval can't stand in for a decision the human never saw (board review 2026-09-30, SEC-01).

**Wait for explicit user approval.** Do NOT proceed without it.

After approval (set `run.json` back to `status: running` and continue in the same turn):
- Lock all decisions as APPROVED
- Any LOW confidence items the user didn't modify: mark as "USER_ACCEPTED"
- Write `agent_state/autonomous/approved.json` with timestamp
- Stitch designs: for each screen the user accepted, `stitch-state.py owner-review <key> --decision accepted`;
  for each change, `/stitch request <key> "<change>"` (owner approves interactively now that the user is
  here), and re-run `/design` normalization for those screens before `/develop`

---

## Step 4 — Develop Phase 1 (`/develop --auto --phase=1`)

Fully autonomous — no more human prompts.

> **Execution path:** each `/develop --auto --phase=N` in this command MUST be run via
> the `/develop-orchestrator` wave-by-wave pattern (Skill `startup:develop-orchestrator`, args `--phase=N --auto`) (parent spawns a separate agent per wave with
> verification between each). Do NOT delegate a whole phase to a single agent — that is the exact
> "reviews/acceptance get dropped" failure the orchestrator exists to prevent (see the orchestration protocol at
> the top of `develop.md`). Autonomous mode makes this MORE important, not less: there is no human
> checking that Wave 4 actually ran, so the roster/`verify-gate.sh` execution guarantee is the only
> backstop, and it only works if every wave is spawned as its own logged agent.

### Auto-mode behaviors:
- **Escalations:** `continueWithDefault: true` for architecture/feature decisions — proceed with recommendation, log for review
- **Debates (`NEEDS_DECISION <topic>`):** run them as `~/.claude/skills/core/child-returns.md` says. A debate's review reasons have no one to read them mid-run, so the Post-Phase review below carries them to the report.
  - **Security debates that need a person** stop the run with `awaiting_human`, `reason: "security_debate"`:
    - INCOMPLETE (no clearly hardened option)
    - the Fable second opinion disagrees
    - a pending security debate at the gate

    `debate-status.py --check` blocks the gate on these and counts them as security findings, so the
    3-cycle force-gate can't pass them. The person's choice goes in `<topic>.override.json`.
- **Security escalations:** never auto-resolve with permissive defaults. Use the **hardened default** (most restrictive option). If no clear hardened default exists → PAUSE and surface to user even in auto mode. Security domains: auth patterns, token storage/caching, IDOR mitigation, encryption, PII handling, CORS/CSRF, rate limiting.
- **Gate failures:** Auto-fix loop (max 3 cycles per failing item)
  - Cycle 1: The owning role agent fixes → re-test the specific failure
  - Cycle 2: Re-run with fresh context → re-test
  - Cycle 3: Narrow the fix: the smallest change that resolves the finding → re-test. For a
    **non-security** item only, an out-of-scope part may be deferred with a logged reason. A security
    finding is never simplified away, skipped or deferred. No fix may remove or weaken auth,
    authorization, tenant or owner scoping, validation, CSRF or rate limiting to make a check pass;
    the Wave 5v security re-review treats that as HIGH.
  - After 3 cycles, **non-security blockers**: force-gate with full logging → continue to the next
    phase. Run `/develop`'s gate with `--force_gate`, citing `approved.json` `force_gate_policy`, and
    write `gate.forced` with the remaining blockers. `verify-gate.sh` still refuses to force past a
    roster whose required agent never ran. That case is a real STOP: set `run.json` `paused` with the
    missing agent named.
  - After 3 cycles, **any security blocker** (a BLOCKING count in `security_review.md`,
    `tenant_isolation.md` or `dependency_scan.md`): **PAUSE. Never force it.**
    1. Write `agent_state/autonomous/security_findings_phase-${PHASE}.md`. For each finding give its
       stable ID (`SR-…`, `TI-…`, `DS-…`), severity, `file:line`, the exploit scenario, the three fix
       attempts and why each failed.
    2. Set `run.json` `status: awaiting_human`, `reason: "security_findings"`, `next_step: "develop"`,
       and show the human the file's contents.
    3. The human answers **per finding**, with one of:
       - **fix**, with guidance: resume the fix loop for that finding;
       - **accept**, with a reason;
       - **stop**.
       A reply that covers several findings at once is valid only for findings the human was shown in
       that file.
    4. Only then, and only for findings the human accepted, add one entry per finding to
       `gate.forced.security_acknowledged[]`:
       `{"finding": "<ID + one-line description>", "approved_by": "<the name the human gave>",
       "reason": "<their reason, verbatim>"}`.
       An agent never writes, pre-fills or copies these entries from earlier phases, and never cites
       `approved.json` for them. `verify-gate.sh` refuses a forced gate whose security failures
       outnumber the acknowledgements.
    5. Accepted security findings are carried forward as CRITICAL items and listed in the Step 7
       report. `/accept` treats an unfixed accepted security finding as a release blocker to confirm
       again.
- **Test failures:** Fix implementation, not tests (max 3 retries per test agent)

### Escalation Circuit Breaker

Prevent runaway escalation loops in autonomous mode:

- **Max escalations per step:** 3 — additional escalations auto-resolve with recommended defaults (security escalations excepted: they follow the Security escalations rule above and never auto-resolve permissively)
- **In --auto mode:** continue with defaults but flag all as `"⚠ AUTO-RESOLVED — may need review"` in decision log and manifest `known_issues[]`
- **Max total escalations per phase:** 10 — if exceeded, EXIT auto mode entirely and surface to user:
  `"⛔ Phase ${PHASE} exceeded escalation limit (10). Review agent_state/debates/unresolved.json before continuing."`
- Unresolved decisions written to `agent_state/debates/unresolved.json`
- All auto-resolved decisions appear in the final report (Step 7) under "Decisions Made → Escalations resolved with default"

### Auto-Resolution Logging (MANDATORY)

Every auto-resolved escalation MUST be logged to:
`agent_state/autonomous/auto-resolved.jsonl`

**Format — one entry per auto-resolution:**
```jsonl
{"ts":"<ISO>","phase":N,"step":"<step_id>","escalation_number":N,"topic":"<decision topic>","question":"<full escalation question>","options":["A: <option>","B: <option>"],"auto_selected":"<option_id>","auto_rationale":"<why this default was chosen>","confidence":"HIGH|MEDIUM|LOW","category":"<architecture|security|data|ux|performance|other>","would_block":false}
```

**Logging rules:**
1. Log BEFORE applying the auto-resolution (not after)
2. Include the FULL question text (not truncated)
3. Include ALL options that were available
4. Tag the category to enable post-run filtering
5. If the auto-resolution involves security-adjacent topics (auth, access, tokens, permissions, tenant, encryption, secrets, CORS, CSRF, rate-limit), set `"category": "security"` and add `"security_flag": true`

### Git branching:
```bash
# Before each phase
git checkout -b phase-${PHASE}-implementation

# After gate passes
git tag phase-${PHASE}-complete
git checkout main
git merge phase-${PHASE}-implementation --no-ff -m "Phase ${PHASE} complete"
```

### Checkpointing (after each step):
```json
{
  "phase": 1,
  "step": "tests_complete",
  "timestamp": "...",
  "tests": { "unit": "pass", "integration": "pass" },
  "next_step": "reconciliation",
  "auto_resolved_count": 0,
  "auto_resolved_security_count": 0,
  "auto_resolved_log": "agent_state/autonomous/auto-resolved.jsonl"
}
```

The `auto_resolved_count` and `auto_resolved_security_count` fields reflect cumulative totals for the current phase at checkpoint time. These enable resume mode to know how many auto-resolutions occurred before interruption.

**On catastrophic failure** (build won't compile, infra won't start after retries):
```bash
# Rollback to last known good state
git checkout main
git branch -D phase-${PHASE}-implementation
```
Log failure report → continue to next phase if independent, or STOP if blocking.

---

## Step 5 — Repeat for Remaining Phases

```
For each phase N (2, 3, ... max_phases):
  1. /map --incremental (update codebase knowledge with changes from previous phase)
  2. /discuss --auto --phase=N (surface assumptions for THIS phase)
  3. /plan --auto --phase=N
  3a. /design --phase=N --auto (UI/mobile phases only, per Step 2c: Stitch edits changed screens and generates new ones, design_quality_reviewer approves, owner-review list grows; BLOCKING design gate; Stitch absent → deferred + wireframe path)
  4. If --confirm_each_phase: 🛑 HUMAN CHECKPOINT (same format as Step 3; run.json → awaiting_human)
  5. /develop --auto --phase=N   (via /develop-orchestrator wave pattern — see Step 4 MANDATORY note)
  6. plan_goal_verifier: goal-level verification (VERIFICATION.md)
  7. Checkpoint + run.json (next_step = next phase's "discuss", or "deploy" after the last phase)
```

Each numbered item is a Skill invocation (see *How this command runs*). Continue from one to the
next in the same turn.

### Post-Phase Auto-Resolution Review

After each phase completes in autonomous mode, before proceeding to next phase:

1. Carry the phase's debate review reasons into the log: for each topic that
   `python3 .claude/hooks/debate-status.py --phase ${PHASE} --json` lists with review reasons (LOW
   confidence, INCOMPLETE, a second opinion that disagrees, a non-hardened security choice, an
   assumption, auto-resolved), append
   `{"ts":…,"phase":N,"step":"debate","topic":…,"auto_selected":<verdict>,"auto_rationale":<the reasons>,"confidence":…,"category":"debate"}`
   to `agent_state/autonomous/auto-resolved.jsonl`, unless that topic and phase are already there.
2. Read `agent_state/autonomous/auto-resolved.jsonl` and filter entries for the just-completed phase
3. Count by category
4. Generate summary:

```
Auto-Resolution Summary — Phase ${PHASE}
────────────────────────────────────────
Total auto-resolved: ${N}
  architecture: ${N}
  data: ${N}
  performance: ${N}
  security: ${N} ${N > 0 ? "⚠ REVIEW RECOMMENDED" : ""}
  ux: ${N}
  debate: ${N}   (verdicts with review reasons, from debate-status.py)
  other: ${N}

Security-flagged decisions:
  ${list each security-flagged decision with topic + auto_selected}

Full log: agent_state/autonomous/auto-resolved.jsonl
```

5. If ANY security-flagged auto-resolutions exist:
   - Surface prominently: "⚠ ${N} security-adjacent decisions were auto-resolved — review recommended before next phase"
   - Include in the phase manifest under `"auto_resolved_security": [...]`
   - These will appear in the final autonomous report (Step 7)

**Phase dependency:** If Phase N gate was force-passed with known issues, Phase N+1 audit will surface them as carried-forward critical items.

---

## Step 5b — Local Deploy (before acceptance)

**Deploy the complete application locally before running global acceptance tests.**

`/accept` Step 0a handles the deploy + health check internally, but in the autonomous pipeline we surface it explicitly here so it's visible in the flow:

```
/develop phases complete → Step 5b: local deploy → Step 6: /accept --auto
```

The `/accept` command's Step 0a will:
1. Build all containers (--no-cache for clean acceptance run)
2. Start services via docker compose
3. Run pending migrations
4. Health check all endpoints (up to 90s)
5. Record deploy status to `agent_state/accept/deploy_status.json`

If the deploy is unhealthy, `/accept` still runs (to document failures) but caps release readiness at `NOT READY`.

---

## Step 6 — Global Acceptance (`/accept --auto`) — Skill `startup:accept`, args `--auto`

Run full acceptance testing across ALL completed phases:
- All personas exercised
- All FR-* acceptance criteria verified
- Contract shape assertions for every API endpoint
- Cross-phase workflow tests
- **Pipeline completeness validation** — holistic chain audit (requirements -> BRD -> specs -> code -> tests -> acceptance)

Results written to `agent_state/autonomous/acceptance-report.md`.

The pipeline completeness validator (`pipeline_completeness_agent`) runs automatically as part of `/accept` Step 5b. It produces:
- `agent_state/accept/pipeline_completeness_report.md` — scored verdict
- `agent_state/accept/traceability_matrix.md` — full forward+reverse chain
- `agent_state/accept/unresolved_gaps.md` — all gaps never resolved

**Completeness verdict feeds release readiness:** If completeness < 80%, release readiness is `NOT READY` regardless of acceptance test results.

---

## Step 7 — Final Report

After writing the report, set `run.json` to `{"active": false, "status": "complete", ...}`. The
Stop hook then lets the turn end.

```markdown
# Autonomous Run Report

## Summary
- Phases completed: N/N
- Total FR-* implemented: N
- Total tests: N passing
- Forced gates: N (see details below)
- Security findings accepted by a human: N (each listed below with finding, approved_by, reason)
- Low-confidence decisions: N (user approved: N, still open: N)

## Per-Phase Results
| Phase | Goal | Gate | Tests | Issues |
|-------|------|------|-------|--------|
| 1 | Auth + Users | PASSED | 48/48 | 0 |
| 2 | Core CRUD | PASSED | 124/124 | 2 warnings |
| 3 | Reports | FORCED (1 blocker) | 86/88 | 1 deferred |

## Decisions Made
- Auto-researched: N (HIGH: N, MEDIUM: N, LOW: N)
- User-approved at checkpoint: N
- Escalations resolved with default: N

## Auto-Resolution Audit

Total auto-resolved across all phases: ${N}

| Phase | Total | Architecture | Security | Data | UX | Performance |
|-------|-------|-------------|----------|------|----|-------------|
| 1 | ${N} | ${N} | ${N} | ${N} | ${N} | ${N} |
| 2 | ${N} | ${N} | ${N} | ${N} | ${N} | ${N} |

⚠ Security-Adjacent Auto-Resolutions (review these):
| Phase | Topic | Auto-Selected | Confidence |
|-------|-------|--------------|------------|
| ${phase} | ${topic} | ${option} | ${confidence} |

Full audit trail: agent_state/autonomous/auto-resolved.jsonl

## Pipeline Completeness
Score: N% — VERDICT (COMPLETE / NEAR COMPLETE / INCOMPLETE / FAILING)

| Dimension | Score |
|-----------|-------|
| Forward traceability | N% (N/N requirements fully traced) |
| Reverse traceability | N% (N unspecced items) |
| Reconciliation gaps resolved | N% (N/N resolved) |
| TC-* coverage | N% (N/N implemented) |
| Acceptance coverage | N% (N/N FR-* passed) |

Unresolved gaps: N (N critical, N high, N medium)
Full report: agent_state/accept/pipeline_completeness_report.md
Traceability matrix: agent_state/accept/traceability_matrix.md

## Security Findings Accepted Without a Fix
| Phase | Finding | Severity | Approved by | Reason |
|-------|---------|----------|-------------|--------|
[from each phase's gate.forced.security_acknowledged[]; "none" if empty]

## Designs Awaiting Your Review (Google Stitch)
[`stitch-state.py review-list`: every screen design_quality_reviewer approved after the checkpoint, with
its route and local render path, plus low-fidelity imports; and the Stitch queue — screens deferred
because Stitch was unavailable, and sync-backs not yet pushed. "none" if all empty.]

## Known Issues
[carried-forward items, forced gate items, deferred features]

## Time & Resources
- Total duration: Xh Xm
- Phases: N × (plan + develop)
- Checkpoints written: N

## Pipeline Health
[output of /health --verbose — integrity check of all agent_state/ artifacts]

## Next Steps
[recommendations based on known issues and deferred items]
[if any health issues found: recommend /health --fix]
[if any forced gates: recommend /forensics --phase=N for investigation]
```

---

## Resume Mode (`--resume`)

If the pipeline was interrupted (context exhaustion, crash, timeout):

```bash
RUN=agent_state/autonomous/run.json
RESUME_PHASE=$(jq -r '.phase' "$RUN")
RESUME_STEP=$(jq -r '.next_step' "$RUN")
# re-arm the run (it may be paused / awaiting_human / stalled)
tmp=$(mktemp); jq --arg now "$(date -u +%Y-%m-%dT%H:%M:%SZ)" '.active=true | .status="running" | .session_id=null | .updated=$now | del(.nudges,.last_nudged_update,.last_progress_fp,.stalled_reason,.reason)' "$RUN" > "$tmp" && mv "$tmp" "$RUN"
```

**Step ids** (`step` = last completed, `next_step` = what runs next):
`preflight` → `init` → `map` → `discuss` → `plan` → `design` → `checkpoint` → `develop` →
(per phase N ≥ 2: `map` → `discuss` → `plan` → `design` → [`checkpoint`] → `develop` → `verify`) →
`deploy` → `accept` → `report`. Resuming at `checkpoint` re-presents the review, and never assumes
approval. Resuming a run paused with `reason: "security_findings"` re-presents
`security_findings_phase-N.md` and waits for the per-finding answers. Re-arming the run is not an
approval of any finding.

- Resume from exactly where it stopped
- All previous state preserved in `agent_state/`
- Git branches and tags preserved
- No re-running of completed steps

---

## Dependencies

### Install step (before /develop per phase)
```bash
# Run dependency installation BEFORE implementation agents start
cd ${PROJECT_ROOT}

# Reproducible installs from the lockfile, with lifecycle scripts off (security/secure-coding.md §5).
# Each NEW package was vetted with vet-package.py by the coding agent that added it.
if [ -f package-lock.json ]; then npm ci --ignore-scripts
elif [ -f pnpm-lock.yaml ]; then pnpm install --frozen-lockfile --ignore-scripts
elif [ -f package.json ]; then npm install --ignore-scripts    # first install writes the lockfile: commit it
fi
# then run, explicitly, the build steps a skipped install script would have done (e.g. `npm rebuild esbuild`)
[ -f "go.mod" ] && go mod download
[ -f "requirements.txt" ] && python3 -m pip install -r requirements.txt
[ -f "Cargo.toml" ] && cargo fetch

# Verify
echo "✅ Dependencies installed"
```

---

## Safety Guarantees

1. **One human checkpoint** — review all auto-decisions before implementation
2. **Git branch per phase** — clean rollback to any phase boundary
3. **Checkpoint after every step** — resume from crash without re-work
4. **Auto-fix before revert** — tries to fix failures, doesn't blindly rollback
5. **Force-gate with full logging** — never silently skips failures, and never forces a security finding: those pause for a per-finding human decision
6. **Environment pre-flight** — catches infra issues in seconds, not minutes
7. **Decision audit trail** — every auto-decision documented with evidence + confidence
8. **Structured auto-resolution log** — every auto-resolved escalation captured in `agent_state/autonomous/auto-resolved.jsonl` with full question, options, rationale, category, and security flags for post-run audit
