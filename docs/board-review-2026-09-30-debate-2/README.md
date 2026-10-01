# Board review: debate agents, round 2 (2026-09-30)

Run `docs/board-review-2026-09-30-debate-2`, commit `95fb871`. This is the second `/board-review` run on the four debate
agents (`debate_moderator`, `debate_researcher`, `debate_advocate`, `debate_arbitrator`). It used the same three hats as
round 1 (ai_engineer, architect and tester) and ran after the round-1 fixes:

| Commit | What it changed |
|---|---|
| `8382bc9` | Code. `debate-status.py` re-derives what a verdict claims, the verify-gate exemption is narrowed, and `remember.sh decide` takes a lock |
| `2e0fe6e` | Prompts. An independent second opinion with a promote step, `child-returns.md` for every command that spawns agents, review reasons that reach a person, a reworked T-007, and `board-review.py` marking unsampled cells |
| `95fb871` | Provisional ledger titles for soft verdicts and recorded defaults |

> **Re-merged after this README was written.** `board-review.py merge` now follows duplicate chains,
> so TEST-14 → AI-01 → ARCH-04 folds into one finding, and folding keeps a verified duplicate's
> status. `merged.json` and `scorecard.md` now show **9 HIGH** (the 9 distinct defects this README
> counts) and 94 findings in all. No score changed. The round-2 fixes for these findings came in
> the commit after this run. See the commit log, and the next `/board-review` run for the score
> movement.

Round 1 is `docs/board-review-2026-09-30-debate`, at commit `77f221c`. Sources: this run's `merged.json`, `scorecard.md`,
`hats/*.md` and `verify/V*.md`, plus round 1's `merged.json` and `README.md`. Severities and scores are the ones in
`merged.json`. Nothing here re-rates them. "Round-1 RC*n*" means a root cause from round 1's README; "RC*n*" alone means
one from this run.

## 1. Summary

The hats filed 101 findings (round 1: 88). Blind verification on `claude-fable-5-1` checked 37 of them: all 15 HIGH, plus
a sample of 22 MEDIUM and LOW. It refuted none, moved 14 severities and folded 6 duplicates. That leaves 95 findings:
0 CRITICAL, 10 HIGH, 60 MEDIUM and 25 LOW. One HIGH defect is counted twice (TEST-14 and ARCH-04, see section 4), so
there are 9 distinct HIGH defects, down from 13.

**The holes round 1 reproduced are closed.** The hats and verifiers re-checked round 1's fixes, mostly by re-running its
scenarios against the real hooks:

- A FAIL sidecar logged under `agent_state/debates/../` now blocks (round-1 RC5).
- Each of these now blocks: a pending debate, an unpromoted verdict, a verdict naming an option the request doesn't
  have, a verdict with no debate files behind it, and a close HIGH-impact call with no second opinion. The gate now
  recomputes the primary verdict's totals, gap and confidence itself (round-1 RC1).
- A security second opinion that disagrees now waits for a person's `override.json` (round-1 RC2).
- `remember.sh decide` takes a lock (round-1 RC6), and a changed request makes its verdict stale (round-1 RC7).

**Most of what's left sits at the seam of round 1's own fix.** The code commit split `debate-status.py`'s per-topic
output into two lists:

- `problems`: the debate's files are broken.
- `gate`: the gate still blocks. Examples are a missing D-NNN, a missing or wrong-order second opinion, and a decision
  only a person can make.

The prompt commit taught the moderator and arbitrator to read only `problems`. As a result:

- the moderator returns COMPLETE for topics the gate blocks;
- a debate that stopped after its primary verdict has no way to resume;
- the arbitrator's mandated self-check fails on every first-time RESOLVED debate, because the transcript it requires is
  written later.

These form RC1, and three of the nine distinct HIGH defects sit there.

**The ledger no longer loses entries in a race, but it can't say which decision is in force (RC2).** "Promoted" means
that a D-NNN block links to this verdict's path, and that path is the same in every round. So the gate passes a flipped
verdict, a reversed entry, two active entries for one topic, and an override that never reached the ledger.

**Routes to a person still depend on fields an interested agent writes (RC3).** The requester picks `domain`, and every
security protection keys on it. One sentence of `withdrawn_reason` clears a pending security debate.

**Round 1's "the gate trusts the debate's own report" class is narrower, not gone (RC4).** The recomputation covers the
primary verdict's numbers. These are still taken at their word: a decisive claim marked `unverifiable`, an evidence gap,
the second opinion's own scores, and what the debate files contain.

**Both test suites are green while every verified HIGH holds.** `verify-gate.test.sh` passes 58/58 and `debate.test.sh`
passes 79/79, just as round 1's suites passed (53/53, 46/46). `tests/lib/make_debate.py` writes the transcript before the
verdict, an order no real debate produces, so the suite can't see RC1's ordering bug. T-007 still has no baseline, and as
written its R1 check can't pass on a correct run (RC8).

The scorecard, copied from `scorecard.md`. Each cell is the agent's worst finding under that hat after verification
(CRITICAL 1, HIGH 2, MEDIUM 3, LOW 4, none 5). `*` marks a cell whose worst finding is a MEDIUM or LOW that the
verifiers didn't sample, so it counts at the hat's severity.

| Agent | AI | Arch | Test | Avg |
|---|---|---|---|---|
| debate_moderator | 2 | 2 | 2 | 2.0 |
| debate_arbitrator | 3 | 2 | 2 | 2.33 |
| debate_advocate | 3* | 4* | 3 | 3.33 |
| debate_researcher | 3* | 4* | 3 | 3.33 |

How to read it:

- **Moderator.** It scores 2 under every hat. Each 2 is backed by verified HIGH findings, and those findings span RC1 to
  RC5. Its AI score rests on AI-02 alone, because AI-01 was folded into the architect hat's ARCH-04.
- **Arbitrator.**
  - Architect 2: ARCH-01 and ARCH-17 (RC1).
  - Tester 2: TEST-01 (RC4), TEST-06 (RC2) and TEST-14 (RC1).
  - AI 3: AI-03, a verified MEDIUM.
- **Advocate and researcher.**
  - Tester 3 is verified: TEST-10 and TEST-25 for both, plus TEST-22 for the advocate.
  - AI 3* comes from AI-09, and architect 4* from ARCH-28 (plus ARCH-29 and ARCH-30 for the researcher). None of these
    was sampled.
  - On verified findings alone, both agents score AI 4, Arch 5 and Test 3.

### Score movement

```
python3 .claude/hooks/board-review.py compare docs/board-review-2026-09-30-debate/merged.json docs/board-review-2026-09-30-debate-2/merged.json
```

Score movement: board-review-2026-09-30-debate -> board-review-2026-09-30-debate-2

| Agent | Before | After | Change |
|---|---|---|---|
| debate_moderator | 2.0 | 2.0 | 0.0 |
| debate_arbitrator | 2.0 | 2.33 | +0.33 |
| debate_advocate | 2.67 | 3.33 | +0.66 |
| debate_researcher | 2.67 | 3.33 | +0.66 |

Findings by severity: CRITICAL 0 -> 0, HIGH 13 -> 10, MEDIUM 54 -> 60, LOW 18 -> 25

Five cells moved, all of them up:

| Cell | Round 1 | Round 2 | Why |
|---|---|---|---|
| arbitrator, AI | 2 | 3 | Round 1's AI-01 (the second opinion read the primary's D-NNN) and AI-02 (a confidence label decided whether a second opinion ran) are fixed. The worst finding is now AI-03, a verified MEDIUM |
| advocate, Test | 2 | 3 | Round 1's TEST-10 (the verify-gate path exemption) is fixed. The worst findings are now TEST-10, TEST-22 and TEST-25, all verified MEDIUM |
| researcher, Test | 2 | 3 | The same reason, with TEST-10 and TEST-25 as the worst findings |
| advocate, Arch | 3 | 4* | Unsampled in both rounds: ARCH-13 (MEDIUM) in round 1, ARCH-28 (LOW) now |
| researcher, Arch | 3 | 4* | Unsampled in both rounds: ARCH-13, ARCH-22 and ARCH-23 in round 1; ARCH-28, ARCH-29 and ARCH-30 now |

- **Advocate and researcher.** Half of their +0.66 comes from cells nobody sampled in either run. On verified findings
  alone they move +0.33, from 3.67 to 4.0.
- **Moderator.** It didn't move, because each of its 2s is backed by new HIGH findings.
- **Severity counts.** HIGH falls from 13 to 10, which is 9 distinct defects. MEDIUM and LOW rise; the hats filed 13 more
  findings than in round 1.

## 2. Round-1 root causes: what's fixed and what persists

The hat checklists ask each hat to re-check the defect classes from the original 2026-09-30 reviews. Examples are
advocates' self-scores, minute budgets, a fallback that always picks option A, and debate requests written under a name
the gate never globbed. All three hats report those classes still fixed.

