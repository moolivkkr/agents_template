# Phase ledger

The phase ledger is an observe-only record of how a phase's work actually ran: which subagents were spawned and when, whether each one started and finished, which files each touched, the parent's own task items, and where turns ended or failed. Hooks write it (`.claude/hooks/ledger.py`); agents never do. Step 1, described here, only observes. It never blocks a tool call, never changes one, and never fails a session.

## Why

The framework's tracking used to live only in prose (`develop-orchestrator.md`). The orchestrator asked each wave to append a `completed` line to `execution.jsonl` and to write `roster.json` and wave checkpoints. When a phase was steered interactively instead of through `/develop`, none of that was written. In rera, phases 5–7 have no roster, no checkpoints and no `base_sha`. Phase 7's `execution.jsonl` has 86 self-reported `completed` lines, with no start, fail or skip entries, inconsistent fields and one unparseable line.

Hooks fire however the work is driven (`/develop`, `/autonomous`, or a human steering turn by turn), so the ledger is the record that does not depend on anyone remembering to write it.

## What gets recorded

The ledger appends one JSON line per event to `agent_state/ledger/events-<YYYY-MM-DD>.jsonl`. The file is append-only and never rewritten. Writes take an `fcntl` lock so parallel subagents don't interleave lines, and the file rotates to `events-<day>.1.jsonl`, `.2`, … once it passes 20 MB.

