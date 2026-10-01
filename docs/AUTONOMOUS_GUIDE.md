# Autonomous Guide — running `/startup:autonomous`

`/startup:autonomous` runs the whole SDLC — init, map, discuss, plan, design, develop for every
phase, then local deploy and global acceptance — with **one** required human checkpoint before any
code is written. This guide covers what it does, where it stops on purpose, and how to resume.

Command file: `.claude/commands/autonomous.md`.

---

## 1. Before you start

- `requirements/` exists and is non-empty (Step 0 stops otherwise).
- Docker is running; `git`, `node`, `npm` on PATH; common dev ports (3000, 5432, 8080) free. Step 0
  checks these and stops early with fix instructions rather than spending tokens on a doomed run.
- **Framework hooks are in the project.** `new-project.sh` copies `.claude/hooks/` and
  `.claude/settings.json` into new projects. For an existing project, Step 0 copies them from
  `~/.claude/hooks/startup/` (staged there by `install.sh`). If the hook is still missing, the run
  continues with a warning, but nothing will stop it from ending between steps. Hooks registered
  mid-session take effect for Stop checks from the next turn.

## 2. The flow

```
Step 0   Pre-flight + hooks + run.json
Step 1   /init --auto            BRD + IMPLEMENTATION_GUIDELINES + agents (gaps auto-researched)
Step 1b  /map                    codebase knowledge base (skipped for greenfield)
Step 2a  /discuss --auto         assumptions + decisions for phase 1
Step 2b  /plan --auto            PHASE_PLAN, specs, data contracts, goal verification
Step 2c  /design --auto                    UI / mobile phases only — AFTER /plan (Stitch designs, design_quality_reviewer approves)
Step 3   🛑 HUMAN CHECKPOINT
Step 4   /develop-orchestrator --phase=1 --auto
Step 5   per remaining phase: /map --incremental → /discuss → /plan → /design → [checkpoint] → /develop → verify
Step 5b  local deploy
Step 6   /accept --auto          global acceptance + pipeline completeness
Step 7   final report + /health
```

`/design` runs **after** `/plan`: it hard-stops without `PHASE_PLAN.md` and
`specs/data-contracts.md`, which only `/plan` produces. Google Stitch designs every new or changed
screen; under `/autonomous`, `design_quality_reviewer` approves each render and the screen joins the
owner-review list shown at the checkpoint and in the final report. If the Stitch MCP is unavailable,
each screen is deferred in `docs/design/stitch.json` (queued for Stitch) and designed on the wireframe
path; the run doesn't stop.

## 3. Why it no longer stalls

Earlier runs stopped after every sub-command and waited for the user to type the next one. Three
changes fix that:

1. **Sub-commands are invoked by the model through the Skill tool**, as `startup:<cmd>` with the
   flags in `args` (inside the framework repo, without the prefix). The user is never told to run the
   next command.
2. **A sub-command's closing "▶ Next: …" line is ignored under autonomous.** The model updates the
   run state and continues with the next step in the same turn.
3. **A Stop hook enforces it.** `.claude/hooks/autonomous-continue.sh` blocks the turn from ending
   while `agent_state/autonomous/run.json` has `"active": true, "status": "running"`, and tells the
   model the next step.

**Auto mode everywhere.** `/init`, `/map`, `/discuss`, `/plan`, `/design`, `/develop`,
`/develop-orchestrator` and `/accept` each treat either `--auto` **or** an active `run.json`
(status `running`) as auto mode, so a lost flag doesn't bring back the prompts. In auto mode a
"surface to user" point auto-resolves with the recommended option, is logged to
`agent_state/autonomous/auto-resolved.jsonl`, and is carried to the next checkpoint or the final
report.

## 4. `run.json` — the run state

```json
{"active": true, "status": "running", "session_id": null, "phase": 1, "step": "plan_complete",
 "next_step": "design", "updated": "<iso8601>", "started": "<iso8601>", "args": "<the /autonomous args>"}
```

Written at Step 0 and after every step (`updated` is bumped, `step` = last completed, `next_step` =
what runs next).

| `status` | Set when | Hook behaviour |
|----------|----------|----------------|
| `running` | Normal progress | Blocks the turn from ending |
| `awaiting_human` | The Step 3 checkpoint, `--confirm_each_phase`, or a security pause | Allows stop |
| `paused` (with `reason`) | Escalation limit exceeded, catastrophic failure, a roster agent never ran, or you said stop | Allows stop |
| `failed` | Unrecoverable | Allows stop |
| `complete` | Step 7 done (`active` becomes `false`) | Allows stop |
| `stalled` | Set **by the hook** when the run makes no progress across repeated blocked stops (default 3, `AUTONOMOUS_MAX_NUDGES`) | Allows stop, so a stuck run can't loop forever |