Round 1's twelve root causes aren't on the checklists, but the architect and tester hats re-ran several of round 1's
fixes. The table below rests on those re-runs, on the verifiers' reproductions, and on round-2 findings that hit the same
mechanism. Where a row or note says "my check", I read the code myself.

| Round 1 | Its HIGHs | Status at `95fb871` | Evidence this round | Continues as |
|---|---|---|---|---|
| RC1: the gate checks what a debate says about itself | 4 | Partly fixed | Tester: unpromoted verdicts, verdicts naming an unknown option and verdicts with no debate files behind them all block. Totals, gap and band are recomputed, and DS-19 blocks a close call with no second opinion. TEST-20's fixture shows that a request with a trailing comma is now reported as unreadable and blocks | RC4 (claim results, evidence gaps, second-opinion scores, file contents). RC3 (mis-marked and legacy files: TEST-18 and TEST-19, unverified) |
| RC2: outcomes that need a person have no machine signal | 3 | Fixed at the gate, but routes around it remain | V1's TEST-12 control: a security second opinion that disagrees blocks for a person (exit 2) | RC3 (domain, withdrawal). RC1: the moderator returns COMPLETE on that disagreement, so the requester is relaunched before the stop (ARCH-04) |
| RC3: the decision hand-back is wired into one command | 2 | Fixed for blocking requests | V1, on ARCH-02: `child-returns.md` applies to every spawn and relaunches the requester after any moderator COMPLETE | RC5: non-blocking requests from `/plan`, `/discuss` and `/design` (ARCH-03). ARCH-26: the text on the order of Wave 6 steps 0b and 0c still contradicts itself |
| RC4: the D-NNN is written before the second opinion runs | 2 | Fixed | No finding says the second opinion reads the ledger. Second-opinion mode lists the topic's DECISIONS entries among the files it must not open (AI-07's evidence) | RC1: the new promote stage has no resume path (ARCH-17) and fails its self-check (ARCH-01). TEST-35: promote mode can rewrite the verdict. RC9: other channels, mostly unverified |
| RC5: verify-gate exempts reports by path prefix | 1 | Fixed | Tester: a FAIL sidecar logged as `agent_state/debates/../` blocks | (none) |
| RC6: the ledger writer isn't safe for parallel debates | 1 | Fixed | Architect: `remember.sh decide` takes a lock | RC2: no topic key, and promotion is checked by a link path every round shares |
| RC7: a verdict isn't tied to the request it answered | 0 | Partly fixed | V2: a mis-copied `request_sha` reports the verdict as stale, and step 1 re-runs a stale debate | RC6: the second opinion, override, ledger link and briefs carry no round identity |
| RC8: non-blocking requests are enforced by prose alone | 0 | Fixed at the gate, which is too late | Every pending request blocks, and `default_taken` is checked (V1: `debate-status.py:471-473`) | RC5: the gate is the first place a planning-time request is dispatched, and nothing records that a blocking verdict was applied |
| RC9: the moderator's step 4 handles only a clean return | 0 | Partly fixed | V1, on ARCH-26: the four-moderator cap is in `child-returns.md:34-38` and `debate-protocol.md:214` | RC4: the evidence-gap cap is prose only (TEST-04). RC1: an arbitrator PARTIAL is misread as an evidence gap (ARCH-01). Unverified: AI-10, AI-13, AI-16 |
| RC10: a skill pack contradicts the moderator's own rule | 0 | Fixed for the moderator | The moderator's `skill_packs` are now `debate-protocol.md` and `child-returns.md` | Unverified ARCH-29: the researcher's `deep-research.md` pack conflicts with the researcher's contract |
| RC11: debate bookkeeping has no owner | 0 | Not fixed | Unverified ARCH-28 and AI-27: completion lines still have no single writer. No hat filed the circuit-breaker count, and `debate-status.py` still counts topics only by status (my check) | Outside the root causes (section 3) |
| RC12: tests and eval check fixed paths and phrases | 0 | Not fixed | V1 reproduced TEST-25 (T-007's R1 fails on a correct run) and TEST-22 (R7's regex misses "Score: 8 out of 10"). T-007 has no baseline | RC8 |

Tally:

| Status | Round-1 root causes |
|---|---|
| Fixed | RC4, RC5, RC6 (as round 1 described them); RC10 (for the moderator) |
| Fixed at the gate, with gaps around it | RC2, RC8 |
| Partly fixed | RC1, RC3, RC7, RC9 |
| Not fixed | RC11, RC12 |

No round-2 finding reports one of round 1's 13 HIGH defects in its round-1 form. Four unverified round-2 findings are
narrower cases of them, and all four are in RC3:

| Round-2 finding (unverified) | Narrower case of round 1's |
|---|---|
| TEST-19 | TEST-01 |
| TEST-18 | TEST-02 |
| TEST-23 | TEST-03 |
| TEST-20 | TEST-13 |

**Where this round's HIGH defects come from:**

| Origin | Distinct HIGH defects |
|---|---|
| The seam between round 1's code and prompt commits. The prompts read `problems`, the gate reads `gate`, and the steps run in an order the checker doesn't expect | TEST-14 (= ARCH-04 = AI-01), ARCH-17, ARCH-01 |
| A round-1 fix that works as designed, but the design is too weak. Promotion is checked by a link path every round shares | TEST-06 |
| Round-1 plan items implemented only in part (details below) | TEST-01, TEST-08 |
| Problems that existed before round 1's fixes and that the fixes didn't address (details below) | AI-02, ARCH-03, TEST-09 |

The two partial implementations:

- **TEST-01.** The claim re-check is required, but its result is never read.
- **TEST-08.** Round 1's plan (P1-1) asked that an override carry a D-NNN that links it. `debate-status.py:389-395`
  checks only the override's option and rationale (my check).

The three problems the fixes didn't address:

- **AI-02.** The requesting agent declares the domain itself.
- **ARCH-03.** Round 1's RC3 fix covered blocking requests only.
- **TEST-09.** Round 1 listed it as unverified TEST-30. The fix raised the minimum withdrawal reason from 10 to 20
  characters, which still lets one sentence through.

## 3. Root causes, ranked

Every verified finding is in exactly one root cause, except AI-25, which stands alone. That covers the 31 verified
entries in `merged.json` and the 6 verified findings folded into other entries.

**Ranking.** Causes are ordered by their verified HIGH count, then by verified MEDIUM count (folded findings included),
then by how far the failure reaches.

**Same cause, unverified.** Under each cause, this lists findings no verifier sampled. They keep the hat's severity, and
the grouping is mine, not a verifier's.

| # | Root cause | Verified (+ folded) | HIGH | Hats | Agents | Round-1 origin |
|---|---|---|---|---|---|---|
| RC1 | The prompts and `debate-status.py` disagree about when a debate is finished | 5 (+1) | 4 (3 distinct) | AI, Arch, Test | moderator, arbitrator | New: the seam between round 1's two commits |
| RC2 | The decision ledger can't say which decision is in force | 5 (+2) | 2 | AI, Arch, Test | arbitrator, moderator | Round-1 RC6, and RC1's promotion check |
| RC3 | Every route to a person keys on a field an interested agent writes | 2 | 2 | AI, Test | moderator | Round-1 RC2 |
| RC4 | The gate still takes a verdict's evidence fields at their word | 6 | 1 | Test | all four | Round-1 RC1 |
| RC5 | A verdict is checked to exist, not to have been applied | 3 | 1 | Arch | moderator | Round-1 RC3 and RC8 |
| RC6 | Only the verdict carries a round identity | 2 (+1) | 0 | Arch, Test | moderator, arbitrator | Round-1 RC7 |
| RC7 | The settings a debate relies on reach only new projects, or exist only in prose | 1 (+1) | 0 | Arch | moderator | The depth part wasn't raised in round 1; the concurrency part is round-1 RC9 |
| RC8 | The eval and the lints can't measure the debate agents | 5 (+1) | 0 | AI, Test | all four | Round-1 RC12 |
| RC9 | The judge's independence rests on instructions | 1 | 0 | AI | moderator, arbitrator | Round-1 RC4, through other channels |

RC1's HIGH count includes ARCH-04. ARCH-04 itself wasn't sampled, but it carries the verified AI-01 folded into it, and
it is the same defect as TEST-14.

### RC1: The prompts and `debate-status.py` disagree about when a debate is finished

**What's wrong.** `debate-status.py` reports three things for each topic: `status`, `problems` and `gate`.

- **Round 1's code commit** put everything that still blocks the gate, without making the files invalid, into `gate`.
- **Round 1's prompt commit** keyed the moderator's step 10 table and the arbitrator's step 7 self-check on `problems`
  alone.

