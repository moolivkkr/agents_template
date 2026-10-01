# AI engineer hat: debate agents (run 2026-09-30-debate-2, commit 95fb871)

Targets: `debate_moderator`, `debate_researcher`, `debate_advocate`, `debate_arbitrator`, each read in
full. Findings: 2 HIGH, 16 MEDIUM, 14 LOW (`ai_engineer.json`).

**What I checked them against.** I compared behaviour claims with
`code.claude.com/docs/en/sub-agents` and `code.claude.com/docs/en/tools-reference`, plus three pages
on `platform.claude.com`: `prompting-claude-opus-5-5`, `prompting-claude-opus-5` and
`build-with-claude/effort`. I fetched all of them this session. I reproduced the runtime claims in a
scratch directory, using `tests/lib/make_debate.py`, `.claude/hooks/debate-status.py` and
`.claude/hooks/remember.sh`.

**The six defect classes from 2026-09-30 are fixed in the agent text:**
- children no longer default to the background: "pass `false` where offered", with the fork-mode
  case written out
- requesters return `NEEDS_DECISION` instead of waiting
- limits are counted, not timed in minutes
- advocates give no scores
- the arbitrator no longer falls back to "the first option"
- searches take the year from `date +%Y`

What remains is mostly where these prompts meet `debate-status.py`. That script recomputes and
enforces the verdict, but the agents read only part of its output, and one prompt lets them satisfy
it the wrong way.

## Verdict: top five

1. **The moderator can return COMPLETE for a debate the gate will block, and re-running it doesn't
   help (AI-01, HIGH).**
   - Step 10 keys its answer on `status` and `problems`. Several gate failures appear only in `gate`:
     an unpromoted verdict, a second opinion in the wrong order, a stale `request_sha`. I reproduced
     all three: `problems: []`, `--check` exits 2.
   - Step 1 then treats such a verdict as "already resolved and valid", so the gate dispatcher's
     re-run returns the same answer. Under `/autonomous` the run stalls.
   - The arbitrator's own self-check has the same blind spot (AI-03).
2. **The rubric is chosen by the agent that wants the decision, and nobody checks it (AI-02, HIGH).**
   - Every security protection keys on `domain: security`: the security rubric, the hardened default,
     the person gate and the security tag on gate messages.
   - The moderator checks only that the domain is one of the six names.
   - So a rate-limit or token decision labelled `architecture` skips all of them under `/autonomous`.
3. **The arbitrator can satisfy the score recomputation by editing scores (AI-04, AI-05, AI-06).**
   - Two rules contradict each other: "The BRD decides between close options" against "the winner is
     the highest total".
   - The prompt calls a tie "equal at one decimal place", but the checker requires the totals to be
     within 0.05. With 7.25 against 7.15, the prompt sees a tie and the checker rejects it.
   - Step 7 then says "fix each problem it lists", with no rule against moving scores. I reproduced a
     rejected verdict that passed `--check` after one score moved from 6 to 7.
4. **The second opinion can see the first judgment through the protocol's own reader (AI-07).**
   - Second-opinion mode lists the verdict files it mustn't open, but not `debate-status.py`.
   - The protocol tells every agent to read debates only through that script, and its `--json` and
     text output show the primary's winner, confidence, totals and gap (reproduced).
   - A second opinion is also accepted from a non-Fable model: it goes to review, not the gate
     (AI-17, reproduced).
5. **Re-spawns and limits aren't handled to the end.**
   - **Re-spawned agents start over (AI-10, AI-11).** A moderator re-spawned after a progress note
     redoes the whole debate. A re-spawned arbitrator records a second active `D-NNN` for the same
     verdict: `remember.sh decide` doesn't deduplicate, and I reproduced two active entries.
   - **The concurrency arithmetic has no headroom (AI-13).** Four moderators at five agents each is
     exactly the default limit of 20. A moderator whose first spawns fail has no child to wait for,
     and a transient limit error on the Fable spawn becomes PARTIAL.
   - **Fork mode leaves the moderator no correct move (AI-14, [unverified]).** It is told never to end
     its turn early, but in fork mode a subagent gets its children's results only after its turn ends.

## Missing entirely

| What's missing | Where I looked |
|---|---|
| A resume rule for a re-spawned moderator: reuse the briefs, the presentation order and an already-promoted verdict | `debate_moderator.md` steps 1–10; `child-returns.md` (it passes "Files already written" but nobody acts on it) |
| A dedupe on a ledger link, so the same verdict can't be promoted twice | `remember.sh` decide (lines 71–100); arbitrator step 8 |
| A recommended default in the moderator's `NEEDS_INPUT`, which `child-returns.md` line 45 tells the parent to use under `--auto` | moderator steps 1 and 4 |
| A domain-fit check | moderator step 1; `request_problems()` in `debate-status.py` |
| A rule that scores are frozen once written | arbitrator steps 4–7 |
| A fork-mode setting (`CLAUDE_CODE_FORK_SUBAGENT`), or a written procedure for fork mode | `.claude/settings.json` sets only the spawn-depth variable; moderator step 3 |
| Separate `BLOCKED` first lines for request problems and for verdict or spawn problems, so the parent can route each | moderator steps 1 and 10; `child-returns.md` lines 69–70 |
| An eval that measures position bias on a close call | T-007's R3 tests order on a lopsided case, and R5 doesn't compare the second opinion with the first |
| A way for existing projects to get the spawn-depth setting | `new-project.sh` line 41 and `autonomous.md` line 126 copy `settings.json` only when none exists |

## For other hats

- **devops**
  - **`jq` is an unstated dependency.** The moderator's and arbitrator's commands
    (`debate-status.py --json | jq …`) need it, and nothing installs or checks it.
  - **`install.sh` lines 141–143 copy the framework's `.claude/settings.json` into
    `~/.claude/settings.json` when the user has none.** That makes the project-relative hooks
    (`$CLAUDE_PROJECT_DIR/.claude/hooks/...`) and the depth cap global. (Security may care too.)
- **senior_dev**
  - **One of the checker's messages is misleading.** `debate-status.py` lines 262–264 print "with no
    hardened-default or tie_break reason" even when a `tie_break` is present and only the 0.05
    window failed.
  - **`{{PHASE}}` placeholders in the core debate agents have no value for ad-hoc debates.**
- **sre**
  - **Parallel appends.** Up to four researchers or advocates append to `execution.jsonl` and
    `lessons.md` at the same time, with no locking.
- **architect**
  - **The moderator is the only place debate stages are sequenced, and it has no persisted state.**
    The transcript is written last, in step 9, so nothing survives a re-spawn. Consider writing the
    transcript as the debate goes and treating it as the state file.
- **tester**
  - **T-007 needs two more checks:** a reversed-order close call (AI-18), and an eval run that isn't
    interactive (AI-19).
