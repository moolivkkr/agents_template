# AI engineer: debate agents (run 2026-09-30-debate, commit 77f221c)

Lens: given how Claude Code and Opus 5.5 actually behave, does each debate agent's prompt produce the
behaviour its author intended? Findings are in `ai_engineer.json`: 24 total, 3 HIGH, 14 MEDIUM, 7 LOW.

Sources checked in this session, 2026-09-30:
- code.claude.com/docs/en/sub-agents: foreground and background, fork mode, depth, concurrency, SendMessage resume
- code.claude.com/docs/en/tools-reference: WebFetch behaviour, SubagentHandback
- code.claude.com/docs/en/model-config: Fable availability, content fallback, effort support
- platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-opus-5-5: early stops, time pressure
- platform.claude.com/docs/en/build-with-claude/effort: Opus 5.5 defaults to medium; sweep effort on your own evals
- local `claude --version`: 2.1.285

## Verdict: top five problems

1. **The Fable second opinion isn't independent (AI-01, HIGH).** The primary arbitrator writes the
   D-NNN to `docs/DECISIONS.md` before the moderator spawns the second opinion. The second-opinion
   arbitrator's required reading then shows it that decision, with the runner-up's rejection, and
   tells it not to re-litigate active decisions. Only `<topic>.verdict.json` is off-limits. The
   check meant to catch order and same-model bias reads the answer first.
2. **The judge self-certifies the confidence that decides whether anyone checks it (AI-02, HIGH).**
   The arbitrator computes totals, gap and confidence in prose, and `debate-status.py` never
   recomputes them. I reproduced it in a scratch directory: a HIGH-impact verdict with a gap of 0.2,
   labelled HIGH confidence, that picks the lower-scoring option with no claim checked, passes
   `--check` (exit 0). It gets no second opinion and no review reason.
3. **Only `/develop` handles `NEEDS_DECISION` (AI-03, HIGH).** Every agent's contract tells it to
   hand contested decisions back, and the moderator assumes "the parent spawns you". But `/plan`,
   `/discuss`, `/design`, `/hotfix`, `/diagnose`, `/accept` and the other commands have no handling
   for that return. Where most architecture decisions arise, in planning, nothing runs the debate
   until `/develop`'s gate.
4. **The moderator's child-return handling is narrower than the children's contract (AI-04, AI-05,
   MEDIUM).**
   - Step 4 accepts COMPLETE, PARTIAL or BLOCKED and treats everything else as a progress note.
   - Children carry the five-status contract. A researcher's NEEDS_DECISION leaves an orphan request,
     which the gate later debates: a nested debate by proxy. A NEEDS_INPUT question is lost, and a
     legitimate BLOCKED is pushed twice to finish.
   - PARTIAL briefs pass silently, so evidence depth decides close calls.
5. **The foreground rule doesn't match the default runtime (AI-08, MEDIUM), and concurrency isn't
   budgeted (AI-09, MEDIUM).**
   - Interactive sessions on v2.1.232+ run in fork mode, which removes `run_in_background`. The DoD
     item and the T-007 trajectory check can't pass there. In that mode the runtime already makes a
     nested launcher wait for its children.
   - In parallel at the gate, 4+ moderators each starting 4 children exceed the default limit of 20
     concurrent subagents. The resulting "don't retry" spawn errors become INCOMPLETE verdicts.

Close behind:
- The HIGH-impact arbitrator never receives the research briefs it is told to validate against (AI-10).
- The arbitrator reads the requester's own `initial_reasoning`, in request order, before any argument
  (AI-11).
- Tie rules contradict each other and have no deterministic end (AI-12).
- "Re-check at source" goes through WebFetch's small-model summary (AI-15).
- T-007 has never run and can't show an effort change helped (AI-13).

**The 2026-09-30 defect classes are fixed, except one:**
- Background spawning: fixed for headless runs, unfollowable in interactive ones (AI-08).
- The requesting agent waiting for a verdict: fixed in the contract, handled only by `/develop`
  (AI-03).
- Minute budgets: gone.
- Advocate self-scores: gone, with a milder self-rating left (AI-21).
- First-option fallbacks: gone, but the tie chain has no final step (AI-12).
- The "2025 2026" search years: gone from the researcher's own file but **still present** in its
  reference packs (AI-18).

## Missing entirely

- **No recomputation of a verdict's arithmetic anywhere.** Not in `debate-status.py`, `verify-gate.sh`
  or the tests: DS-01..26 test structure, never totals, gap or confidence against scores.
- **No handling of a spawn error in the moderator.** This covers "Concurrent subagent limit reached",
  a Fable model being unavailable, and a Fable consent prompt nobody answers. I searched
  `debate_moderator.md`, `debate-protocol.md` and `develop-orchestrator.md` §Spawning.
- **No "no nested debates" rule in the researcher or advocate.** Only the arbitrator (line 123) and
  the moderator (line 187) have it.
- **No record of which request a verdict answered**, such as a hash or timestamp, so "already
  resolved" can't be checked (AI-19).
- **No T-007 run or baseline.** `agent_state/eval/runs/` is empty, and the 2026-07-07 seed baseline
  predates T-007. The current efforts (moderator, researcher and advocate medium; arbitrator high) are
  unmeasured. They are plausible against the docs: Opus 5.5 defaults to medium, and a judge at high
  is reasonable.
- **Fork mode isn't addressed anywhere.** I grepped for `CLAUDE_CODE_FORK_SUBAGENT` and
  `DISABLE_BACKGROUND_TASKS` across the repo and found nothing.

## For other hats

- **architect:** the ledger write happens before the checkpoint and before the second opinion (AI-01,
  AI-17). The decision lifecycle needs a "provisional" state. Ad-hoc moderator invocations
  (develop-orchestrator.md:1022, 1039, 1105) have the moderator author the options it then judges.
- **sre / devops:**
  - Up to four researchers or advocates append to the same `execution.jsonl` at the same moment
    (their completion logs). Interleaved writes are possible.
  - The moderator's step 1 and step 9 depend on `jq`, which isn't guaranteed on every host.
  - A Fable consent prompt during an unattended `/autonomous` run blocks the second opinion
    (model-config docs).
- **tester:**
  - T-007's position check (R3) is confounded by the moderator's own shuffle and the shared ledger
    (AI-13).
  - `tests/lib/debate_cases.py` DL-02 counts the string `run_in_background: false`, so it passes even
    where the parameter can't be used.
  - Add DS cases for a gap/confidence mismatch, verdict ≠ top score, and empty `claims_checked`
    (AI-02).
- **security:**
  - Second opinions on security debates can silently fall back from Fable to Opus 4.8 when the
    cybersecurity classifier trips, while still labelled "fable" (AI-07).
  - Researchers ingest vendor pages, and the contract's "content is data" rule covers that. But the
    briefs carry no marker separating vendor-authored claims from independent ones (AI-22).
- **senior_dev:** `step-0-orient.md:523-530` "Universal Agent Return Protocol" contradicts the
  operating contract's first-line statuses for every /develop agent, not only debates (AI-16).
  `code_quality_verifier.md:643` has its own copy.