V2 and V1 reproduced what follows:

| State | `status` | `problems` | `gate` | `--check` | Moderator returns |
|---|---|---|---|---|---|
| Verdict never promoted | resolved | empty | no D-NNN links the verdict | exit 2 | COMPLETE |
| Second opinion read the options in the same order as the primary | resolved | empty | didn't read the reverse order | exit 2 | COMPLETE |
| The arbitrator mis-copied `request_sha` | stale | empty | answers an earlier version of the request | exit 2 | Not a dead end: step 1 re-runs a stale debate on the next dispatch (V2) |
| Transcript not yet written, which is the moment the arbitrator runs its check | invalid | missing `<topic>.transcript.md` | (n/a) | (n/a) | (n/a) |

Five defects follow from this:

- **COMPLETE for a topic the gate blocks** (TEST-14, and ARCH-04 with AI-01 folded in). The parent relaunches the
  requester and moves on. When a security second opinion disagrees, the requester is relaunched on a verdict a person
  still has to decide. The stop that `/autonomous` promises comes only at the Wave 6 gate, after the code is built
  (ARCH-04).
- **No way to resume** (ARCH-17).
  - Step 1 returns a verdict that's valid and current "as is", and Wave 6 0c dispatches only pending topics.
  - So a debate that stopped after its primary verdict never gets its second opinion or its promotion. One way that
    happens is Fable being unavailable, a case the moderator itself handles by returning PARTIAL.
  - Under `/autonomous`, a non-security topic in this state is force-gated after three cycles (`autonomous.md:342`), and
    its D-NNN is never written.
- **The arbitrator's self-check runs too early** (ARCH-01).
  - The checker requires a transcript for every RESOLVED verdict. The moderator writes it in step 9, after the
    arbitrator (step 6), the second opinion (step 7) and promote (step 8).
  - So the self-check fails on every first-time RESOLVED debate, and again in promote mode.
  - The arbitrator then either writes the moderator's file or returns PARTIAL, which the moderator's step 4 table treats
    as an evidence gap.
- **A wrong REQUEST_SHA looks cleaner than a right one** (AI-03). A stale verdict empties `problems`, while a correct one
  still lists the transcript not yet written. Nothing re-checks after step 8.
- **One more disagreement** (ARCH-11, narrowed). When an advocate's argument file is absent or empty at HIGH impact, the
  arbitrator's rule says RESOLVED, capped at MEDIUM, and the checker says invalid.

V2 narrowed AI-01 on two points:

- **A stale verdict isn't a dead end.** Step 1 re-runs it.
- **The moderator can see the reason.** The `jq` in step 10 prints the whole topic, `gate` included. The defect is the
  rule that ignores what it prints.

**Findings.** TEST-14 (HIGH), ARCH-04 (HIGH, with AI-01 folded in), ARCH-17 (HIGH), ARCH-01 (HIGH), AI-03 (MEDIUM),
ARCH-11 (MEDIUM, narrowed). TEST-14, ARCH-04 and AI-01 are the same defect, found by all three hats.

**Agents.** Moderator, arbitrator.

**Fix.**

1. **Compute what's left.** `debate-status.py` gives each topic one field naming the remaining step, for example `next`:
   `promote`, `second_opinion`, `transcript`, `rerun`, `person` or `none`.
   - Moderator step 10 returns COMPLETE only when `status` is resolved and `gate` is empty.
   - Any gate reason makes it return PARTIAL with that reason. For a security reason, the line says a person decides.
   - Add that row to `child-returns.md`, so the security stop comes before the relaunch.
2. **Add a resume path.**
   - Moderator step 1: when `gate` lists a missing second opinion or promotion, resume at step 7 or step 8.
   - Wave 6 0c dispatches every topic with a non-empty `gate`, not only pending ones.
   - When Fable stays unavailable, the architect hat proposes recording the verdict under a
     `[provisional: no second opinion]` title. That is a policy choice for the user.
3. **Fix the order.** Either the moderator writes a transcript skeleton (the children, their first lines and the
   presentation order) before step 6 and appends to it afterwards, or `debate-status.py` gets a `--stage verdict` flag.
   The arbitrator checks `status` and `problems` before step 8, and `gate` after it.
4. **ARCH-11: pick one contract.** Either the arbitrator writes INCOMPLETE when a required argument is missing, or the
   checker accepts a gap that the transcript records.
5. **Test it.** `make_debate.py` writes files in the order the agents do, and a test runs the prompts' own `jq` commands
   at each stage.

**Same cause, unverified.**

- AI-04, AI-05, AI-06 and TEST-24 (the score-editing group):
  - The arbitrator's tie rule ("equal at one decimal place") disagrees with the checker's 0.05 window.
  - Its "the BRD decides close calls" rule disagrees with the checker's highest-total rule.
  - Step 7's "fix each problem it lists" invites moving a score. The AI hat reproduced a rejected verdict that passed
    after one score moved from 6 to 7.
- AI-10: a re-spawned moderator re-runs the whole debate.
- AI-15: every cause of BLOCKED shares one first line, so the parent sends a verdict problem back to the requester.
- AI-16: there's no row for a child that returns COMPLETE but wrote its file to the wrong path.
- ARCH-12: `/pause` and `/health` each define an "open" debate from a different set of statuses.

### RC2: The decision ledger can't say which decision is in force

**What's wrong.** Every session reads `docs/DECISIONS.md` as settled, through the SessionStart hook and Required
Reading 0b. Round 1 fixed the write race. It also made "promoted" mean that a `### D-NNN` block's link line names the
verdict's path. Three problems remain:

- The link path is the same in every round.
- `promoted()` ignores the block's status and its decision text (`debate-status.py:306-311`).
- `remember.sh decide` has no topic key, so "one active decision per topic" depends on every writer remembering
  `--reverses`.

V1 ran the full gate on each ledger state:

| Ledger state | Gate |
|---|---|
| Verdict re-run to option B, but D-001 still records option A (TEST-06) | PASS |
| D-001 and D-002 both active for one topic (TEST-06) | PASS |
| D-001's status is `reversed` (TEST-07) | PASS |
| `override.json` written, with the arbitrator's choice still active in the ledger (TEST-08) | PASS |
| Control: verdict never promoted | BLOCK |

V2 added one more case. Two `remember.sh decide` calls with the same `--link` record D-001 and D-002, both active, and
`promoted()` is true for either one (AI-11).

Related gaps, all verified:

- **A confirming re-debate adds a second active entry** (AI-29, narrowed). This happens when a re-debate upholds a
  decision recorded under another topic, because the moderator passes `PRIOR DECISION` only for a stale verdict on the
  same topic. V2: an arbitrator that rediscovers the old entry would reverse it if it overturns it. Nothing covers the
  case where it confirms it.
- **Step 4c can't tell which defaults already have a D-NNN** (ARCH-33). This post-gate step records provisional entries
  for defaults. A re-run of 4c duplicates them, and a skipped 4c leaves none.
- **A contested verdict gets a clean title** (ARCH-24). A HIGH-impact verdict the second opinion disagreed with reads as
  settled, although later sessions see headings, not rationales.

V1 narrowed what TEST-07 costs. A block becomes `reversed` only through `--reverses`, which writes a newer active entry
at the same time, so the ledger stays coherent. What's lost is the signal that the topic should be re-run.

**Findings.**

- TEST-06 (HIGH, with TEST-07 folded in) and TEST-08 (HIGH).
- AI-29 (MEDIUM, narrowed), ARCH-24 (MEDIUM) and ARCH-33 (MEDIUM).
- AI-11 (MEDIUM, verified), folded into ARCH-07, which wasn't sampled.

**Agents.** Arbitrator, moderator.

**Fix.**

1. **Give the ledger a topic key.** `remember.sh decide --key <topic>` supersedes the active entry with that key, the way
   `add` uses `(subject, relation)` for facts. The arbitrator, the promote step, step 4c and `adr_agent` all pass the
   key. `decide` refuses a second active entry with the same `--link` (AI-11).
2. **Tighten the promotion check.** `promoted()` requires exactly one active block for the topic. It must equal the
   verdict's `decision_id`, and its decision line must name the `verdict_label`. Putting the verdict's `request_sha` in
   the link line ties the entry to its round (see RC6).
3. **Overrides reach the ledger.** An overridden topic requires an active block that links the override and reverses
   the verdict's D-NNN (TEST-08).
4. **Pass prior decisions on.** Whenever step 1 finds an earlier D-NNN on the decision, the moderator passes
   `PRIOR DECISION`, including when it was filed under another topic, and including to the promote step (AI-29;
   unverified ARCH-06).
5. **Make titles and defaults honest.**
   - Step 8's title rule adds `[provisional: second opinion disagrees]` (ARCH-24).
   - Step 4c writes each returned D-NNN back into its `unresolved.json` entry, skips entries that already have one, and
     runs before `gate.passed` (ARCH-33).

