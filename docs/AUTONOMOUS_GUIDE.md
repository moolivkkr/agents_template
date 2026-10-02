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
- **Framework hooks are in the project and current.** `new-project.sh` installs `.claude/hooks/` and
  `.claude/settings.json` into new projects. For an existing project, Step 0 runs
  `~/.claude/scripts/startup/startup-project-update.sh --no-build` (installed by `install.sh`): it adds
  missing hooks, refreshes stale ones, keeps any hook edited in the project (printing its diff), merges
  `settings.json` and ignores `agent_state/graph/`. Run it yourself beforehand with `--dry-run` to preview
  ([docs/SDLC_GRAPH.md](SDLC_GRAPH.md)). If the hook is still missing, the run continues with a warning,
  but nothing will stop it from ending between steps. Hooks registered mid-session take effect for Stop
  checks from the next turn.
- **python3 ≥ 3.9 with sqlite3** for the hooks and the project graph (`scripts/graph-preflight.sh`; FTS5
  recommended). Without it the graph is unavailable and phase gates block on the TC check.

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

**What does NOT pause a run: TC gate warnings (D-002).** The graph TC gate's four stricter checks —
malformed TC ID cells, range-defined IDs, and the gate's own runner-results and `base_sha` requirements —
are warnings until the project enforces them. An autonomous run never force-gates over them, because they
don't fail the gate; they appear as `⚠ tc warning` lines in `verify-gate.sh` (h) and in each phase's gate
summary. Track them with `python3 .claude/hooks/sdlc-graph.py warnings` and enforce with
`python3 .claude/hooks/sdlc-graph.py policy --strict` (or `--strict-check <check>`) when the project is
aligned. Everything the TC inventory blocked on before still blocks.

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
--one_step             Run only run.json's next_step, then end the turn (set by the supervisor's per-step mode)
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
| `agent_state/autonomous/supervisor.json` | Supervisor state for this run: budgets, cost per session, restarts, last exit |
| `agent_state/autonomous/supervisor.log` | One line per supervisor decision (launch, exit, restart, wait, outcome) |
| `agent_state/autonomous/supervisor-runs/attempt-N.*` | Each launch's stream-json output and stderr |
| `agent_state/autonomous/supervisor.config.json` | Optional default budgets (`max_cost_usd`, `max_hours`, `max_restarts`) |

Each phase runs on its own git branch (`phase-N-implementation`) and is tagged `phase-N-complete`
when its gate passes.

---

## 10. Unattended runs: the supervisor

The Stop hook keeps one session going between steps. It can't help once that session is gone: a
crash, a run the hook marked `stalled`, an API error that ended the turn through `StopFailure`, or a
closed terminal. `scripts/startup-autonomous-run.sh` is the outer loop for that case. `install.sh`
copies it to `~/.claude/scripts/startup/`, so every project can use the same copy.

```bash
cd <project>
~/.claude/scripts/startup/startup-autonomous-run.sh --max-cost-usd 150 --max-hours 12
# fresh run with /autonomous flags:
~/.claude/scripts/startup/startup-autonomous-run.sh --max-cost-usd 150 -- --skip_init --max_phases=2
# see the exact claude command without running it:
~/.claude/scripts/startup/startup-autonomous-run.sh --dry-run
```

Each launch is:

```
claude -p "/startup:autonomous --resume" --output-format stream-json --verbose \
       --permission-mode auto --permission-prompts none \
       (--session-id <new uuid> | --resume <session id>) [--max-budget-usd <remaining>]
```

The first launch of a new run omits `--resume` and passes the arguments after `--`. Inside the
framework repo, which has the command at `.claude/commands/autonomous.md`, the supervisor uses
`/autonomous`; elsewhere it uses `/startup:autonomous`, the installed name. Override with
`--command` or `AUTONOMOUS_COMMAND` (for example, once the framework ships as a plugin).

