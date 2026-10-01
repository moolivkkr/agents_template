# Tester hat: debate agents (run 2026-09-30-debate-2, commit 95fb871)

Targets: `debate_moderator`, `debate_researcher`, `debate_advocate`, `debate_arbitrator`. There are 35 findings in all: 10 HIGH, 23 MEDIUM and 2 LOW. The findings table is in `tester.json`.

## How I checked

I built every gate claim as a fixture and ran the real gate on it. Each fixture starts from a passing implementation phase built with the `tests/verify-gate.test.sh` helpers (implementer, review and verification floor, fresh PASS sidecars, `gate.passed: true`). I then added a debate with `tests/lib/make_debate.py`, broke it in one way, and ran `CLAUDE_PROJECT_DIR=$D bash .claude/hooks/verify-gate.sh 1`.

The scripts are in `/tmp/claude-501/-Users-kishoremoli-development-startup-agents/dd7de203-8961-486b-bc72-acd57dd003fe/scratchpad/tester-debate2/`: `sim.sh` (scenarios S0–S18), `sim_extra.sh` (S19–S22), `sim_s4b.sh` and `sim_s23.sh`. Their output is in `out*.txt`. The prompt-lint mutation test ran in the same directory under `mut/`, a `git archive` copy of the repo.

**What still holds:**
- `tests/verify-gate.test.sh` passes 58/58 and `tests/debate.test.sh` passes 79/79.
- The 2026-09-30 fixes still hold:
  - a FAIL sidecar logged under `agent_state/debates/../` blocks
  - a pending debate, an unpromoted verdict, a bad option and a verdict with no artifacts each block
  - a close HIGH-impact call with no second opinion blocks (DS-19)
- The gate recomputes the primary verdict's totals, gap and confidence independently, which is the right design.

**Where the gaps are:** almost all of them sit where the gate trusts a field written by the agent it is checking.

## Verdict: top five problems

1. **The moderator reports COMPLETE on topics the gate blocks, and nothing repairs them (TEST-14).**
   - **What goes wrong:** step 10 of the moderator and step 7 of the arbitrator read only `.problems`. Gate reasons are kept in `.gate`: a missing D-NNN, a missing second opinion, and a mismatched `default_taken`.
   - **What I saw:** an unpromoted verdict shows `{"status":"resolved","problems":[]}` while `--check` exits 2.
   - **Why it doesn't recover:** step 1 returns an "already resolved" verdict as it is. Re-spawning the moderator therefore never retries the promotion or the second opinion. Under `/autonomous` the blocker is force-gated after three cycles.

2. **The decision ledger can contradict the verdict and the gate still passes (TEST-06, TEST-07, TEST-08, TEST-17).** `promoted()` only checks that some block's `- link:` line names the verdict path, and that path is the same on every re-run.
   - A re-run that flips the verdict from A to B passes on the old D-001 ("option A"), or on two active, contradictory entries.
   - An entry with status `reversed` still counts.
   - A user override is never reversed in the ledger.
   - LOW-confidence calls reach the ledger without the `[provisional]` marker.

   Every later session reads the ledger as ground truth, so all of these mislead it.

3. **Withdrawing a request clears a pending security debate with no person involved and no trace left (TEST-09).** One sentence in `withdrawn_reason` is enough:
   - no `override.json`
   - no `security_acknowledged` entry
   - no review reason

   Three places tell agents to withdraw requests. Related ways a security decision slips past a person:
   - a malformed security request counts as a non-security finding, so it can be force-gated (TEST-20)
   - a mistyped marker makes the request invisible (TEST-19)
   - a request in a phase no gate covers is never checked (TEST-21)
   - the legacy file shapes skip every v2 check (TEST-18)

4. **The independent second opinion is skipped, or satisfied by something stale (TEST-01, TEST-04, TEST-05, TEST-12, TEST-13).**
   - **Skipped:** an `unverifiable` decisive claim or an `EVIDENCE INCOMPLETE` gap should cap confidence at MEDIUM and trigger the second opinion. Neither does, and a HIGH verdict passes without one.
   - **Stale:** a second opinion left over from the request's previous version passes after the re-run's Fable spawn failed.
   - **Self-inconsistent:** a second opinion whose own scores favour the other option counts as agreeing, even on security.
   - **Same model:** a second opinion run on the primary's model passes security; it only goes on the review list.