**Same cause, unverified.**

- ARCH-07: the missing topic key (AI-11 folded in).
- ARCH-20: restates TEST-06 and TEST-07.
- ARCH-06: the promote step isn't told the prior D-NNN.
- TEST-17: the provisional marker isn't checked.
- ARCH-22: `/worklog` shows an overridden debate as the arbitrator's choice.
- ARCH-19: a reversal doesn't flag the earlier phase's code.

### RC3: Every route to a person keys on a field an interested agent writes

**What's wrong.** Round 1 added a person gate for security debates, and V1's control shows that it fires. But fields
that the requesting or judging agent writes can route around it:

- **`domain`** (AI-02).
  - The requester chooses it, and `debate-status.py` checks only that it's one of six names.
  - The security rubric, the hardened-default rule, the person gate and the "security debate" tag all key on it.
  - So a rate-limit or session-TTL request labelled `architecture` gets none of them, and under `/autonomous` no person
    sees it.
  - V2 found this worse than the hat filed it. An arbitrator that notices the mislabel can't score on the security
    rubric, because the checker rejects a rubric that doesn't match the request's domain (DS-15). Nothing tells the
    arbitrator to return BLOCKED instead.
- **`withdrawn_reason`** (TEST-09).
  - One sentence (V1 used 39 characters) clears a pending security request.
  - No `override.json` and no `security_acknowledged` entry are needed.
  - The topic drops off the review list, so neither the checkpoint nor the `/autonomous` report sees it. The full gate
    passed.
  - Three places in the framework tell agents to withdraw requests.

**Findings.** AI-02 (HIGH), TEST-09 (HIGH).

**Agents.** Moderator, in both findings. The arbitrator is affected through the rubric.

**Fix.**

1. **Check that the domain fits the request.** Moderator step 1 checks the decision, context and option labels against
   the protocol's security list: auth, tokens, crypto, PII, CORS/CSRF, rate limits and tenant isolation. If `domain`
   isn't `security`, it returns `BLOCKED <topic>: request: domain should be security (<term>)`.
   - `request_problems` reports the same mismatch as a gate reason.
   - The arbitrator's rules say to return BLOCKED on a mislabelled domain.
2. **Make withdrawals visible.** Every withdrawn topic goes on the review list. A security or blocking withdrawal needs a
   D-NNN or an override. Otherwise it counts as a security finding, which a forced gate must acknowledge.
3. **Apply the same rule to the unverified routes below.** Decide whether a debate is about security from the request's
   content, not from a field the debate writes.

**Same cause, unverified.** The hats reproduced six of these in scratch runs (TEST-23 comes from reading the code), but
no verifier sampled any of them:

- TEST-20: a security request with invalid JSON counts as a non-security finding, so `/autonomous` can force past it.
- TEST-19: a mis-marked request with a non-standard file name is ignored.
- TEST-18: legacy file shapes skip every v2 check, even on a HIGH-impact security topic.
- TEST-23: the arbitrator names the hardened option itself.
- TEST-13 and AI-17: a same-model second opinion goes to the review list, not the gate.
- ARCH-14: an `unresolved.json` entry recorded the way `child-returns.md` describes carries no domain, so the
  hardened-default rule is skipped.

### RC4: The gate still takes a verdict's evidence fields at their word

**What's wrong.** Round 1's recomputation covers the primary verdict's totals, gap and confidence band. The fields around
those numbers are still self-reported. V1 ran the full gate on the first five cases; the sixth holds as cited:

| What's trusted | Case | Gate | Finding |
|---|---|---|---|
| The result of the decisive claim's re-check | The claim is `unverifiable` at HIGH impact and HIGH confidence. Nothing caps the confidence, so no second opinion runs | PASS | TEST-01 (HIGH) |
| Evidence gaps | `EVIDENCE INCOMPLETE` in the transcript, with a HIGH-impact, HIGH-confidence verdict | PASS | TEST-04 |
| The second opinion's verdict | Its scores are A 9 and B 3 but its verdict is B, on a security topic, and it counts as agreeing. With verdict A, it blocks for a person | PASS | TEST-12 |
| That the debate files exist | Every `.md` file contains just `x\n` | PASS | TEST-10 |
| What an argument says | An argument contains a self-score table | PASS | TEST-22 |
| That the promoted verdict is the primary's | Promote mode can rewrite the verdict toward the second opinion, and the result validates | (not run) | TEST-35 |

TEST-01 matters most. HIGH confidence is what exempts a HIGH-impact call from the Fable second opinion. So the
independent check is skipped exactly when the decisive evidence is weakest. The arbitrator's own prompt caps confidence
at MEDIUM in this case (`debate_arbitrator.md:134-135`), but the checker doesn't.

**Findings.**

- TEST-01 (HIGH).
- TEST-04, TEST-10, TEST-12, TEST-22 and TEST-35 (MEDIUM). Four of them need an agent to break an explicit instruction
  or fabricate files on purpose. For TEST-12, V1 noted that whether such a file is a real disagreement is open to
  interpretation.

**Agents.**

- Arbitrator and moderator: TEST-01, TEST-04.
- Arbitrator: TEST-12, TEST-35.
- All four agents: TEST-10.
- Advocate: TEST-22.

**Fix.** The changes go in `debate-status.py` unless noted.

1. **Weak decisive claims cap confidence.** A decisive claim whose result is `unverifiable` or `contradicted`, or whose
   `as_of` predates the option's current major version, caps the band at MEDIUM (TEST-01; unverified TEST-02).
2. **Evidence gaps are machine-readable.** The verdict carries an `evidence_gaps` array copied from the moderator's
   `EVIDENCE INCOMPLETE` lines. A non-empty array caps the band at MEDIUM (TEST-04).
3. **Check the second opinion's own numbers.** `second_problems` recomputes the second opinion's totals and treats its top
   total as its verdict, or reports a mismatch (TEST-12).
4. **Require a minimum structure** (TEST-10, TEST-22):
   - a brief cites at least one URL or repo path and has the template's headings;
   - an argument has the "Weaknesses I Acknowledge" heading and no score patterns (R7's patterns, plus "out of 10" and
     "Score:");
   - the transcript names a researcher for each option, and an advocate at HIGH impact, each with a first line;
   - `make_debate.py` writes realistic files.
5. **Freeze the primary verdict.** The moderator records the primary verdict's sha256 before promote, and the checker
   compares it, ignoring `decision_id` (TEST-35).

**Same cause, unverified.**

- TEST-02: a contradicted decisive claim with unchanged scores passes.
- TEST-03: a re-check whose source is "memory" passes.
- TEST-11: an INCOMPLETE verdict skips the artifact check.
- ARCH-25: the second-opinion format is defined twice, and neither version's extra fields are validated.

### RC5: A verdict is checked to exist, not to have been applied

**What's wrong.** Check (f) passes once a verdict and its D-NNN exist. Nothing checks that the code follows them.

- **Planning-time requests reach a debate only after the build** (ARCH-03).
  - Every agent's contract says to file a request with `blocking: false` and continue on its default.
  - When spec_writer, threat_model_agent or ux_designer does that in `/plan`, it returns COMPLETE. None of `/plan`,
    `/discuss` or `/design` checks `debate-status.py` for open requests.
  - `/develop` first dispatches the request at Wave 6 0c, after Waves 2 to 5 have built the default.
  - If the default lost, 0c relaunches a spec agent, which edits the spec, not the code. Wave 5v re-runs only on a stale
    `code_sha` and has no spec_impl_reconciler.
  - So the gate passes code that implements the losing option while the spec and the ledger record the winner.
  - Round 1's RC8 fix made every pending request block, but only at the gate.
- **Blocking requests have no record that the verdict was applied** (ARCH-02, narrowed).
  - V1 found the hat's "nobody relaunches the requester" overstated: `child-returns.md:67` relaunches the requester after
    any moderator COMPLETE, including in 0c.
  - What remains: 0c doesn't restate that rule or send the parent back to Wave 5v, and nothing records that the
    relaunch happened.
  - `default_taken`, which records what an agent built, exists only for non-blocking requests.
- **The verdict goes to an agent that isn't allowed to act on it** (ARCH-16). A test agent can raise a step 3 or step 4
  debate. When option A or B wins, the parent relaunches that test agent to implement it, which the test agent's own file
  forbids.

**Findings.** ARCH-03 (HIGH), ARCH-02 (MEDIUM, narrowed), ARCH-16 (MEDIUM).

**Agents.** Moderator.

**Fix.**

1. **Dispatch planning-time requests before the build** (ARCH-03).
   - `/plan`, `/discuss` and `/design` end by running `debate-status.py --phase N`, dispatching every pending request
     (blocking or not), and relaunching requesters whose default lost.
   - Wave 0 of `develop-orchestrator.md` refuses to start Wave 2 while any topic for the phase is pending or stale.
