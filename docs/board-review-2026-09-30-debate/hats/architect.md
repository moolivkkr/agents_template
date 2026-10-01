# Architect hat — debate group (run 2026-09-30-debate, commit 77f221c)

Targets: `debate_moderator`, `debate_researcher`, `debate_advocate`, `debate_arbitrator` (all read in full).
Findings: `hats/architect.json`: 31 in total (0 CRITICAL, 7 HIGH, 18 MEDIUM, 6 LOW). It passes `board-review.py validate`.
I reproduced the runtime claims under `/tmp/.../scratchpad/arch/`, with `debate-status.py`, `remember.sh` and
`verify-gate.sh` from this commit.

## Verdict: the five most important problems

1. **Only one place handles the hand-back (ARCH-01).** The operating contract tells every agent to return
   `NEEDS_DECISION <topic>`, but only `develop-orchestrator.md` has a rule for that return. `/plan` has none,
   and `/plan` is where spec_writer and threat_model_agent meet architecture, security and data-model
   choices. `/test`, `/accept`, `/optimize`, `/discuss` and `/design` have none either. Sub-orchestrators
   such as brd_agent and ux_designer have no rule to pass a child's return up. A blocking request
   raised in `/plan` is first noticed at the `/develop` Wave 6 gate, after the phase has already been
   built on an unfinished spec.
2. **Review reasons have no consumer under `/autonomous` (ARCH-04).** These reasons are LOW confidence,
   INCOMPLETE, a second opinion that disagrees, a security verdict that isn't the hardened default, and an
   assumption. The moderator, the arbitrator and the orchestrator all send them to "the checkpoint".
   Under `/autonomous` the only checkpoint is before implementation, and it never runs `debate-status.py`.
   Its post-phase review reads only `auto-resolved.jsonl`. The design's human-review layer is never shown
   to a human before the gate.
3. **The second opinion isn't independent (ARCH-02).** The primary arbitrator records the `D-NNN` (step 6)
   before the Fable second opinion is spawned (step 7). The second-opinion arbitrator's Required Reading
   and step 1 then make it read that active `DECISIONS.md` entry, which carries the chosen option and its
   rationale, and tell it not to re-litigate an active decision. ARCH-11 adds that `debate-status.py`
   accepts `{}`, a second opinion run on Opus, or one whose verdict isn't an option. ARCH-12 adds that
   `model-routing.md` doesn't list this as a case for passing `model: fable`.
4. **Topics are joined by slug alone (ARCH-05).** Nothing ties a verdict to the request it answered.
   - Reproduced: a phase-5 HIGH-impact security request was reported RESOLVED by a phase-3 MEDIUM
     architecture verdict whose label isn't one of its options, and `--check` returned 0. Impact and
     domain are read from the verdict first, so the stale verdict also switched off the second-opinion
     and hardened-default checks.
   - When the old option ids don't overlap the new ones, the topic is INVALID instead. The moderator
     returns BLOCKED, nobody owns clearing the stale verdict, and the parent has no rule for that return
     (ARCH-14).
5. **The ledger isn't safe for the parallel debates the docs allow (ARCH-03).** Both the moderator and
   Wave 6 step 0c allow parallel moderators, but `remember.sh decide` has no lock and uses a fixed tmp name.
   - Reproduced: 15 of 20 concurrent runs lost a `D-NNN`. In 7 of them both calls printed the same id.
   - `promoted()` accepts any heading with that id, so the lost topic still passes the gate as "promoted".

Close behind:
- **ARCH-07:** `verify-gate.sh` exempts any report path under `agent_state/debates/` before the test-sidecar
  check. I reproduced a test agent with no evidence passing the gate that way.
- **ARCH-06:** the request schema has no field for the default a non-blocking requester built, but Wave 6
  needs to compare against it.

## Missing entirely

- **A link from verdict to request** (phase, or a request hash). Not in the verdict schema
  (`debate-protocol.md:107-147`) or in `debate-status.py`. The moderator's "the request hasn't changed
  since" (`debate_moderator.md:78-79`) has nothing to check against.
- **A shared NEEDS_DECISION / NEEDS_INPUT return handler.** I ran `grep -ln NEEDS_DECISION` and
  `grep -ln debate_moderator` over `.claude/commands/*.md`; the only full handler is in
  `develop-orchestrator.md`. The operating contract has no rule for passing a child's return upward.
- **A lock or atomic append for `docs/DECISIONS.md`.** `remember.sh` lines 64-97 are a read-modify-replace.
- **A record of the default a non-blocking requester built.** Not in either request schema
  (`debate-protocol.md`, `step-0-orient.md`).
- **A consumer of debate review reasons under `/autonomous`.** Checked `autonomous.md` in full, including
  the Step 3 checkpoint, the post-phase review and the Step 7 report.
- **A consumer of `<topic>.transcript.md` and `<topic>.verdict-detailed.md`,** and any check that the
  presentation order was actually randomized. I grepped commands, hooks and skills.
- **Any reader of `status: reversed` / `reversed_by`.** Nothing reworks code built on a decision that
  was overridden or reversed (ARCH-19).
- **Validation of second-opinion content** (`debate-status.py:198-200`).
- **Missing `tests/debate.test.sh` cases.** DS-01 to DS-26 cover none of: topic reuse across phases,
  concurrent `decide`, an empty second opinion, the slug produced by the acceptance-escalation template,
  `reset-phase` archive collisions, or the debates-path exemption in `verify-gate`. DS-22 asserts the
  non-blocking gap (ARCH-08) as intended behaviour.

**Defect classes from the 2026-09-30 run:**
- **"Debate requests written under a name the gate never globbed":** fixed for the gate, `/health`,
  `/pause`, `/worklog` and `/accept`, which all read through `debate-status.py`. It has come back in
  `reset-phase.md:86`. That file's `"$T"-*` archive glob moved another phase's pending blocking debate,
  and that phase's gate then passed (ARCH-17).
- **API envelope, `ui_developer/manifest.json`, browser E2E before deploy, candidate mode:** outside this
  group's agents. I didn't re-check them here.

## For other hats

- **ai_engineer:** I didn't verify these Claude Code behaviour claims in the moderator:
  - the `CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS` default of 20, and that "a spawn fails and should not be
    retried" at the limit (`debate_moderator.md:190-191`);
  - "a resumed agent runs in the background" under SendMessage (`:117`).

  Also check the effort split: moderator and researchers on medium, arbitrator on high. These claims are
  unverified.
- **security:**
  - A security verdict that isn't the hardened default, at MEDIUM confidence, passes `--check` with only a
    review reason (reproduced: verdict B, `hardened_default` A, rc 0). `debate-protocol.md:279-280` says
    the verdict must be the hardened default unless a cited MUST rules it out; nothing enforces that.
  - The sdlc-guard resolves `docs/DECISIONS.md` against the session's working directory, not the
    command's `cd`. That's why my scratch write under `/tmp` was denied (`sdlc-guard.sh:208-223`).
- **tester:**
  - Add the missing `debate.test.sh` cases listed above.
  - Eval T-007-debate exists, but nothing exercises multi-debate concurrency.
- **sre / devops:** `remember.sh add` (facts) also reads, transforms and then `mv`s with no lock. I only
  tested `decide`. Concurrent `/remember` calls may lose facts the same way; this is unverified.
- **senior_dev:**
  - `promoted()` falls back to a substring match on the verdict's basename, so `caching.verdict.json`
    matches a link to `tenant_caching.verdict.json`.
  - `classify()` treats any file named `*.second-opinion.json` as a second opinion, whatever its content.