5. **The debate agents' judgment can't be measured (TEST-25 to TEST-31), and the artifact check accepts stubs (TEST-10, TEST-11).**
   - **T-007 R1 can never pass.** Each fixture copy's ledger starts at D-001, so merging the copies gives four `### D-001` blocks, and R1 fails on a correct run.
   - **No baseline:** T-007 has none, and the seed baseline has no T-007 row.
   - **The trajectory can't be checked:** its steps (mode, model, `run_in_background`, who wrote the verdict) aren't recorded anywhere the eval reads.
   - **The bias checks are too weak:**
     - the position check uses the clear-cut case
     - no request seeds `initial_reasoning`
     - R5 grades the judge's confidence instead of the second-opinion mechanics
   - **The prompt lints miss inversions:** DL-07, DL-21 and DL-22 still pass after I inverted the sentences they guard.
   - **DL-01 never runs in a worktree:** it skips every file whose path contains `/worktrees/`.
   - **Stub artifacts pass:** files of 2 bytes satisfy "a debate behind the verdict", and INCOMPLETE verdicts skip that check entirely.

## Missing entirely

These checks don't exist anywhere. Where I looked:

| Missing | Where I looked |
|---|---|
| A link from the second opinion to the request or primary it answered (`request_sha`, primary order) | protocol §"Second opinion" (line 169); `second_problems` (debate-status.py:281-296) |
| A machine-readable evidence-gap field in the verdict; gaps live only in transcript prose | verdict format, protocol:110-144; `verdict_problems` |
| Any check of argument or research *content*: citations, template headings, absence of self-scores | debate-status.py:269-277; verify-gate.sh check (b), which skips debate artifacts at 364-370 |
| A record of who wrote each debate file, in which mode, on which model | the agents' completion-log blocks; the transcript format at moderator:186-193; `execution.jsonl` contract |
| Freshness against the BRD and PROJECT_FACTS (acceptance-map has it for tests; verdicts don't) | `request_sha` keys (debate-status.py:98); no BRD read anywhere in debate-status.py |
| A gate or test case with two promoted debates in one phase | `make_debate.py:48` hardcodes D-001; verify-gate.test.sh:330-378; debate_cases.py |
| A cross-phase `debate-status.py --check` | accept.md:715 (release notes only); develop-orchestrator 0c is phase-scoped |
| A requester- or threat-model-named hardened option | request format, protocol:75-93 |
| A measured T-007 baseline, and an eval case that runs a close call in both orders or seeds `initial_reasoning` | baselines/2026-07-07-seed.json; T-007 `task.md`, `rubric.json` |

## For other hats

- **architect:**
  - The orchestrator's Wave 6 step 0c (develop-orchestrator.md:1224-1232) covers pending, non-blocking, `--auto` and withdrawal. It has no branch for "resolved, but with gate reasons" or "stale". Moderator step 1 has the same hole.
  - child-returns.md:68 tells `--auto` to continue on a non-security PARTIAL (Fable failed). The gate then blocks that topic (DS-19), and the only way out is the force path.
- **security:**
  - TEST-09 (withdrawing a security debate)
  - TEST-18 (legacy file shapes on a security topic)
  - TEST-20 (a malformed security request counted as a non-security finding)
  - TEST-23 (the arbitrator names the hardened option itself)

  Each one lets a security decision pass with no person involved.
- **sre / devops:**
  - Debate children log to `agent_state/phases/{{PHASE}}/execution.jsonl`, but the moderator's spawn prompt (moderator:113-117) passes no phase. In `/plan` or `/discuss` that directory may not exist yet.
  - DL-01's result depends on where the repo is checked out (TEST-32), so `tests/run-all.sh` gives different results in a worktree and in the main checkout.
- **ai_engineer:**
  - "Fix each problem it lists" invites re-scoring to fit the verdict (TEST-24).
  - Promote mode can rewrite the primary verdict and leave no trace (TEST-34).
  - The second opinion's model is self-reported (TEST-13).
  - The randomized presentation order is never exercised (TEST-30).
  - T-007's position check has no power to detect bias (TEST-27).
- **senior_dev:** `make_debate.py:30` writes files through a lambda that never closes them. It's harmless in CPython, but sloppy for a shared fixture.