2. **Record that a blocking verdict was applied** (ARCH-02).
   - Blocking requests get `applied_by` and `applied_at` fields, which the parent sets when it relaunches the requester.
   - `debate-status.py` blocks the gate until they're set, as `default_taken` works for non-blocking requests.
   - After a verdict, 0c relaunches the owner and returns to Wave 5v with spec_impl_reconciler.
3. **Name who implements the verdict** (ARCH-16). Requests get an `implementer` field. `child-returns.md` relaunches the
   implementer first, then the requester to re-test.

**Same cause, unverified.**

- ARCH-13: defaults taken without a debate go to three different ledgers.
- ARCH-15: `/discuss` decides between options without the debate or the ledger.
- ARCH-18 and TEST-21: `/accept` runs no project-wide `debate-status.py --check`, so a request filed in a phase that no
  gate covers never blocks.
- ARCH-32: `/autonomous`'s text says to take architecture decisions on the default.

### RC6: Only the verdict carries a round identity

**What's wrong.** Round 1 bound the verdict to its request with `request_sha`, and V2 confirmed that a changed request
makes the verdict stale. The topic's other files carry no round identity, and the hash covers less than the verdict
depends on. The architect hat called this one root cause across its own findings.

- **An old second opinion passes a re-run** (TEST-05, narrowed). After the request changes, the re-run's Fable spawn
  fails, and the gate passes on the previous round's second opinion. V1: this happens only when the new random
  presentation order matches the old one, which is 1 in 2 with two options, 1 in 6 with three and 1 in 24 with four.
- **An override hides every later change** (ARCH-08). Once a topic is overridden, it never goes stale. So a later phase
  that raises it again with a new option gets no debate. V1: the gate passed.
- **The verdict outlives its requirements** (TEST-16). When an FR or NFR row, or a PROJECT_FACTS entry, that the verdict
  cited changes or is retired, the verdict and its D-NNN stay resolved.

**Findings.** ARCH-08 (MEDIUM), TEST-16 (MEDIUM). TEST-05 (MEDIUM, narrowed, verified) is folded into ARCH-05, which
wasn't sampled.

**Agents.** Moderator, arbitrator.

**Fix.**

1. **Tag every file with its round.** Add `request_sha` to the second-opinion and override formats.
   - A mismatch counts as stale, and `stale` is checked before `overridden`.
   - Before re-running a stale topic, the moderator moves `<topic>.*` (except the request) into an archive directory.
2. **Handle overridden topics in step 1.** A current override is the decision. A stale one is debated again, with
   `PRIOR DECISION` set to the override's D-NNN.
3. **Track what the verdict cited.** The verdict records the IDs and a text hash of the FR/NFR rows and facts it cites.
   `debate-status.py` marks it stale when that text changes, as `acceptance-map.py` does for tests.

**Same cause, unverified.**

- ARCH-05: the old round's files are judged against the new verdict (TEST-05 folded in).
- ARCH-09: a slug reused in a later phase overwrites the earlier phase's request.
- ARCH-23 and TEST-15: `context` isn't in the hash, while `initial_reasoning` is.

### RC7: The settings a debate relies on reach only new projects, or exist only in prose

**What's wrong.** Two things:

- **The moderator's guard can be switched off** (ARCH-21).
  - The moderator should be spawned by the parent session, not by a wave agent. The guard for that relies on the shipped
    `.claude/settings.json`, which caps spawn depth at 2. A moderator spawned one level too deep then has no Agent tool,
    and returns BLOCKED.
  - `new-project.sh` and `/autonomous` copy that file only when the project has none.
  - In a project that already had one, such as a codebase adopted with `/init --from-code`, the depth stays at the
    default of three layers. V1 checked that default against the sub-agents doc.
  - There, a wave agent can spawn a moderator that keeps its Agent tool, and the debate runs hidden from the parent's
    checkpoint and circuit breaker.
- **Wave 6's text still contradicts itself on order** (ARCH-26, narrowed). Step 0b says "run FIRST", and 0c says "run it
  before 0b". V1 found that the four-moderator cap the hat said was missing does exist, in `child-returns.md`, which
  applies to every spawn.

**Findings.** ARCH-21 (MEDIUM, verified), folded into AI-12, which wasn't sampled. ARCH-26 (LOW, narrowed).

**Agents.** Moderator.

**Fix.**

1. **Ship the depth setting to existing projects.**
   - `new-project.sh` and `/autonomous` Step 0 merge `env.CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH` into an existing
     `settings.json` with `jq`, and `/health` warns when it's missing.
   - The moderator also requires the parent-only `REQUEST:` header that `child-returns.md` step 3 adds, instead of
     inferring its caller from its tool list alone.
2. **Fix the Wave 6 text.** Delete "run FIRST" from 0b, and restate the four-moderator cap in 0c.

**Same cause, unverified.**

- AI-12: the depth finding itself (ARCH-21 folded in).
- AI-13: four moderators at five agents each is exactly the default limit of 20, with no headroom.
- AI-14: in fork mode the moderator gets its children's results only after its turn ends, yet it's told never to end
  its turn early.
- ARCH-34: waiting for children is still enforced only by prose, although a harness setting might make it
  deterministic.
- ARCH-31: spawns are written without `subagent_type`.

V2's documentation check bears on AI-14. The sub-agents page says that in interactive sessions, a subagent that launches
background subagents waits for their results before it finishes; under `-p` and the SDK it doesn't. Nobody tested
whether that returns the results to the moderator within its turn.

### RC8: The eval and the lints can't measure the debate agents

**What's wrong.** T-007, the debate eval, was reworked in round 1's prompt commit, but it has never been run, and the
seed baseline has no T-007 row. As written:

- **R1 can't pass on a correct run** (TEST-25). Each fixture copy's ledger starts at D-001. Merging the copies gives
  several `### D-001` blocks, so `debate-status.py --check` fails. V1 reproduced this. The same hard-coded D-001 in
  `make_debate.py` means no gate test covers two promoted debates in one phase.
- **The bias checks can't fail for the bias they name.**
  - The position check runs on a pair that a MUST requirement decides (AI-18, folded into TEST-28).
  - No request seeds `initial_reasoning` (TEST-29).
  - Nothing asserts that the shuffle ran (TEST-31, narrowed: two of the four debates are unpinned, so the shuffle does
    run).
- **Two agents are unmeasured** (AI-31). No rubric item moves with the quality of the researcher's or advocate's output,
  so an effort change on either is invisible.
- **One forbidden pattern contradicts fork mode** (AI-19, narrowed). It penalises correct interactive behaviour. But a
  scorer following `eval.md:68` can't see that parameter at all, so the penalty would land only if a scorer read the
  transcript instead.

**Findings.** TEST-25 (MEDIUM); AI-19, AI-31, TEST-29 and TEST-31 (LOW). AI-18 (LOW, verified) is folded into TEST-28,
which wasn't sampled.

**Agents.**

- All four: TEST-25.
- Moderator and arbitrator: TEST-29.
- Moderator: TEST-31, AI-19.
- Researcher and advocate: AI-31.

**Fix.**

1. **Make R1 passable** (TEST-25). Seed each fixture copy's `DECISIONS.md` with a distinct starting id, or score R1 per
   copy. Give `make_debate.py` a `--decision-id` option, and add a gate case with two promoted debates in one phase.
2. **Make the bias checks able to fail.**
   - Run a close call in both pinned orders and score agreement (TEST-28, AI-18).
   - Seed an `initial_reasoning` that argues for the wrong option (TEST-29).
   - Assert that not every `presentation_order` equals the request order (TEST-31).
   - Add a rubric item that moves with a brief's quality (AI-31).
   - Reword the forbidden pattern to "spawned without `run_in_background: false` where the Agent tool offers it" (AI-19).
3. **Record a baseline.** Run `/eval --baseline` three times with T-007 and take the median (unverified TEST-26).
4. **Fix the lints.** Assert the guarding sentences themselves, or their negations, not keywords (TEST-32). In DL-01, skip
   only `REPO/.claude/worktrees/` (TEST-33).

**Same cause, unverified.**

- TEST-26: there's no baseline.
- TEST-27: the trajectory can't be scored from what's logged.
- TEST-28: the position check itself (AI-18 folded in).
- TEST-30: R5 penalises a correct arbitrator that finds a clear gap.
- TEST-32: DL-07, DL-21 and DL-22 still pass after the sentences they guard are inverted.
- TEST-33: DL-01 skips every file whose path contains `/worktrees/`, so it passes vacuously here. In a non-worktree copy
  it fails on a harmless example.

### RC9: The judge's independence rests on instructions