| Hook | Ledger `event` | Fields beyond the common ones |
|------|----------------|-------------------------------|
| PreToolUse `Agent\|Task` | `spawn_requested` | `tool_use_id`, `subagent_type`, `description` (120 chars), `task` (from a `TASK: <id>` tag in the prompt), `prompt_sha256`, `prompt_head` (200 chars), `background` |
| PostToolUse `Agent\|Task` | `spawn_returned` | `tool_use_id`, `spawned_agent_id`, `status` (`completed` or `async_launched`), `total_ms`, `total_tokens`, `tool_uses` |
| SubagentStart | `started` | `task`, `tool_use_id`, `match` (`exact`, `fifo` or `none`), `card_chars` |
| SubagentStop | `finished` | `duration_s`, `tool_use_id` and `task` (exact, from the subagent's `.meta.json`), `transcript_bytes` (size only), `last_message_chars` |
| PostToolUse `Edit\|Write\|MultiEdit\|NotebookEdit` | `files` | `tool`, `files` (paths relative to the project) |
| PostToolUse `Bash` | `bash` | `command` (200 chars, with obvious secrets masked) |
| PostToolUse `TodoWrite` | `todos` | `counts` by status |
| TaskCreated / TaskCompleted | `task_created` / `task_completed` | `task_id`, `subject` (200 chars) |
| Stop | `turn_end` | `background_tasks` (count), `stop_hook_active` |
| StopFailure | `turn_error` | `error`, `details` (200 chars) |

Every line also carries these common fields:

- `ts`: UTC time, to the millisecond.
- `session_id`.
- `phase`: see [How the phase is chosen](#how-the-phase-is-chosen).
- `head`: the short git HEAD, read from `.git` without spawning git.
- `agent`: the subagent's `agent_id`, or `main` for the parent session.
- `agent_type`.
- `plan_version`: always `null` in step 1.
- `facts_v` and `decisions_v`: the first 8 hex characters of the sha256 of `docs/PROJECT_FACTS.md` and `docs/DECISIONS.md`.

### Linking a spawn to its subagent

These payload shapes were checked against a live `claude -p` run on Claude Code 2.1.285 on 2026-10-02. The recorded payloads are in `tests/fixtures/ledger/`.

- The spawn tool is `Agent`. Its PreToolUse `tool_input` includes `subagent_type`, `prompt`, `description` and `run_in_background`. The matcher also keeps the older name `Task`.
- SubagentStart carries only `agent_id` and `agent_type`, with no prompt and no `tool_use_id`. At start time the ledger therefore matches the oldest unclaimed spawn of the same type (`match: fifo`). This guess is what the task card uses.
- PostToolUse on `Agent` returns `tool_response.agentId`, which is the exact link. A background spawn (`async_launched`) returns it before SubagentStart fires, so the start is matched exactly. A foreground spawn returns it after the subagent finishes, and the return corrects any wrong FIFO guess.
- SubagentStop carries `agent_transcript_path`. The `.meta.json` file beside that transcript holds the `toolUseId`, so `finished` lines are matched exactly (`match: exact`). The ledger reads that small meta file and the transcript's size. It never reads the transcript itself.

To make a task traceable, put `TASK: <id>` in the spawn prompt (for example `TASK: W4-code_reviewer_I`). Without a tag the link still works through `tool_use_id`, but `task` is null.

## Privacy

- Prompts are stored as a sha256 plus the first 200 characters, not in full.
- Bash commands are cut to 200 characters. Bearer and basic auth headers, `password=`/`token=`-style values, `--password`/`--token` flags, `sk-…` keys, AWS access key ids and URL credentials are masked as `***`. The masking is pattern-based, so keep secrets out of commands anyway.
- Subagent transcripts and final messages are never copied. The ledger records only their size and length.
- Tool outputs are never stored.
- `agent_state/ledger/` is gitignored by default. To keep a phase's ledger in history, delete the `agent_state/ledger/` line from `.gitignore` and commit the files at phase end, or copy that phase's slice: `python3 .claude/hooks/ledger.py report --phase N --json > agent_state/phases/N/ledger-summary.json`. The `.state/` and `.lock` files inside the directory are scratch and are never worth committing.

## How the phase is chosen

The ledger uses the first rule that applies:

1. A pin: the `SDLC_PHASE=<n>` environment variable, or `"phase": <n>` in `agent_state/config/ledger-policy.json`.
2. An active `/autonomous` run: `agent_state/autonomous/run.json` with `"active": true` gives its `phase`.
3. The highest `agent_state/phases/<N>/` that is not closed. A phase counts as closed when it has a `gate.passed` file, when the manifest's `gate.passed` is true, or when its `gate.state`, `gate.status` or `status` is PASSED, NOT_APPLICABLE, CLOSED…, COMPLETE…, DONE or STUB. A directory with no manifest counts as open. `/plan` and `/develop` create the phase directory long before the gate writes its manifest, so a rule that required a manifest would keep labelling new work with an older phase that is still IN_FLIGHT.
4. The highest numbered phase directory.
5. `unscoped`.

The result is cached per session and recomputed whenever a phase directory, `run.json` or the policy file changes. If the automatic answer is wrong for a project (for example, a stray higher-numbered directory that isn't a phase), pin the phase in the policy file while the phase runs.

## Reading it

```bash
python3 .claude/hooks/ledger.py report                          # every phase, ~1.5k-token budget
python3 .claude/hooks/ledger.py report --phase 10               # one phase (repeat --phase for several)
python3 .claude/hooks/ledger.py report --phase 10 --compare-roster   # + required agents with no finished event
python3 .claude/hooks/ledger.py report --since 2026-10-02 --json     # full structured output
```

For each phase the report shows:

- main-session turns, spawns, subagents started and finished, and files and bash commands recorded;
- per agent type, finished out of started, with median and maximum duration;
- subagents that started but never finished;
- spawns that never started a subagent;
- files touched by more than one agent while those agents were live at the same time (overlap warnings);
- turn errors;
- the parent's task and todo items;
- whether `PROJECT_FACTS.md` or `DECISIONS.md` changed during the window;
- with `--compare-roster`, the roster's required agents that have no finished event. `deploy_*` entries are listed but not checked, because `deploy.sh` logs them and no agent is spawned for them.

To set aside a phase's data, filter by phase. Nothing is deleted. Example output from the test fixture (`tests/lib/ledger_cases.py`, `case_report`):

```
phase 5 — 10 events, 1 session(s), 2026-10-02T17:03 → 2026-10-02T17:03, HEAD 8457f4f
  main turns 1 · spawns 3 · subagents started 2 / finished 1 · files 2 · bash 0 · subagent tokens 0
  agent types (finished/started): backend_developer 1/1 (med 0s, max 0s); unit_test_agent 0/1
  ⚠ unfinished (started, no finish): 1
    unit_test_agent u1 task U-1 started 2026-10-02T17:03:00
  ⚠ spawns with no subagent start: 1
    Explore task lost 2026-10-02T17:03:01 — d t3
  ⚠ files touched by more than one live agent: 1
    src/shared.go ← b1, u1
  roster: 4 required, 1 finished per the ledger, missing 2: unit_test_agent, code_reviewer_I
    not agents (logged by deploy.sh, not checked here): deploy_dev
```

## The task card

When a subagent starts, the SubagentStart hook can add a short card to its context. The card is at most 3,200 characters, which is about 800 tokens, and has these lines:

- The phase, the matched task id, HEAD and `base_sha`, when those are known.
- The `PROJECT_FACTS` and `DECISIONS` versions, with a one-line pointer to read both files.
- When `roster.json` lists the agent's type as required, a line saying so.
- A reminder that the ledger is hook-written.

If nothing useful is known (no phase, no facts or decisions files, no task), no card is sent. The card is deterministic: the same state always produces the same card.

## Turning it off

| Scope | How |
|-------|-----|
| Whole ledger, one project | `agent_state/config/ledger-policy.json`: `{"enabled": false}` |
| Task card only | `{"enabled": true, "task_card": false}` |
| One shell or session | `SDLC_LEDGER=0` turns the whole ledger off, `SDLC_LEDGER_CARD=0` turns the card off. Setting either to `1` turns it back on even if the policy file says otherwise. |
| Remove | Delete the `ledger.py` hook entries from `.claude/settings.json` |

When the policy file is absent, the ledger and the card are both on: installing the hook is the opt-in.

## Failure policy

Any error inside the hook, such as bad JSON, an unwritable directory, a full disk or a busy lock (waited for up to 3 seconds), still exits 0 and prints nothing. The error is written as one line to `agent_state/ledger/errors.log`, which rotates at 256 KB. Only SubagentStart ever writes to stdout, and only to send the card. The hook adds about 25 ms per event on an M-series Mac, of which about 15 ms is Python starting up.

## Enabling it in a project

To enable only the ledger, without the framework's Stop gate check or other hooks, run:

```bash
~/.claude/scripts/startup/startup-project-update.sh --project ~/development/<app> --ledger-only --dry-run   # preview
~/.claude/scripts/startup/startup-project-update.sh --project ~/development/<app> --ledger-only
```

From a framework checkout, use `scripts/startup-project-update.sh` instead. `--ledger-only` changes only these files:

- `.claude/hooks/ledger.py`;
- its entry in `.claude/hooks/.framework-manifest.json`;
- the ledger's hook entries in `.claude/settings.json`, which are merged in without removing or editing anything already there (if the file doesn't exist, it is created with only the ledger hooks);
- the `agent_state/ledger/` line in `.gitignore`.

It adds no env keys and no other hook, and it doesn't build the graph. Running it again changes nothing, and a `ledger.py` that was edited in the project is kept unless you pass `--force`. A full update (without `--ledger-only`) installs the ledger along with everything else.

## Roadmap

- **Step 2: plan.** `plan.json` holds a DAG of tasks (id, agent type, depends-on, expected outputs) and `plan_version` gets filled in. The card then lists the task's expected outputs and dependencies, and the report shows tasks started before their dependencies finished.
- **Step 3: board and stale detection.** A live board of each task's state, and stale detection: a subagent started with no finish after N minutes, a spawn that never started, a plan task that never ran, work done against an older facts or decisions version.
- **Later: enforcement.** SubagentStop and TaskCompleted can block (exit 2), for example to refuse a finish whose expected outputs are missing. That stays off until steps 1–3 have shown the data is trustworthy, and each check is opt-in through the policy file.
