---
skill: child-returns
description: How a command or orchestrating agent spawns subagents and acts on what each returns — waiting for every child, NEEDS_INPUT, NEEDS_DECISION (run the debate), progress notes, overrides, concurrency
version: "1.0"
tags:
  - orchestration
  - subagents
  - decisions
  - core
---

# Spawning agents and reading what they return

Every command that spawns agents follows this, and so does any agent this framework tells to spawn
others. It used to live only in `develop-orchestrator.md`. Agents raised `NEEDS_DECISION` from
`/plan` and `/discuss` too, where nothing handled it, so the decision was first noticed at the
`/develop` gate, after the code was built (board review 2026-09-30-debate, AI-03 and ARCH-01).

## Wait for every child before acting on its result

**What the docs say** (`code.claude.com/docs/en/sub-agents`, checked 2026-09-30):
- **Non-interactive runs** (`claude -p`, the Agent SDK) and sessions without fork mode: a subagent
  runs in the background unless the Agent call passes `run_in_background: false`.
- **Interactive sessions on Claude Code v2.1.232 or later:** fork mode is on, every subagent runs in
  the background, and the parameter doesn't exist. There, "a subagent that launches background
  subagents waits for their results before it finishes".

**So:**
- **Where the Agent tool offers `run_in_background`, pass `false`**, and put independent spawns in
  one message. They run in parallel and the turn waits for all of them.
- **Where it doesn't** (an interactive session with fork mode on), don't verify a wave, merge or gate
  until every agent you spawned for it has returned its completion. Don't end your turn while one is
  still running.
- **Concurrency:** at most 20 subagents run at once by default
  (`CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS`). Above that a spawn fails with "Concurrent subagent limit
  reached" and must not be retried at once. A debate holds one moderator plus up to four children,
  so run at most four moderators at a time. When a spawn fails on the limit, spawn the rest after the
  current ones return.

## Act on the first line of every return

| First line | What you do |
|---|---|
| `COMPLETE` / `PARTIAL` / `BLOCKED` | Your command's own handling. |
| `NEEDS_INPUT` | **Interactive:** ask the user (AskUserQuestion for choices), then relaunch the same agent with its original prompt plus the answers. **`--auto` / `/autonomous`:** take the agent's recommended default, record it in `agent_state/debates/unresolved.json` (with `phase`, `topic`, `auto_resolved_with`, `reason`) and the manifest's `known_issues[]`, then relaunch. |
| `NEEDS_DECISION <topic>` | Run the debate (below), then relaunch the agent with the decision. |
| anything else | A progress note ("I'll now…", a plan, an offer to continue) is not a result; the current model can end a long turn that way. Re-spawn the agent with its original prompt plus `Your previous run ended before finishing (it returned: "<first line>"). Files already written: <paths>. Finish the assignment in this run.` At most two re-spawns, then treat it as failed (`/develop`: log `failed` in `execution.jsonl`). Don't resume it with SendMessage: a resumed agent runs in the background. |

**If you are yourself a subagent** that spawned the child (a sub-orchestrator such as `brd_agent` or
`architecture_orchestrator`), you can't run a debate or ask the user. End your own turn with the
same first line (`NEEDS_DECISION <topic>` or `NEEDS_INPUT`) and the child's question, so your parent
handles it and relaunches you.

## Running a debate for `NEEDS_DECISION <topic>`

1. **See the request:** `python3 .claude/hooks/debate-status.py --phase N`. It shows the request
   and any contract problem. A request with problems goes back to its agent, relaunched with the
   problems to fix.
2. **Apply the circuit breaker:** at most 3 debates per step and 10 per phase
   (`develop-steps/step-0-orient.md`). Beyond that, record recommended defaults in `unresolved.json`.
3. **Spawn `debate_moderator`** (waiting for it as above) with `REQUEST:
   agent_state/debates/<topic>.request.json` and the GROUND TRUTH line.
4. **Act on the moderator's return:**

   | Moderator returns | What you do |
   |---|---|
   | `COMPLETE <topic>: <label> (<confidence>)` | Relaunch the requesting agent with its original prompt plus `DECISION <topic>: <label> — agent_state/debates/<topic>.verdict.json. Continue from where you stopped.` In an interactive run, first show the user any review reasons the moderator listed. Under `--auto` they go to the review list below. |
   | `PARTIAL` (INCOMPLETE verdict, or the second opinion couldn't run) | Interactive: show the user and ask whether to accept the verdict or decide themselves. `--auto`: a non-security topic continues with the verdict and goes to the review list; a security topic stops the run for the user (`/autonomous`: `awaiting_human`). |
   | `BLOCKED <topic>: already decided by D-NNN` | Relaunch the requester with `DECISION <topic>: see D-NNN`, then withdraw the request (`"status": "withdrawn"`, `withdrawn_reason`). |
   | `BLOCKED` with request problems | Relaunch the requester to fix its request, then run the moderator again. |
   | `NEEDS_INPUT` (missing data or an ambiguous requirement) | Handle it as the `NEEDS_INPUT` row above. The question goes to the user, not to a debate. |

5. **Escalating yourself:** when the parent itself needs a decision (an architectural failure in a
   fix loop, a replan cap), write the request yourself first, with `from_agent` set to your command's
   name, then follow steps 2–4. The gate only sees debates that have a request file.

## Non-blocking requests

An agent that continued on a default has filed a request with `"blocking": false` and
`"default_taken": "<id>"`.
- **When to run it:** right after the wave that raised it, not at the gate.
- **If the verdict differs** from `default_taken`: relaunch that agent with the decision, then set the
  request's `default_taken` to the verdict.

`debate-status.py --check` blocks the gate until both have happened. If code changed as a result, go
back through the phase's re-verification (`/develop`: Wave 5v, including the security re-review)
before gating.

## The review list (what a person must see)

`python3 .claude/hooks/debate-status.py --phase N --json` lists each topic's `review` reasons:
- LOW confidence
- INCOMPLETE
- a second opinion that disagrees
- a security choice that isn't the hardened default
- an assumption
- auto-resolved

How each kind of run surfaces them:
- **Interactive commands:** show them before continuing.
- **`/autonomous`:** after each phase, append each topic with review reasons to
  `agent_state/autonomous/auto-resolved.jsonl` (category `debate`), so the final report carries it.
  Security topics that need a person block the gate on their own (`debate-status.py --check`), and
  the run stops at `awaiting_human`.

## When the user overrides a verdict

1. Write `agent_state/debates/<topic>.override.json`: `{topic, original_verdict, user_override,
   user_rationale, overridden_at, phase}`.
2. Append the same record to `overrides.jsonl`.
3. Record the reversal: `remember.sh decide … --reverses <the verdict's D-NNN>`.
4. Relaunch the agent that built on the verdict with `DECISION <topic>: <user_override> (override)`.
5. If an earlier phase already implemented the reversed decision, add a carried-forward item to this
   phase's manifest.