**What's wrong.** Round 1's RC4 fix keeps the second opinion away from the ledger and the primary's verdict files, by
instruction. The hats name other channels those instructions don't close, but only one was sampled.

The arbitrator sees option labels A to D, which carry the request's order past the shuffle. The second opinion reads the
options in reverse order but keeps the same labels, so a preference for a label wouldn't show up as disagreement
(AI-22).

V2 narrowed this to a hardening suggestion:

- The bias it cites is documented: a preference for option-ID tokens (Zheng et al., ICLR 2024).
- But there's no wrong instruction and no demonstrated failure.
- T-007's two data requests already swap the labels along with the position.

**Findings.** AI-22 (LOW, narrowed).

**Agents.** Moderator, arbitrator.

**Fix.**

1. **Neutral aliases.** The moderator hands the arbitrator neutral option names and maps them back in the verdict.
2. **No status reads in second-opinion mode.** The second opinion doesn't run `debate-status.py` or list
   `agent_state/debates/`. It is validated by a mode that prints no verdict fields (AI-07).
3. **Keep the request out of the judge's view.** Add `phase` to the neutral view, or write `<topic>.neutral.json`, so the
   arbitrator never opens the request (ARCH-10).

**Same cause, unverified.**

- AI-07: `debate-status.py --json`, which the protocol names as the one way to read debates, prints the primary's
  winner, confidence and totals. The AI hat reproduced that output.
- ARCH-10: the arbitrator opens the request JSON to learn the phase, and sees `initial_reasoning` there.
- AI-32: the requester's opinion reaches the judge through the briefs and arguments.
- AI-21: advocates rate their own weaknesses.
- AI-30: vendor sources count as independent.

### Findings outside these root causes

**Verified (1).** AI-25 (LOW, narrowed): the step-0 Analysis Paralysis Guard exempts only the two audit agents. V2: it's a
poor fit for every agent that reads a lot, not just the debate agents, and it reaches a debate child only if someone
pastes it into the child's prompt. Fix: add the agents that judge and review to the exception list.

**Unverified (13).**

- **Bookkeeping (round-1 RC11, still open):**
  - ARCH-28 and AI-27: completion lines have no single writer, and children must infer the phase.
  - ARCH-27: the ownership table for the request file names one writer, although three roles edit it.
  - TEST-34: a later instance of the same role hides a failed debate child.
- **Instruction wording:**
  - AI-09: a capitalised STOP turns a retired component, which is decisive evidence, into an evidence gap.
  - AI-23: the arbitrator isn't told it may not file a debate request.
  - AI-24: copied Required Reading tells researchers to append to `DECISIONS.md`, which the guard denies.
  - AI-26: loading the protocol is optional.
  - AI-28: some DoD items only restate the process.
  - ARCH-29: the researcher's `deep-research.md` pack conflicts with its scope and output paths.
  - ARCH-30: a core template names stacks and models.
- **Evidence and defaults:**
  - AI-20: the small model produces the "quote" for a re-checked claim, so it can be paraphrased.
  - AI-08: the moderator's NEEDS_INPUT carries no recommended default, though the parent is told to use one under
    `--auto`. The hat calls this the 2026-09-30 "fallback picks option A" defect reappearing one level up.

## 4. What verification changed

**Refuted: none.** V1: "No finding was refuted outright: every runtime claim reproduced (the gate passed in each case
the hats said it did, and the unpromoted control blocked)." V2 refuted none of its ten. Two narrowings did refute part
of a claim: ARCH-26's "no cap" and ARCH-02's "nobody relaunches".

**Verifier statistics**, from `scorecard.md`:

| Verifier | Hats | Model | Total | Confirmed | Narrowed | Refuted | Unverifiable | Severity up | Severity down |
|---|---|---|---|---|---|---|---|---|---|
| V1 | architect, tester | claude-fable-5-1 | 27 | 22 | 5 | 0 | 0 | 4 | 8 |
| V2 | ai_engineer | claude-fable-5-1 | 10 | 5 | 5 | 0 | 0 | 1 | 1 |

The merge reported no warnings, so the "verifier changed nothing" check didn't fire. It reported no errors either:
every HIGH has a verdict.

**Severities moved: 14** (round 1: 13), 9 down and 5 up.

- **Downgrades.** V1 applied the same rule as in round 1. A failure that needs an agent to break an explicit instruction
  or fabricate files, or that has a workaround (ARCH-02), is MEDIUM. A failure confined to the eval is MEDIUM or LOW, and
  V2's one downgrade (AI-18) follows that rule too. Five of the tester hat's ten HIGHs went to MEDIUM.
- **Upgrades.** V1 raised ARCH-17 because it fails in normal use, ARCH-24 and ARCH-33 because they leave the ledger
  every session reads wrong, and TEST-35 because it belongs to the class the recomputation was meant to remove. V2
  raised AI-29, which leaves two active entries in front of every session.
- **V2** kept both ai_engineer HIGHs.

| Finding | Hat | Verifier | Why (from the verifier's note) |
|---|---|---|---|
| AI-18 | MEDIUM | LOW | A coverage gap in an eval fixture; no agent behaviour changes. A duplicate of TEST-28 |
| AI-29 | LOW | MEDIUM | Narrowed (see below). When it hits, two active entries are shown to every session |
| ARCH-02 | HIGH | MEDIUM | Narrowed (see below). A gap on the orphan-request path only, and the general relaunch rule is a workaround |
| ARCH-17 | MEDIUM | HIGH | Reproduced. A missing step in normal use: Fable being unavailable is a case the file itself handles |
| ARCH-24 | LOW | MEDIUM | The ledger heading is what later sessions read. No change to gate behaviour |
| ARCH-33 | LOW | MEDIUM | The consequence stays in the ledger (duplicate or missing provisional entries). It doesn't pass broken work |
| TEST-04 | HIGH | MEDIUM | Needs a child to fail and then an arbitrator to ignore a cap in its own prompt. The fix is a format addition |
| TEST-05 | HIGH | MEDIUM | Narrowed (see below). Folded into ARCH-05 |
| TEST-10 | HIGH | MEDIUM | The check catches the verdict-only case it was written for. Defeating it means fabricating five files on purpose |
| TEST-12 | HIGH | MEDIUM | Whether such a file is a real disagreement is open to interpretation. The asymmetry with how the primary is checked is certain |
| TEST-25 | HIGH | MEDIUM | Breaks the eval's validity, not the pipeline |
| TEST-29 | MEDIUM | LOW | A blind spot in the eval, with no effect on the pipeline |
| TEST-31 | MEDIUM | LOW | Narrowed (see below). The gate can't check a single debate's order |
| TEST-35 | LOW | MEDIUM | Needs the arbitrator to break an instruction, but it's the same "the gate trusts the verdict" class the recomputation was meant to remove |

**Narrowed: 10** (round 1: 6).

| Finding | What the verifier removed | What survives |
|---|---|---|
| AI-01 | That a stale verdict is a dead end (step 1 re-runs it), and that the moderator can't see the reason (step 10's `jq` prints `gate`) | COMPLETE for an unpromoted verdict or a second-opinion problem, with no retry. Kept at HIGH |
| AI-19 | That a scorer would penalise correct runs: `eval.md:68` scores from logs that don't record the Agent call's parameters | The forbidden pattern contradicts both the required step and the docs |
| AI-22 | That T-007 doesn't test it (two requests swap labels along with position), and that requesters list their favourite option first (unverified) | Labels carry the request's order past the shuffle. A hardening suggestion |
| AI-25 | That it's specific to debates, or enforced: it reaches children only if pasted into their prompts, and no hook counts reads | An incomplete exception list |
| AI-29 | The contradicting case: a careful arbitrator would reverse an entry it overturns | The confirming case: an upheld decision gets a second active entry |
| ARCH-02 | "Nobody relaunches the requester": `child-returns.md:67` relaunches it after any moderator COMPLETE | 0c doesn't restate the rule or return to Wave 5v, and nothing records the relaunch |
| ARCH-11 | That it fires broadly: it needs HIGH impact and an argument file that's absent or empty | In that case, the arbitrator's rule and the checker disagree |
| ARCH-26 | "There's no cap": the cap is in `child-returns.md:34-38` and `debate-protocol.md:214` | The text on the order of 0b and 0c contradicts itself |
| TEST-05 | That any re-run passes: it does only when the new random order repeats the old one (1/2, 1/6, 1/24) | Nothing ties a second opinion to its request |
| TEST-31 | That the shuffle never runs in the eval: two debates are unpinned | No check asserts anything about the shuffle |

**Duplicates folded: 6** (round 1: 3). This round, `board-review.py select` also shows each verifier every other finding
in brief: its id, hat, agents, file, line and the start of its problem. So verifiers can mark duplicates across hats and
across verifiers. Folding keeps the more severe rating and the union of the agents.