**How the hooks decide (2026-09-30 hardening):**
- **Progress** is a fingerprint of `run.json.updated`, the newest wave checkpoint, the
  `execution.jsonl` line counts and git state. Many turns inside one long `/develop` step therefore
  count as progress as long as agents keep checkpointing, logging or committing.
- **Background agents:** when the Stop input lists running background tasks (subagents run in the
  background by default), the turn is allowed to end without spending a nudge. The tasks'
  completion wakes the session.
- **One session per run:** `session_id` starts `null`. The first session that stops binds the run,
  and stops from any other session (a status check in a second terminal) are ignored.
  `--resume` clears the binding so the resuming session takes over.
- **API errors:** a `StopFailure` hook records `last_error` and `error_count`. Permanent errors
  (billing, auth, account, invalid request, model not found) set `paused` with a reason; transient
  ones (rate limit, overloaded, server) leave the run `running` for `--resume` or a supervisor.
- **After compaction or resume:** a `SessionStart` hook restates the run's position and the driver
  rules, because compaction truncates the `/autonomous` instructions.
- **Claude Code's 8-block cap** counts consecutive blocks with no tool use in between, so it only
  ends a genuinely stuck loop.

## 5. The one human checkpoint

Step 3 sets `status: awaiting_human` and presents a review: LOW-confidence decisions,
HYPOTHESIZED assumptions, phase 1 scope, tech stack, and UI designs. Reply `go` / `approve`,
describe changes, or `stop`.

**What approval also covers — the force-gate policy.** The review states: *in autonomous mode, a
phase gate that still fails after 3 fix cycles is force-gated with full logging, except (1) a
structurally incomplete roster (a required agent never ran) and (2) any security finding, which both
pause the run.* Approving the checkpoint is the explicit approval that `/develop --force_gate` requires
for **non-security** blockers only. It is recorded as `"force_gate_policy": "approved_non_security"` in
`agent_state/autonomous/approved.json`. A security finding (security_reviewer,
tenant_isolation_verifier, dependency_scanner) pauses for a per-finding decision: fix, accept or stop.
An accepted one becomes a `gate.forced.security_acknowledged[]` entry naming you, and `/accept` reports
NOT READY while it is unfixed. A forced gate writes
`gate.forced` with the remaining blockers, and the next phase's audit surfaces them as
carried-forward items. `verify-gate.sh` still refuses to force past a roster whose required agent
never ran — that pauses the run with the missing agent named.

With `--confirm_each_phase`, the same checkpoint is repeated before each later phase's `/develop`.

## 6. What legitimately pauses a run

- The Step 3 checkpoint (and per-phase checkpoints with `--confirm_each_phase`).
- A **security decision with no hardened default** — security choices never auto-resolve
  permissively; when there is no clear most-restrictive option the run sets `awaiting_human`.
- The **escalation circuit breaker**: more than 10 escalations in one phase exits auto mode
  (`paused`); unresolved items are in `agent_state/debates/unresolved.json`.
- A **roster gap**: a required agent has no completed entry in `execution.jsonl`.
- A catastrophic failure (won't build, infra won't start after retries) that blocks later phases.
- The hook marking the run `stalled`.

Anything else — a failing test, a blocking review finding, a design-gate BLOCK — is handled inside
the run by fix loops, with the outcome logged.

## 7. Resuming

```
/startup:autonomous --resume
```

Reads `phase` and `next_step` from `run.json`, re-arms it (`status: running`, `session_id: null`,
clears the nudge, progress and stall fields) and continues from that step. Step ids, in order:

```
preflight → init → map → discuss → plan → design → checkpoint → develop →
  (per phase N ≥ 2: map → discuss → plan → design → [checkpoint] → develop → verify) →
deploy → accept → report
```

Resuming at `checkpoint` re-presents the review and never assumes approval. After an automatic
context compaction mid-run, the model re-reads `run.json` + `checkpoint.json` and continues from
`next_step` without a resume command.

## 8. Other flags

```
--confirm_each_phase   Checkpoint before every phase's /develop
--skip_init            Reuse existing BRD + IMPLEMENTATION_GUIDELINES
--max_phases=N         Build only the first N phases
--resume               Continue from run.json
```

## 9. Artifacts

| Path | Contents |
|------|----------|
| `agent_state/autonomous/run.json` | Run state read by the Stop hook |
| `agent_state/autonomous/checkpoint.json` | Per-step checkpoint (counts, auto-resolution totals) |
| `agent_state/autonomous/approved.json` | Checkpoint approval, incl. `force_gate_policy` |
| `agent_state/autonomous/auto-resolved.jsonl` | Every auto-resolved decision: question, options, choice, rationale, category, security flag |
| `agent_state/autonomous/decisions.md` | `/init --auto` research decisions with confidence |
| `agent_state/autonomous/acceptance-report.md` | `/accept` results |

Each phase runs on its own git branch (`phase-N-implementation`) and is tagged `phase-N-complete`
when its gate passes.
