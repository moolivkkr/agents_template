---
skill: subagent-supervision
description: How an orchestrator sizes, budgets, monitors and stops subagents so none runs away — the BUDGET line, the enforcing agent-budget.py hook, the monitoring loop, the intervention ladder, scripts for long jobs, impact-based test selection, and the per-wave budget ledger
version: "1.0"
tags:
  - orchestration
  - subagents
  - cost
  - budgets
  - core
---

# Supervising subagents: size, budget, watch, stop

Read with `child-returns.md`. That skill covers what to do with a return; this one keeps a subagent
from burning hours before it returns.

**Why it exists (ZoneOS phase 1, 2026-10):** about 35 Opus subagents used up a $200 plan.
- One agent was given "write 51 TC rows and run them on the cluster": about 400 tool calls, 7 hours
  and 800k tokens. Cost grows with calls × context, and context grows with calls.
- Agents sat through 75–90 minute test runs and a 7.5 hour dry run, polling.
- Agents retried a guard refusal for about 3 hours and committed nothing.
- The orchestrator saw tokens rising with no commits and answered "still running" six times.

Every rule below answers one of those.

## 1. Size the task before spawning

Estimate before every spawn: **units of work × tool calls per unit**. Typical rates:
- 3–5 calls per TC row written;
- 8–15 calls per endpoint implemented;
- 2–4 calls per review finding verified.

If the estimate is over **60 calls**, split the task:
- write at most 10 TC rows per agent;
- give an implementation agent one spec section;
- give a fix agent one finding cluster.

Several small agents in parallel cost less than one large one, because each starts with a small
context.

## 2. Every brief carries a BUDGET line

Put one line in the spawn prompt, after the ground-truth line:

```text
BUDGET: calls=60 minutes=30 no_progress=30
```

- `calls`: the hard cap on tool calls.
- `minutes`: wall clock.
- `no_progress`: tool calls without a commit or file edit.
- Omit a key to take the policy default.
- Raise it only for jobs that are long by nature (`test_runner`, `e2e_orchestrator`,
  `system_test_agent`). Set those in the policy's `types`, not ad hoc.

**`.claude/hooks/agent-budget.py` enforces the line.** It counts every subagent's tool calls by
`agent_id`, and the main session is never limited.
- **At spawn:** the subagent gets its budget card through `SubagentStart`.
- **At the soft limit** (default 60 calls or 30 minutes): the subagent is warned once to finish the
  unit, commit, write its checkpoint and return.
- **At the hard limit** (default 90 calls, 45 minutes, 45 calls without progress, or the same command
  4 times in a row): every tool is denied except a short wrap-up window (`git add`/`commit`/`status`/
  `diff`, writing the checkpoint). The agent returns `PARTIAL budget:<kind>` with its checkpoint path.
- **At 2 permission refusals** (guard, auto-mode classifier, RBAC, quota): the agent is stopped. It
  may make one commit of finished work, then returns `BLOCKED <refusal>`.

Defaults and per-type limits: `agent_state/config/budget-policy.json`
```json
{"enabled": true,
 "defaults": {"calls_soft": 60, "calls_hard": 90, "minutes_soft": 30, "minutes_hard": 45,
              "no_progress_soft": 30, "no_progress_hard": 45, "repeat_hard": 4, "refusals_hard": 2},
 "types": {"test_runner": {"minutes_soft": 60, "minutes_hard": 90}}}
```
To switch it off: `SDLC_BUDGET=0` or `"enabled": false`. It fails open: a bug in the hook never blocks
work, and errors go to `agent_state/budget/errors.log`.

## 3. The blocker rule (in every brief, and enforced)

> On a permission refusal from the guard, the auto-mode classifier, RBAC or a quota, or an outage
> that isn't yours: stop, don't retry, don't route around it. Return `BLOCKED <exact refusal>`.

The parent never relaunches a BLOCKED agent with the same task. It sends the refusal to the human:
- interactive: say it now;
- `/autonomous`: set `run.json` `paused` with the refusal as `reason`.

Don't ask a different agent or session to do the refused action. That gets around the human's
permission decision.

## 4. Watch while agents run

The completion notice of a background subagent carries `<usage>` with `subagent_tokens`, `tool_uses`
and `duration_ms` (observed first-hand; not in the docs). Use it in the wave budget ledger (§8).

While agents run, at every wake-up (a completion notice, an interim notice, or a check-in you
scheduled), run:
```bash
python3 .claude/hooks/agent-budget.py status        # running agents: calls, minutes, no-progress, refusals, flag
```
- **`RUNAWAY`:** no progress for 20+ minutes with 10+ calls since the last commit or edit, or any
  refusal. Go to §5 now.
- **`WARN`:** past a soft limit. It should return soon; check again at the next wake-up.
- **`CAPPED:<kind>`:** it is wrapping up. Wait for its return.

**Never answer "still running" twice in a row without reading `status`.** "Tokens up, no new commit"
is the runaway signal, not a sign of progress.

## 5. The intervention ladder

1. **`SendMessage`** to the agent: "Stop at the next clean point: commit, write your checkpoint,
   return PARTIAL." It arrives between tool calls.
2. **If it's still running at the next wake-up:** `TaskStop` it.
3. **Relaunch from its checkpoint** with a smaller task and a tighter `BUDGET`. Never relaunch the
   same oversized brief.

Record each step in `execution.jsonl`, with status `stopped` and the reason.

## 6. Long jobs are scripts, not babysat agents

Deploys, full test sweeps, dry runs and anything else over about 10 minutes run as a background
script that writes a JUnit or sidecar file. Use a `Bash` call with `run_in_background`, or the
project's runner.
- No agent sleeps or polls through the run.
- When it finishes, read the sidecar.
- Wake an agent only for a failure, and give it only the failing slice: the test ID, the error and
  `file:line`, not the whole log.

## 7. Run only the tests a change affects

During fix loops, choose tests by impact:
```bash
python3 .claude/hooks/sdlc-graph.py diff-context --base <sha>   # changed symbols → endpoints, tables, TCs, FRs
python3 .claude/hooks/sdlc-graph.py impact <file|symbol>        # one target's reverse closure → tests, TC IDs
```
Full sweeps run only at Wave 3v, Wave 5v and the gate.

## 8. Handoffs and the per-wave budget ledger

- **Returns stay short:** at most 10 lines plus a path to a structured findings file (id, cause,
  owner, status) that the next agent can query.
- **Per-wave budget ledger:** append one line per wave to `agent_state/phases/N/budget.jsonl`:
  ```json
  {"wave": "3a", "agents": 4, "est_calls": 180, "actual_calls": 205, "subagent_tokens": 1240000, "minutes": 38, "overrun_pct": 14}
  ```
  The actuals come from the `<usage>` blocks, or from `agent-budget.py status --all --json`.
- **A wave more than 25% over its estimate:** stop and say so.
  - Interactive: tell the user.
  - `/autonomous`: write it to `auto-resolved.jsonl` (category `performance`). If it happens twice in
    a phase, set `paused` with the reason.

## 9. Models and context

- **Choose models by task:** Sonnet for mechanical work (tests, acceptance, docs); Opus for design,
  debugging and review. That's the agents' `model:` frontmatter (commit 15910e9).
- **Restart the orchestrator at wave boundaries:** in a long run, restart from `run.json` and the
  wave checkpoint rather than carrying a multi-day context. `/autonomous --resume` and the supervisor's
  per-step mode do this.