| Flag | Source (checked 2026-10-01, Claude Code 2.1.285) |
|------|------|
| `-p`, `--output-format stream-json`, `--verbose` | [CLI reference](https://code.claude.com/docs/en/cli-reference); `-p` with `stream-json` exits with "requires --verbose" otherwise (error string in the 2.1.285 binary; every [headless](https://code.claude.com/docs/en/headless) example pairs them) |
| `--permission-mode auto` | [CLI reference](https://code.claude.com/docs/en/cli-reference), [permission modes](https://code.claude.com/docs/en/permission-modes) |
| `--permission-prompts none` | [CLI reference](https://code.claude.com/docs/en/cli-reference), [headless: unattended runs](https://code.claude.com/docs/en/headless) (v2.1.259+) |
| `--session-id`, `--resume` | [CLI reference](https://code.claude.com/docs/en/cli-reference) |
| `--max-budget-usd` | [CLI reference](https://code.claude.com/docs/en/cli-reference) (print mode; counts only this call's spend, not a resumed session's earlier spend) |
| result event `total_cost_usd`, `subtype` | [cost tracking](https://code.claude.com/docs/en/agent-sdk/cost-tracking) |

### Before the first unattended run (user settings, set by you)

- **Auto mode must be available.** `--permission-mode auto` needs a supported model (Opus/Sonnet
  4.6+ on the Anthropic API) and no `disableAutoMode` in any settings file. When auto mode isn't
  available, Claude Code silently starts in Manual, and with `--permission-prompts none` every
  action that would prompt is denied. Check with an interactive session first. `defaultMode: "auto"`
  is ignored in project settings, but the supervisor passes the flag, so you don't need it.
- **Usage limits.** `autoContinueAtUsageLimit` (user settings) makes an interactive session wait out
  a claude.ai usage limit. The supervisor doesn't rely on it: a `rate_limit` error recorded by the
  StopFailure hook makes it wait (the "Retry after N seconds" hint when present, else
  `AUTONOMOUS_RATE_LIMIT_WAIT`, default 300 s) and resume.
- **Trust.** `-p` skips the workspace trust dialog and runs the project's hooks. Run it only in
  projects you trust.
- `jq` on PATH. The supervisor makes no network calls of its own. Notifications are local
  (`osascript` on macOS, otherwise a terminal bell; `AUTONOMOUS_NOTIFY=0` turns them off).

### What happens when the session exits

| `run.json` after the exit | Supervisor |
|------|------|
| `complete` | exit 0 |
| `awaiting_human` (checkpoint, security finding) | exit 10. Answer in an interactive session (`/startup:autonomous --resume`), then re-run the supervisor, or let that session carry on |
| a NEW permanent API error (`billing_error`, auth, account): `paused` by the StopFailure hook | exit 12, not retried |
| `paused` for any other reason | exit 11 |
| a NEW `rate_limit` error | waits for the retry hint, then resumes |
| `running` (a crash, or the turn ended), `stalled`, `failed`, other API errors | restart with exponential backoff (`AUTONOMOUS_BACKOFF_BASE` 30 s, doubling to `AUTONOMOUS_BACKOFF_MAX` 900 s; back to the base after progress) |
| no `run.json` | exit 32 (Step 0 pre-flight failed; see `supervisor-runs/attempt-N.stderr.log`) |

A run that is `paused`, `stalled` or `failed` when you START the supervisor is resumed: starting it
is the human's go-ahead. A run that is `awaiting_human` is not, because the question needs an answer.

### Budgets

| Budget | Default | Counts |
|------|------|------|
| `max_cost_usd` | none (a warning is logged) | `total_cost_usd` from each launch's stream-json `result` event. A resumed session reports its cumulative total, so per session the latest value counts; sessions are summed. The remainder is also passed as `--max-budget-usd`, so Claude Code stops inside a launch too. These are client-side estimates, not your bill |
| `max_hours` | 24 | wall-clock hours since this run was first supervised. A running launch is sent SIGINT at the deadline; a wait that would cross it ends the run instead |
| `max_restarts` | 10 | relaunches after a crash, stall, `failed` or API error. Per-step continuations aren't restarts |

Set them with flags (`--max-cost-usd`, `--max-hours`, `--max-restarts`), env
(`AUTONOMOUS_MAX_COST_USD`, `AUTONOMOUS_MAX_HOURS`, `AUTONOMOUS_MAX_RESTARTS`), `run.json.budgets`,
or `agent_state/autonomous/supervisor.config.json`, in that order of precedence. Counters persist in
`supervisor.json` for the run (keyed by `run.json.started`), so re-running the supervisor doesn't
reset them; `--reset-budgets` does. A breach pauses `run.json` with the reason.

### Exit codes

| Code | Meaning |
|------|------|
| 0 | Run complete |
| 10 | `awaiting_human`: checkpoint or security decision |
| 11 | `paused` for a human (escalation limit, roster gap, catastrophic failure) |
| 12 | Permanent API error (billing, authentication, account): not retried |
| 20 | `max_restarts` exceeded |
| 21 | `max_cost_usd` reached |
| 22 | `max_hours` reached |
| 30 | Another supervisor holds this project's lock |
| 31 | Usage error or missing prerequisite (`jq`, bad flag or budget value) |
| 32 | No `run.json` after a launch (pre-flight failed) |
| 129 | SIGHUP (terminal closed) |
| 130 | SIGINT |
| 143 | SIGTERM |

On SIGINT, SIGTERM or SIGHUP the supervisor sends the child SIGINT, which ends its turn cleanly (a SIGTERM'd
`claude -p` leaves the turn unfinished), then SIGTERM after `AUTONOMOUS_SUPERVISOR_KILL_GRACE`
seconds (default 30). It records `interrupted` and releases the lock. It works however it is started
(terminal, tmux, launchd, or `cmd &` from a script): a background job of a non-interactive shell starts
with SIGINT ignored, so the child is launched through a small exec shim (perl, else python3) that
restores the default INT/TERM/HUP handling first. To stop a backgrounded supervisor, send it SIGTERM
(`kill <pid>`); a SIGINT sent to a supervisor that itself started with SIGINT ignored never arrives.

One supervisor per project: `agent_state/autonomous/supervisor.lock/` holds its pid. A lock whose
process is gone is reclaimed.

### Session boundary (`--session-mode`)

- `resume` (default; what this command assumes today): one long session. A restart resumes the same
  session id (`claude -p --resume <id> "/startup:autonomous --resume"`), so the conversation and
  its context carry over. If that session can't be resumed, the next launch starts a fresh one.
- `per-step`: one fresh `claude -p` per pipeline step (`/startup:autonomous --resume --one_step`).
  The supervisor writes `step_boundary.json`, and the Stop hook lets the turn end once
  `(phase, next_step)` moves past it. Each step starts with a clean context and reads its state from
  `run.json` and `agent_state/`.

Which mode produces better runs is open (review 2026-09-30 §5: Anthropic's 2026 guidance says
continuous sessions also work on current models). It's meant to be measured with `/startup:eval`
before the default changes.

### `run.json` fields the supervisor adds

```json
{"budgets": {"max_cost_usd": 150, "max_hours": 12, "max_restarts": 10},
 "supervisor": {"state": "complete", "exit_code": 0, "exit_reason": "run complete",
                "session_mode": "resume", "budgets": {"max_cost_usd": 150, "max_hours": 12, "max_restarts": 10},
                "total_cost_usd": 42.17, "restarts": 1, "attempts": 2, "session_id": "<uuid>", "updated": "<iso8601>"}}
```

`budgets` is optional input. `supervisor` is written only while no `claude` child is running, so it
never races the session's own writes. `supervisor.state` is one of `running`, `waiting`, `complete`,
`awaiting_human`, `paused`, `api_error`, `budget_exceeded`, `no_run_state` or `interrupted`.