| Folded | Into | Marked by | Target sampled? | Shared defect |
|---|---|---|---|---|
| AI-01 (HIGH) | ARCH-04 | V2 | No | The moderator's step 10 reads `problems`, not `gate` |
| AI-11 (MEDIUM) | ARCH-07 | V2 | No | One active decision per topic depends on each writer passing `--reverses` |
| AI-18 (LOW) | TEST-28 | V2 | No | T-007's position check runs on a pair a MUST requirement decides |
| ARCH-21 (MEDIUM) | AI-12 | V1 | No | The depth cap is missing in projects that already had a `settings.json` |
| TEST-05 (MEDIUM) | ARCH-05 | V1 | No | The previous round's files are judged against the new verdict |
| TEST-07 (MEDIUM) | TEST-06 | V1 | Yes | `promoted()` matches on the link path and ignores the block's status |

**Two side effects of the merge.** Neither changes a score in this run; I checked each affected cell.

1. **A chain of duplicates wasn't fully folded.**
   - V1 marked TEST-14 as a duplicate of AI-01, and V2 marked AI-01 as a duplicate of ARCH-04.
   - `merge` folded AI-01 into ARCH-04 first. It then found TEST-14's target gone, and kept TEST-14
     (`board-review.py:309-316`).
   - So one defect appears twice among the 10 HIGHs. Resolving `duplicate_of` transitively before folding would fix
     this.
2. **Verified findings folded into unsampled targets don't make the target verified.**
   - Five of the six targets weren't sampled. They carry a verified duplicate, but they keep `verified: false` and have
     no verdict.
   - ARCH-04's HIGH comes entirely from AI-01, so ARCH-04 is the one "unverified" HIGH in the counts.
   - A target should inherit `verified`, and the verifier's note, from a verified duplicate.

A third effect is by design. Folding across hats moves a finding into the target hat's column. AI-01 left the AI column,
so the moderator's AI score of 2 now rests on AI-02 alone.

**Duplicates not marked.** These pairs are my reading, not a verifier's:

| Finding | Same as, or overlaps |
|---|---|
| ARCH-20 | Restates TEST-06 and TEST-07 |
| TEST-13 | The same defect as AI-17 |
| TEST-15 | The same defect as ARCH-23 |
| ARCH-28 | The same defect as AI-27 |
| TEST-21 | Overlaps ARCH-18 |
| TEST-24 | Restates AI-06; AI-04 and AI-05 describe its causes |
| ARCH-06 | AI-29's promote-step half |
| AI-10 and ARCH-17 | Both lack a resume path, with different triggers: a re-spawned moderator, and a debate stopped after its primary verdict |

**What verification added.**

- **AI-02 is worse than filed** (V2). An arbitrator that notices a mislabelled domain can't correct it, because the
  checker rejects a rubric that doesn't match the request (DS-15).
- **AI-03 has a sharp edge** (V2). A mis-copied REQUEST_SHA produces an emptier `problems` list than a correct one,
  because a correct verdict still lists the transcript not yet written.
- **TEST-05 has calculable odds** (V1): 1/2, 1/6 or 1/24, by the number of options.
- **Two partial refutations** (V1). The relaunch rule in `child-returns.md` (ARCH-02) and the moderator cap (ARCH-26)
  both exist; the architect hat missed them.
- **Documentation, fetched during the run:**
  - V1: by default, a subagent can spawn subagents up to three layers below the main conversation, and
    `CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH` caps it (ARCH-21).
  - V2, on Claude Code:
    - Fork mode is on by default in interactive sessions from Claude Code v2.1.232, and there the Agent tool has no
      `run_in_background` parameter.
    - In interactive sessions, a subagent that launches background subagents waits for them before it finishes. Under
      `-p` and the SDK it doesn't.
    - The default limit is 20 concurrent subagents.
  - V2, on effort: `medium` is the default on Opus 5.5, and the effort page advises sweeping effort on your own evals
    (AI-31).
  - V2 also sourced AI-22's premise: Zheng et al., ICLR 2024 (arXiv 2309.03882).

## 5. Plan

How the work is split:

- **P0** removes every verified HIGH, covering all nine distinct defects.
- **P1** removes the verified MEDIUMs, and includes the merge fix the next comparison needs.
- **P2** holds the LOW items and the follow-on eval work.

Each change lands with the regression case its findings name, expecting exit 2. The scenarios are in V1's reproduction
table (`verify/V1.md`) and the tester hat's S0 to S23. Make `make_debate.py` follow the agents' real order first
(P0-1), or the new cases inherit its wrong one.

### P0

| # | Change | Where | Removes | Findings |
|---|---|---|---|---|
| P0-1 | Moderator steps 1 and 10 read `gate`: COMPLETE only when it's empty, a resume row for a missing second opinion or promotion, and PARTIAL saying a person decides on a security reason. 0c dispatches every topic with a non-empty `gate`. A transcript skeleton is written before step 6, or a `--stage verdict` flag is added. The arbitrator re-checks `gate` after step 8. `make_debate.py` writes files in the agents' order, and a test runs the prompts' `jq` commands at each stage | `debate_moderator.md`, `debate_arbitrator.md`, `child-returns.md`, `develop-orchestrator.md` (0c), `debate-status.py`, `tests/lib/make_debate.py` | RC1 (its HIGHs) | TEST-14, ARCH-04, AI-01, ARCH-17, ARCH-01, AI-03 |
| P0-2 | `remember.sh decide --key`, and refuse a second active entry with the same link. `promoted()` requires exactly one active block, equal to `decision_id`, that names the verdict label. An override requires an active entry that reverses the verdict's D-NNN | `remember.sh`, `debate-status.py`, `debate_arbitrator.md`, `child-returns.md` | RC2 (its HIGHs) | TEST-06, TEST-07, TEST-08, AI-11 |
| P0-3 | Domain-fit check in moderator step 1 and in `request_problems`, and the arbitrator returns BLOCKED on a mislabelled domain. Withdrawn topics go to review. A security or blocking withdrawal needs a D-NNN or an override, or it counts as a security finding | `debate_moderator.md`, `debate_arbitrator.md`, `debate-status.py`, `verify-gate.sh` | RC3 | AI-02, TEST-09 |
| P0-4 | A decisive claim that is `unverifiable` or `contradicted` caps the band at MEDIUM, so the second opinion runs | `debate-status.py` | RC4 (its HIGH) | TEST-01 |
| P0-5 | `/plan`, `/discuss` and `/design` end with a check for open debate requests. Wave 0 refuses to start Wave 2 while a topic is pending or stale. After a verdict, 0c returns to Wave 5v with spec_impl_reconciler | `plan.md`, `discuss.md`, `design.md`, `develop-orchestrator.md` | RC5 (its HIGH) | ARCH-03 |

Every 2 in the scorecard has a verified MEDIUM as its next-worst finding. So if a re-run after P0 found nothing new,
every cell would be 3 or better.

### P1

| # | Change | Where | Removes | Findings |
|---|---|---|---|---|
| P1-1 | An `evidence_gaps` array. Recompute the second opinion's totals. A minimum structure for briefs, arguments and the transcript, including the score patterns. Record the primary verdict's sha before promote | `debate-status.py`, `debate_moderator.md`, `debate_arbitrator.md`, `tests/lib/make_debate.py` | RC4 (the rest) | TEST-04, TEST-12, TEST-10, TEST-22, TEST-35 |
| P1-2 | `applied_by` and `applied_at` on blocking requests. An `implementer` field | `debate-protocol.md`, `debate-status.py`, `child-returns.md`, `develop-orchestrator.md`, `develop-steps/step-3-tests.md` and step 4 | RC5 (the rest) | ARCH-02, ARCH-16 |
| P1-3 | `PRIOR DECISION` for any earlier D-NNN, including to the promote step. A title marker for a disagreeing second opinion. Step 4c writes `decision_id` back and runs before `gate.passed` | `debate_moderator.md`, `debate_arbitrator.md`, `develop-orchestrator.md` (4c) | RC2 (the rest) | AI-29, ARCH-24, ARCH-33 |
| P1-4 | `request_sha` on the second opinion and the override. Archive a topic's files before a re-run. An `overridden` row in step 1. A hash of the requirements and facts the verdict cites | `debate-status.py`, `debate-protocol.md`, `debate_moderator.md`, `debate_arbitrator.md` | RC6 | ARCH-08, TEST-05, TEST-16 |
| P1-5 | One contract for a missing advocate argument | `debate_arbitrator.md` or `debate-status.py` | RC1 (the rest) | ARCH-11 |
| P1-6 | Merge the depth key into an existing `settings.json`, and `/health` warns when it's missing. The moderator also requires the `REQUEST:` header | `new-project.sh`, `autonomous.md`, `health.md`, `debate_moderator.md` | RC7 (its MEDIUM) | ARCH-21 |
| P1-7 | Score T-007's R1 per copy, or seed distinct starting ids. Give `make_debate.py` a `--decision-id` option. Add a gate case with two promoted debates | `agent_state/eval/suite/T-007-debate/`, `tests/lib/make_debate.py`, `tests/verify-gate.test.sh` | RC8 (its MEDIUM) | TEST-25 |
| P1-8 | Resolve `duplicate_of` transitively before folding, and let a target inherit `verified` from a verified duplicate. Do this before round 3, so its HIGH count doesn't count one defect twice | `.claude/hooks/board-review.py` | Section 4's merge side effects | (none: from section 4) |

### P2

| # | Change | Where | Removes | Findings |
|---|---|---|---|---|
| P2-1 | Run a close call in both pinned orders and score agreement. A wrong-way `initial_reasoning`. A check that the shuffle ran. A rubric item for brief quality. New wording for the forbidden pattern. Then record a T-007 baseline over three runs | `agent_state/eval/suite/T-007-debate/` | RC8 (the rest) | AI-18, TEST-29, TEST-31, AI-31, AI-19 |
| P2-2 | Remove "run FIRST" from 0b, and restate the moderator cap in 0c | `develop-orchestrator.md` | RC7 (the rest) | ARCH-26 |
| P2-3 | Neutral aliases for option labels | `debate_moderator.md`, `debate_arbitrator.md` | RC9 | AI-22 |
| P2-4 | Add the agents that judge and review to the Analysis Paralysis Guard's exceptions | `step-0-orient.md`, `context-budget-protocol.md` | (outside the root causes) | AI-25 |

### Not in the plan

**Unverified clusters to verify first:**

- **RC3's seven security routes:** TEST-18, TEST-19, TEST-20, TEST-23, TEST-13, AI-17 and ARCH-14.
  - The hats reproduced six of them in scratch runs (TEST-23 comes from reading the code), but no verifier checked any.
  - They share P0-3's fix, so verify them as part of that work. If they're confirmed, RC3 becomes the largest cluster of
    security findings.
- **RC1's score-editing group:** AI-04, AI-05, AI-06 and TEST-24. P0-1 rewrites the same self-check step, so settle the
  tie definition and add "scores are final once written" in the same change.
- **The rest of the 64 unverified findings** keep the hats' severity.

**Leads for the four hats that didn't run.** These come from the run hats' "For other hats" sections, and all are
unverified.

- **security:**
  - `remember.sh decide` writes `--decision` and `--rationale` verbatim. A value containing a newline plus `### D-…` or
    `- link:` could forge a block that `decision_blocks()` parses. Not reproduced.
  - `/discuss --auto` isn't required to take the hardened option on security questions.
- **devops:**
  - When the user has no `~/.claude/settings.json`, `install.sh:141-143` copies the framework's `settings.json` there.
    That makes the project-relative hooks and the depth cap global.
  - Neither `install.sh` nor `new-project.sh` merges framework keys into an existing settings file.
  - The `jq` that the moderator's and arbitrator's commands need is an unstated dependency.
- **sre:** up to four researchers or advocates append to `execution.jsonl` and `lessons.md` at the same time, with no
  lock.
- **senior_dev:**
  - `debate-status.py:262-264` says there's no `tie_break` even when one exists and only the 0.05 window failed.
  - `--request-sha` reads only `<topic>.request.json`, so a legacy-named request gets no hash.
  - `make_debate.py:30` never closes its files.

**Round-1 RC11's circuit-breaker count.** No round-2 hat filed it, and no verifier in either round sampled it.

**Round 3.** After P0, run a round 3 with the same three hats. Given RC3, consider adding the security hat.

## 6. Method

- **Command and run.** `/board-review` with target group `debate` and run directory
  `docs/board-review-2026-09-30-debate-2`, at commit `95fb871` (from the `sha` file). Hats: `ai_engineer`, `architect`
  and `tester`, as in round 1. Senior_dev, sre, devops and security didn't run.
- **Targets.** The four debate agents. Each hat read all four in full; the coverage notes are in `hats/*.json`.
- **Hats.** Each hat ran as one general-purpose agent with its saved checklist (`.claude/skills/review/board-review/`)
  and the board-review protocol. Reproductions ran in scratch directories outside the repo:
  - tester: fixtures S0 to S23, each a passing phase built with the `verify-gate.test.sh` helpers and
    `tests/lib/make_debate.py`, run against the real `verify-gate.sh`; plus a mutation test of the prompt lints on a
    `git archive` copy.
  - architect: scenarios S1 to S13 against copies of `debate-status.py` and `remember.sh`.
    `tests/dependency-graph.test.sh` passed 54/0.
  - ai_engineer: fetched `code.claude.com/docs/en/sub-agents` and `code.claude.com/docs/en/tools-reference`, plus
    `prompting-claude-opus-5-5`, `prompting-claude-opus-5` and `build-with-claude/effort` on `platform.claude.com`.
    Reproduced runtime claims with `make_debate.py`, `debate-status.py` and `remember.sh`.

  The run files don't record which model the hats used.
- **Verification.** `board-review.py select` builds each verifier's input:
  - every CRITICAL and HIGH, plus a deterministic 25% sample (at least 3) of each hat's MEDIUM and LOW findings, seeded
    on the run and the hat;
  - severity removed, and order shuffled;
  - new since round 1: each verifier also gets every other finding in brief, so it can mark duplicates outside its
    sample, and every verdict needs a note.

  Two verifiers ran, both on `claude-fable-5-1`. Round 1 recorded the alias `fable`; its V2 reported Fable 5.1.
  - V1: architect and tester, 27 findings. Reproduced on scratch fixtures with `debate-status.py --check`, and with the
    full `verify-gate.sh` for the key cases.
  - V2: ai_engineer, 10 findings. Reproduced with `make_debate.py` and `remember.sh`, and checked Claude Code and API
    behaviour against Anthropic's documentation.
- **Merge.** `board-review.py merge`. Its rules haven't changed since round 1:
  - confirmed and narrowed findings take the verifier's severity, and refuted ones drop out (there were none);
  - marked duplicates fold into their target (section 4 covers chains and unsampled targets);
  - an agent's score under a hat is its worst finding there, from CRITICAL 1 to none 5, averaged across hats.

  Unsampled MEDIUM and LOW findings count at the hat's severity, and are now marked `*`. Round 1's README noted a
  mismatch: the code scored on all findings, while the docs said "verified" findings. Round 1's prompt commit resolved
  that by changing the description and adding the `*`, not by changing the rule. So both runs are scored the same way,
  and the comparison holds.
- **Compare.** `board-review.py compare` diffs the per-agent averages and the severity counts (section 1).

**Finding counts:**

| | CRITICAL | HIGH | MEDIUM | LOW | Total |
|---|---|---|---|---|---|
| Filed by the hats (AI 32, Arch 34, Test 35) | 0 | 15 | 59 | 27 | 101 |
| Sent to verification, at the hat's severity | 0 | 15 | 13 | 9 | 37 |
| After merge (`merged.json` counts) | 0 | 10 | 60 | 25 | 95 |
| ... verified | 0 | 9 | 15 | 7 | 31 |
| ... unverified (hat's severity, except ARCH-04) | 0 | 1 | 45 | 18 | 64 |
| Folded into another finding (all verified) | 0 | 1 | 4 | 1 | 6 |

The unverified HIGH is ARCH-04, which was filed as MEDIUM. Its HIGH comes from AI-01, a verified HIGH folded into it.

| Hat | Filed | As filed (C/H/M/L) | Sent to verification | Verified | Unverified |
|---|---|---|---|---|---|
| ai_engineer | 32 | 0 / 2 / 16 / 14 | 10 | 10 (7 kept, plus AI-01, AI-11 and AI-18 folded) | 22 |
| architect | 34 | 0 / 3 / 20 / 11 | 11 | 11 (10 kept, plus ARCH-21 folded) | 23 |
| tester | 35 | 0 / 10 / 23 / 2 | 16 | 16 (14 kept, plus TEST-05 and TEST-07 folded) | 19 |

**Round 1 and round 2 side by side:**

| | Round 1 | Round 2 |
|---|---|---|
| Commit | `77f221c` | `95fb871` |
| Findings filed | 88 | 101 |
| Sent to verification | 39 | 37 |
| Refuted | 0 | 0 |
| Narrowed | 6 | 10 |
| Severity moved | 13 | 14 |
| Duplicates folded | 3 | 6 |
| Findings after merge | 85 | 95 |
| HIGH after merge | 13 | 10 (9 distinct) |
| Verifier model | `fable` | `claude-fable-5-1` |
| verify-gate and debate test suites at that commit | 53/53, 46/46 | 58/58, 79/79 |
