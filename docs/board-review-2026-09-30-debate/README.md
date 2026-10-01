# Board review: debate agents (2026-09-30, trial run)

Run `docs/board-review-2026-09-30-debate`, commit `77f221c`. This was a trial run of `/board-review` with three of
its seven hats (ai_engineer, architect, tester) on the four debate agents: `debate_moderator`, `debate_researcher`,
`debate_advocate` and `debate_arbitrator`. Sources: `merged.json`, `scorecard.md`, `hats/*.md`, `verify/V1.md`,
`verify/V2.md`. Severities and scores are the ones in `merged.json`. Nothing here re-rates them.

## 1. Summary

The hats filed 88 findings. Blind verification on Fable checked 39 of them: every CRITICAL and HIGH, plus a sample of
the rest. It refuted none, moved 13 severities and folded 3 duplicates, which leaves 85 findings: 0 CRITICAL, 13 HIGH,
54 MEDIUM and 18 LOW.

The main finding is that the debate's safeguards are written into the prompts but the gate doesn't enforce them. The
gate check is `debate-status.py --check`, which verify-gate check (f) runs. It blocks on four conditions, and each one
is keyed on something the debate reports about itself: a schema key, a confidence label, whether a file exists, or a
D-NNN heading. The verifiers reproduced these effects:

- **A self-reported confidence label decides the second opinion.** A verdict that calls a 0.2-point gap "HIGH
  confidence" skips the Fable second opinion, even when it picks the lower-scoring option.
- **Files count by existing.** An empty second-opinion file satisfies the second-opinion requirement.
- **Malformed requests are ignored.** A blocking request with a JSON typo is silently skipped.
- **A path prefix skips report checks.** Any agent's report logged under `agent_state/debates/` skips report
  validation, so a failing `test_runner` passes the gate.

The protocol says some outcomes need a person: a security choice that isn't the hardened default, an INCOMPLETE
verdict, or a second opinion that disagrees. These end as review notes that don't fail the gate, and under
`/autonomous` nothing reads those notes. Only `/develop` handles a `NEEDS_DECISION` return, so a decision raised in `/plan` waits for `/develop`'s
gate, after the code is built. The Fable second opinion reads the primary verdict's D-NNN entry in
`docs/DECISIONS.md` before it judges. Two debates that finish together can lose a ledger entry.

Most of the fixes sit outside the four prompts. 11 of the 13 HIGH findings are fixed mainly in `debate-status.py`,
`verify-gate.sh`, `remember.sh` or the commands.

The scorecard, copied from `scorecard.md`. Each cell is the worst finding naming the agent under that hat (CRITICAL 1,
HIGH 2, MEDIUM 3, LOW 4, none 5). Section 6 explains which findings count toward it.

| Agent | AI | Arch | Test | Avg |
|---|---|---|---|---|
| debate_arbitrator | 2 | 2 | 2 | 2.0 |
| debate_moderator | 2 | 2 | 2 | 2.0 |
| debate_advocate | 3 | 3 | 2 | 2.67 |
| debate_researcher | 3 | 3 | 2 | 2.67 |

How to read the scores:

- **Arbitrator and moderator.** Both are at 2 under every hat, and verified HIGH findings back every one of those 2s.
- **Advocate and researcher, tester hat.** Their 2 comes from one finding, TEST-10: the verify-gate path exemption,
  which names all four agents because their files live under `agent_state/debates/`.
- **Advocate and researcher, ai_engineer and architect hats.** Their 3s come from findings that weren't in the
  verification sample (see section 6, Method).

## 2. Root causes, ranked

Each of the 36 verified findings that remain after merging is in exactly one root cause; 39 if you count the three
duplicates that were folded in. The ranking goes by the verified severity of the findings a cause explains (HIGH count
first, then MEDIUM), then by how far the failure reaches. Seven of the twelve causes cut across hats, including five of
the six that carry a HIGH.

Under each cause, "Same cause, unverified" lists findings that weren't sampled for verification. They keep the hat's
severity, and the grouping is mine, not a verifier's.

| # | Root cause | Verified findings | HIGH | Hats | Agents |
|---|---|---|---|---|---|
| RC1 | The gate checks what a debate says about itself, not what it contains | 11 | 4 | AI, Test | all four |
| RC2 | Outcomes that need a person have no machine signal, and `/autonomous` reads no review notes | 5 (+1 folded) | 3 | Arch, Test | arbitrator, moderator |
| RC3 | The decision hand-back is wired into one command, for one outcome | 5 | 2 | AI, Arch | moderator, arbitrator |
| RC4 | The D-NNN is written before the second opinion runs | 2 | 2 | AI, Arch | arbitrator, moderator |
| RC5 | verify-gate exempts reports by path prefix | 1 (+1 folded) | 1 | Test, Arch | all four |
| RC6 | The ledger writer isn't safe for parallel debates | 1 | 1 | Arch | arbitrator, moderator |
| RC7 | A verdict isn't tied to the request it answered | 3 (+1 folded) | 0 | AI, Arch, Test | moderator, arbitrator |
| RC8 | Non-blocking requests are enforced by prose alone | 2 | 0 | Arch, Test | moderator |
| RC9 | The moderator's step 4 only handles a clean return | 2 | 0 | AI | moderator, arbitrator |
| RC10 | A skill pack contradicts the moderator's own rule | 1 | 0 | AI | moderator |
| RC11 | Debate bookkeeping lives in the model's memory or has no owner | 2 | 0 | Arch | all four |
| RC12 | Tests and eval check fixed paths and phrases, not behaviour | 1 | 0 | Test | advocate |

### RC1: The gate checks what a debate says about itself, not what it contains

**What's wrong.** V1 named this the common thread of its HIGH findings. `debate-status.py --check` blocks on four
conditions: pending, invalid, not promoted, and second opinion missing. Each condition is keyed on a self-reported field
or on whether a file exists. V1 and V2 reproduced every bypass below against the real hooks; each passed with exit 0.

| What the gate trusts | Bypass (reproduced) | Finding | Severity |
|---|---|---|---|
| That a debate file parses and classifies | A request with a trailing comma, or a mistyped `schema`/`type`, is listed as "(ignored)" and the gate passes | TEST-01 | HIGH |
| The verdict's `schema` key | Leaving it out switches off every v2 check. A LOW-confidence security verdict with no hardened default, no second opinion and no D-NNN passes | TEST-02 | HIGH |
| The confidence label and the stated gap | A verdict for the lower-scoring option, with wrong totals, a 0.2 gap labelled HIGH and no claim checked, passes with no second opinion. The same file labelled LOW blocks | AI-02, TEST-04 | HIGH, MEDIUM |
| That a second-opinion file exists | `{}`, or an Opus opinion in the same order with no verdict, clears the block | TEST-05 | HIGH |
| The second opinion's `model` field | The arbitrator copies the literal `"fable"`, so a classifier fallback to Opus 4.8 or an omitted model parameter still reads as Fable | AI-07 | MEDIUM |
| The rubric fields | A verdict passes as HIGH confidence with the wrong rubric, the runner-up unscored, no `presentation_order` and an unverifiable decisive claim | TEST-12 | MEDIUM |
| That a D-NNN heading exists | Any existing heading, or any ledger text containing the verdict's file name, counts as promoted | TEST-14 | MEDIUM |
| That `verdict.json` exists | Research, arguments, transcript and an arbitrator completion line are all optional, so any agent can unblock itself | TEST-06 | MEDIUM |
| That `override.json` has a `user_override` key | One key clears a pending or even an invalid request | TEST-09 | MEDIUM |
| `unresolved.json` entries | An option the request never offered, or a permissive security default marked HIGH, counts as resolved | TEST-17 | MEDIUM |

**Agents.** All four: the arbitrator and moderator in most rows, and the researcher and advocate through TEST-06.

**Fix.** The changes go in `debate-status.py` unless noted. Each lands with a DS case built from V1's scenario table.

1. Fail closed. Any `*.request.json`, and any JSON under `agent_state/debates/` other than overrides, that won't parse
   or classify is a blocking problem (TEST-01).
2. A v1 request requires a v1 verdict. Keep the legacy path only for legacy-named pairs (TEST-02).
3. Recompute each option's total from its per-criterion scores and the domain rubric's weights. Derive the gap and the
   confidence band from those totals. Require the verdict to be the top total unless it cites `hardened_default`,
   `none_ideal` or the tie rule. Key `second_opinion_required()` on the computed gap. Load the weights from one table
   shared with lints DL-09/10/11 (AI-02, TEST-04).
4. Check that the rubric matches the domain, every option is scored on every criterion, `presentation_order` is a
   permutation of the option ids, `claims_checked` is non-empty with sources, and no decisive claim is unverifiable at
   HIGH confidence (TEST-12).
5. Count a second opinion only when it has the v1 schema, a Fable model id, a verdict among the option ids, and the
   reverse of the primary's `presentation_order`.
   - The arbitrator's template writes the exact model id from its system prompt.
   - Add a review reason when that id isn't Fable or equals the primary's (TEST-05, AI-07).
6. Treat a verdict as promoted only when the link line of its `### D-NNN` block equals the verdict's path (TEST-14).
7. A RESOLVED verdict needs research for every option, arguments for every option at HIGH impact, and a transcript. In
   check (f), it also needs a `debate_arbitrator` completion line whose report is that verdict (TEST-06).
8. Validate overrides and auto-resolved entries (TEST-09, TEST-17).
   - An override needs an option id, a rationale, a timestamp and a D-NNN that links it, and it never clears an invalid
     request.
   - An auto-resolved entry must name one of the request's options, a hardened one for security, and is shown at LOW
     confidence.

**Same cause, unverified.**

- ARCH-11: restates TEST-05.
- ARCH-27: `presentation_order` and the transcript are never checked.
- TEST-18: research briefs and arguments are never opened, although check (f) is said to validate them.
- TEST-30: a 10-character reason withdraws a blocking request.
- TEST-31: a phase written as `01` or `phase-1` is silently out of scope.
- TEST-32: an extra field can get a request classified as `unresolved.json` and dropped.

### RC2: Outcomes that need a person have no machine signal, and `/autonomous` reads no review notes

**What's wrong.** The protocol sends four outcomes to "the checkpoint": a security choice that isn't the hardened
default, an INCOMPLETE verdict, a disagreeing second opinion, and an assumption. `debate-status.py` emits them as review
notes, which don't fail `--check`, and nothing maps them to `run.json` `awaiting_human`.

- **No checkpoint left under `/autonomous`.** The one checkpoint comes before implementation, so it has already passed
  when these notes appear. `autonomous.md` never runs `debate-status.py`, and its Post-Phase review and Step 7 report
  read only `auto-resolved.jsonl`. The first reader is `/accept`'s release notes (`accept.md:713`), after all phases.
- **A weaker security choice passes.** It goes through at MEDIUM confidence even when the Fable judge chose the
  hardened option (reproduced).
- **A pending security debate counts as a non-security blocker.** A forced gate under `/autonomous` therefore clears it
  without the per-finding security acknowledgement that SEC-01 requires.
- **"No hardened option" blocks with the wrong reason.** The protocol's prescribed output for that case is classed
  INVALID, so it blocks as a broken contract instead of asking the user.

**Findings.** ARCH-04 (HIGH, with TEST-07 folded in), TEST-03 (HIGH), TEST-13 (HIGH), TEST-08 (MEDIUM, narrowed),
ARCH-10 (MEDIUM).

**Agents.** Arbitrator, moderator.

**Fix.**

1. Add a needs-human class to `debate-status.py` that blocks `--check` until an `override.json` exists. It covers:
   - a security verdict below HIGH confidence that isn't `hardened_default` and has no `must_override` naming the
     FR/NFR (TEST-03);
   - a security verdict whose second opinion disagrees (TEST-03);
   - a security INCOMPLETE (TEST-08);
   - a security verdict with no hardened option, accepted as INCOMPLETE/LOW instead of INVALID (ARCH-10).
2. In verify-gate check (f), add one to `SECURITY_FAILS` for each blocking security-domain topic, so a forced gate
   needs a per-finding `security_acknowledged` entry. Also list a pending security debate among `/autonomous`'s pause
   conditions (TEST-13).
3. Give review reasons a consumer. `/autonomous`'s Post-Phase review runs `debate-status.py --phase N` and sets
   `awaiting_human` for needs-human topics, or appends them to `auto-resolved.jsonl`. The moderator and the protocol
   name that consumer instead of "the checkpoint" (ARCH-04).

### RC3: The decision hand-back is wired into one command, for one outcome

**What's wrong.** Every agent's contract says to write a request and return `NEEDS_DECISION <topic>`, but only
`develop-orchestrator.md` has a rule for that return; a grep over `.claude/commands` finds no other.

- **Where decisions arise, nothing handles them.** `/plan`, `/discuss` and `/design` are where spec_writer, adr_agent,
  project_planner and ux_designer make architecture and data-model calls, and none of them handles the return.
  `plan.md` recognises a single return shape. A request raised in `/plan` is first seen at `/develop`'s Wave 6 gate,
  after the phase was built on an unfinished spec.
- **Sub-orchestrators can't pass it on.** They have no rule to pass a child's `NEEDS_DECISION` upward.
- **Even `/develop` handles only a moderator COMPLETE:**
  - A moderator BLOCKED (already decided by a D-NNN, an invalid request, or the wrong depth) leaves the request
    pending, and 0c re-spawns the moderator.
  - Wave 6 runs the gate (0b) before the debate dispatcher (0c), and exits on the failure.
  - An override or reversal has no path back to the requester, or to code already built on the old decision.

**Findings.** AI-03 (HIGH), ARCH-01 (HIGH), ARCH-14 (MEDIUM, narrowed), ARCH-29 (MEDIUM), ARCH-19 (MEDIUM). AI-03 and
ARCH-01 are the same defect, found by two hats.

**Agents.** Moderator; arbitrator (ARCH-19).

**Fix.**

1. Move the return table, "Spawning agents and reading what they return" (`develop-orchestrator.md:269-289`), into one
   shared section: a skill, `agent-common.md` or `debate-protocol.md`. Load it from every command that spawns agents:
   plan, discuss, init, design, test, accept, deploy, hotfix, optimize, diagnose, review and recon. Add to the operating
   contract: a sub-orchestrator that gets `NEEDS_DECISION` from a child returns `NEEDS_DECISION` itself. Extend lint
   DL-16 to fail any spawning command that lacks the handler (AI-03, ARCH-01).
2. Add rows for a moderator BLOCKED (ARCH-14):
   - already decided: relaunch the requester with `DECISION <topic>: <D-NNN>` and withdraw the request;
   - invalid: relaunch the requester to fix its request.
3. Run Wave 6 0c before 0b, or let 0b's failure continue to 0c (ARCH-29).
4. Define who acts on an override (ARCH-19):
   - relaunch the requester with the override;
   - raise a carried-forward item when earlier phases built on the reversed D-NNN;
   - expose an `effective_verdict` for `/worklog` and `/accept`.

**Same cause, unverified.** AI-16 and ARCH-20: step-0-orient's "Universal Agent Return Protocol" contradicts the
contract's first-line statuses. ARCH-24: ad-hoc moderator calls skip the requester. TEST-21: the moderator returns
COMPLETE for an invalid or INCOMPLETE verdict. ARCH-15: the acceptance-escalation template produces an invalid topic,
which ends in an unhandled BLOCKED.

### RC4: The D-NNN is written before the second opinion runs

**What's wrong.** The order of moderator steps 6 and 7 hands the second opinion the answer it should check:

1. In step 6, the primary arbitrator records the D-NNN with `remember.sh decide`.
2. In step 7, the moderator spawns the Fable second opinion with the same inputs.
3. The second opinion's Required Reading and step 1 tell it to read `docs/DECISIONS.md` first and not to re-litigate
   an active decision. Second-opinion mode excludes only `<topic>.verdict.json`.
4. The ledger entry it reads carries the chosen option and why the runner-up lost.

The one cross-model check on close HIGH-impact calls therefore reads the primary's answer before judging, and agreement
looks like confirmation. V2 confirmed the structure; the anchoring itself is a general LLM property and wasn't
reproduced.

**Findings.** AI-01 (HIGH), ARCH-02 (HIGH): the same defect, found by two hats.

**Agents.** Arbitrator, moderator.

**Fix.** When a second opinion is required, the primary arbitrator writes the verdict without calling `remember.sh`.
The moderator records the D-NNN after step 7 returns, or re-spawns the arbitrator in a promote mode. In MODE
second-opinion, the arbitrator skips any `DECISIONS.md` entry that links `agent_state/debates/<topic>.*`, and doesn't
open `<topic>.verdict.json`, `.verdict-detailed.md` or `.transcript.md`. The moderator passes that exclusion list in the
spawn prompt.

**Same cause, unverified.**

- TEST-19: the second opinion can also find the primary verdict by listing the directory.
- AI-17: LOW and INCOMPLETE verdicts enter the ledger as active before any human review.
- ARCH-18: a re-debate leaves two active D-NNN entries.
- AI-06 and ARCH-12: `model-routing.md` doesn't sanction the Fable spawn, and nothing says what to do when Fable can't
  run.

### RC5: verify-gate exempts reports by path prefix

**What's wrong.** `verify-gate.sh:359-361` skips report validation for any logged path that starts with
`agent_state/debates/`. The skip runs before the test-sidecar branch, and the bash `case` pattern `*` matches `/` and
`..`. V1 reproduced three passes:

- a `test_runner` with a FAIL sidecar, logged as `agent_state/debates/../phases/1/reports/test_runner.md`;
- a security_reviewer report `agent_state/debates/sec.md` with `BLOCKING:3`;
- a unit_test_agent with no sidecar at all.

The same FAIL logged at its normal path blocks. This reopens the 2026-09-30 defect class "the gate passed a phase whose
reports said FAIL", and it does so for every agent, not just the debate agents.

**Findings.** TEST-10 (HIGH, with ARCH-07 folded in).

**Agents.** All four. They're named because their files live under that directory; the defect is in `verify-gate.sh`.

**Fix.** Apply the exemption only when the agent is one of the four debate agents and the resolved path (realpath) is
inside `agent_state/debates/` with no `..`. Add verify-gate test S14.

### RC6: The ledger writer isn't safe for parallel debates

**What's wrong.** Wave 6 0c and the moderator both allow parallel moderators. But `remember.sh decide` reads the ledger,
modifies it and replaces the file, with no lock and a fixed tmp name. V1 ran two concurrent calls 20 times:

| Outcome | Trials |
|---|---|
| One entry lost | 20 of 20 |
| Loud failure: one caller crashed with a traceback | 17 of 20 |
| Silent failure: both printed the same D-NNN and nothing failed | 3 of 20 |

In the silent case, the gate's promotion check passes on the other topic's heading (TEST-14, in RC1).

**Findings.** ARCH-03 (HIGH, narrowed on "silently").

**Agents.** Arbitrator, moderator.

**Fix.** Serialize `remember.sh decide` with a lock (`mkdir` or `flock` on `docs/DECISIONS.md.lock`) and a unique tmp
file, and land TEST-14's link check with it. Until then, run moderators one at a time. The architect hat suspects
`remember.sh add` (facts) has the same race; that's unverified.

### RC7: A verdict isn't tied to the request it answered

**What's wrong.** Topics are joined by slug alone, and a verdict carries no phase and no request hash.

- **A reused slug gets the old verdict back,** whether the slug comes back in a later phase or a request is rewritten
  under it. V1 reproduced a phase-5 HIGH-impact security request being "resolved" by a phase-3 MEDIUM architecture
  verdict.
- **The stale verdict also switches checks off.** Impact and domain are read from the verdict first, so it disabled
  the second-opinion and hardened-default checks.
- **No overlap means a stuck topic.** When the old option ids don't overlap the new ones, the topic goes INVALID and
  nobody owns clearing it.
- **Only part of a re-file is caught.** `debate-status.py` catches a re-file that drops the winning option id. It
  misses changed labels or context, and added options.
- **The legacy suffix match crosses topics.** Matching on `<step>-<topic>` can resolve a v1 request with another
  topic's verdict.

**Findings.** ARCH-05 (MEDIUM, with TEST-15 folded in), AI-19 (MEDIUM, narrowed), TEST-16 (MEDIUM).

**Agents.** Moderator, arbitrator.

**Fix.**

1. Copy `phase` and a `request_sha` into the verdict. `debate-status.py` treats a mismatch as stale: the topic is
   pending, with "verdict is for an earlier request".
2. Take impact and domain from the request, not the verdict.
3. The moderator archives a stale verdict and re-runs the debate instead of returning BLOCKED.
4. Apply the suffix match only to true legacy requests: no `topic` field and no v1 schema.

**Same cause, unverified.** ARCH-17: the `"$T"-*` glob in `reset-phase.md` archives another phase's pending debate.

### RC8: Non-blocking requests are enforced by prose alone

**What's wrong.** The protocol says a non-blocking request lets the agent continue on its default, and that "the debate
still runs before the gate". But `blocking_reason()` returns None for any non-blocking request, so a pending
HIGH-impact non-blocking request passes the gate. Test DS-22 asserts that as intended behaviour.

The request schema also has no field for the default the agent built. By Wave 6, usually after compaction, the parent
can't tell whether the verdict differs from what the code does.

**Findings.** TEST-11 (MEDIUM), ARCH-06 (MEDIUM).

**Agents.** Moderator.

**Fix.**

1. Add `default_taken` to `sdlc.debate-request/v1`, required when `blocking` is false, and validate it.
2. Under `--check`, block every pending in-scope request, with the reason "non-blocking debate never run".
3. Emit "verdict B differs from default A the agent built", so the relaunch is computed rather than remembered.
4. Change DS-22 and the matching verify-gate case to expect exit 2.

**Same cause, unverified.** ARCH-08 (restates TEST-11). ARCH-09: non-blocking debates are dispatched at the gate, after
the security re-review.

### RC9: The moderator's step 4 only handles a clean return

**What's wrong.** Step 4 has no case for two kinds of return:

- **A thin brief.** Step 4 accepts a PARTIAL research brief as a finished result, so nothing caps confidence when one
  option's evidence is much thinner than another's, and the scoring anchors reward the better-documented option.
- **A spawn error.** "Concurrent subagent limit reached" has no case. Anthropic's sub-agents doc says the 21st
  running subagent fails and the error says not to retry. The error turns into a gap and an INCOMPLETE/LOW verdict that
  reflects slot exhaustion, not evidence. It needs five or more moderators with three or four options each, dispatched
  in one message.

**Findings.** AI-05 (MEDIUM, narrowed), AI-09 (MEDIUM, narrowed).

**Agents.** Moderator, arbitrator.

**Fix.**

1. Treat a PARTIAL as a gap. Record it and pass `EVIDENCE INCOMPLETE: <option>: <what is missing>` to the arbitrator.
   The arbitrator caps confidence at MEDIUM, or writes INCOMPLETE when the decisive criterion has no evidence.
2. Budget subagent slots in the moderator's Limits and in Wave 6 0c. Each moderator holds 1 + (number of options)
   slots, so run at most four moderators at once.
3. On a limit error, spawn the remaining children in a later message. Don't record it as a gap.

**Same cause, unverified.**

- AI-04 and ARCH-13: a child's `NEEDS_DECISION` or `NEEDS_INPUT` is treated as a progress note and re-spawned, and its
  request file later blocks the gate.
- AI-20 and TEST-33: a re-spawned moderator or arbitrator overwrites the first attempt.
- AI-24: in auto mode, a child's plain-text final message may not reach the moderator.

### RC10: A skill pack contradicts the moderator's own rule

**What's wrong.** `auto-research.md` is in the moderator's `skill_packs`. Under `--auto`, its "NEVER skip a question"
rule tells the moderator to research or default a missing fact itself instead of returning `NEEDS_INPUT`. A verdict can
then rest on an invented fact that isn't marked as an assumption. The moderator's own body says `NEEDS_INPUT` in four
places, so most of the instruction weight is on the right side.

**Findings.** AI-14 (MEDIUM).

**Agents.** Moderator.

**Fix.** Drop `auto-research.md` from the moderator's `skill_packs`; it belongs to debate_researcher. Alternatively, add
to step 1 that the pack doesn't apply, and that missing data returns `NEEDS_INPUT` under `--auto` too.

**Same cause, unverified.**

- ARCH-22: the same contradiction, and it adds that a researcher may log its "answer" to `decisions.md`.
- AI-18: `deep-research.md`, in the researcher's packs, still hard-codes the search years that were removed on
  2026-09-30.

### RC11: Debate bookkeeping lives in the model's memory or has no owner

**What's wrong.** Two pieces of bookkeeping have no tool or no owner:

- **The circuit breaker is counted by hand.** Nothing reports the per-step and per-phase debate counts, so compaction
  loses the count.
- **Completion lines have no single writer.** Either the child or the moderator may write the children's
  `execution.jsonl` completion lines. Children must infer `{{PHASE}}`, and ad-hoc debates have no phase directory at
  all.

**Findings.** ARCH-26 (LOW), ARCH-28 (LOW).

**Agents.** All four (ARCH-28); moderator (ARCH-26).

**Fix.**

1. `debate-status.py --json` reports counts per (phase, `from_step`) and a `limits_exceeded` list.
2. The child writes its own completion line, and the moderator passes `PHASE: <n>` in each child prompt.
3. The protocol says what to do when a request has no phase.

### RC12: Tests and eval check fixed paths and phrases, not behaviour

**What's wrong.** Eval T-007's R5 "no anchoring" item matches three phrases from the old template, so an advocate that
writes "I rate it 9/10" passes (reproduced). More broadly, the tester hat reports that both committed suites are green
at this commit (debate 46/46, verify-gate 53/53) even though every gate hole above is present. DS-22 asserts one of
those holes (RC8) as intended behaviour.

**Findings.** TEST-27 (LOW).

**Agents.** Advocate.

**Fix.**

1. R5 also fails on `[0-9]+(\.[0-9]+)? ?/ ?10` and `score[s]? *[:=] *[0-9]`.
2. Every fix for RC1–RC8 lands with a regression case built from V1's scenario table (`verify/V1.md`) that expects
   exit 2.

**Same cause, unverified.**

- TEST-26: no negative tests.
- TEST-22 and AI-13: T-007 has never run, so nothing measures the debate agents' effort settings.
- TEST-23: R3 doesn't control presentation position.
- TEST-24: the eval covers only clear-cut calls.
- TEST-28: R6 passes a verdict that scored only the winner.
- TEST-29: a lint's matches come from boilerplate, so deleting the instruction still passes.

### Unverified findings outside these root causes (16)

- **Judge inputs and evidence quality, mostly from the ai_engineer hat:**
  - AI-10 and ARCH-31: the HIGH-impact arbitrator doesn't get the research briefs.
  - AI-11: the arbitrator reads the requester's `initial_reasoning` first.
  - AI-12: the tie rules contradict each other and have no deterministic end.
  - AI-15: the source re-check goes through WebFetch's summary.
  - AI-21: advocates rate their own weaknesses.
  - AI-22: evidence strength counts agreeing sources, not independent ones.
  - AI-23: argument length isn't bounded.
  - TEST-20: the decisive claim is re-checked only by the judge that relies on it.
  - TEST-25: evidence carries no version or date.
  - ARCH-23: the researcher doesn't know the rubric it will be scored on.
- **Runtime:** AI-08, the foreground rule against interactive fork mode.
- **Templates, ledger coverage and install:**
  - ARCH-16: the E2E escalation picks the testing rubric.
  - ARCH-21: `/discuss` decisions never become D-NNN entries.
  - ARCH-25: `remember.sh` is missing in projects set up by `/init`.
  - ARCH-30: the guard tells an arbitrator to put the D-NNN in its final message instead of running
    `remember.sh decide`.

## 3. Per-agent: the first change

All four agents score 2 under at least one hat, because every tester-hat score is 2, so all four are listed. The first
change is the one in, or for, the agent's own file that removes a verified HIGH. Most of each agent's other HIGH
findings are fixed in hooks and commands (see section 5, Plan).

| Agent | AI / Arch / Test (avg) | First change | Removes | Verified HIGH findings still naming it |
|---|---|---|---|---|
| debate_arbitrator | 2 / 2 / 2 (2.0) | In MODE primary, don't call `remember.sh decide` when a second opinion is due. In MODE second-opinion, skip the topic's D-NNN entry and don't open its verdict, verdict-detailed or transcript files. In the same edit, write the exact model id from the system prompt instead of the literal `"fable"` (AI-07) | AI-01, ARCH-02 (RC4) | AI-02, TEST-02, TEST-05 (RC1); TEST-03, ARCH-04 (RC2); TEST-10 (RC5); ARCH-03 (RC6) |
| debate_moderator | 2 / 2 / 2 (2.0) | Own the ledger write: record the D-NNN after step 7 returns, and pass the second opinion an explicit exclusion list. This is the other half of the arbitrator change | AI-01, ARCH-02 (RC4) | AI-02, TEST-01, TEST-05 (RC1); ARCH-04, TEST-03, TEST-13 (RC2); AI-03, ARCH-01 (RC3); TEST-10 (RC5); ARCH-03 (RC6) |
| debate_advocate | 3 / 3 / 2 (2.67) | Fix the verify-gate path exemption (RC5). The defect isn't in the advocate's file: TEST-10 names it because its argument files live under `agent_state/debates/` | TEST-10 | None. Its worst verified finding becomes TEST-06 (MEDIUM, RC1) |
| debate_researcher | 3 / 3 / 2 (2.67) | The same: fix the RC5 path exemption | TEST-10 | None. Its worst verified finding becomes TEST-06 (MEDIUM, RC1) |

In their own files, the advocate and researcher have no verified finding above LOW: ARCH-28, and TEST-27, which is in
the eval rubric. The prompt change both the ai_engineer and architect hats raised for them is unverified: inside a
debate, never file a request or return `NEEDS_DECISION`; record the sub-question as an open question in the brief
(AI-04, ARCH-13).

## 4. What verification changed

**Refuted: none.** V1 wrote that it "tried to refute every finding and could not refute any": every cited `file:line`
says what the evidence quotes, and every gate or `debate-status.py` scenario produced the exit code the finding claims.
V2 refuted none of its 8.

**Verifier statistics** (from `scorecard.md`):

| Verifier | Hats | Model | Total | Confirmed | Narrowed | Refuted | Unverifiable | Severity up | Severity down |
|---|---|---|---|---|---|---|---|---|---|
| V1 | architect, tester | fable | 31 | 28 | 3 | 0 | 0 | 1 | 11 |
| V2 | ai_engineer | fable | 8 | 5 | 3 | 0 | 0 | 1 | 0 |

The merge reported no warnings; the "verifier changed nothing" check didn't fire. It reported no errors either: every
CRITICAL and HIGH has a verdict.

**Severities moved: 13.** Nine of the 11 downgrades were the tester hat's: all three CRITICALs went to HIGH, and six
HIGHs went to MEDIUM. V1's stated rule was that a failing path which needs an agent to break its own instructions, a
reused slug or a malformed file is MEDIUM. V2 kept all three ai_engineer HIGHs, and two LOWs went up.

| Finding | Hat | Verifier | Why (verifier's note) |
|---|---|---|---|
| TEST-01 | CRITICAL | HIGH | No reason recorded |
| TEST-02 | CRITICAL | HIGH | No reason recorded |
| TEST-03 | CRITICAL | HIGH | The code can't tell whether a MUST was cited, so a plain block would false-positive; the fix needs a `must_override` field |
| ARCH-05 | HIGH | MEDIUM | Needs a reused slug or a rewritten request. The consequence, an undebated HIGH-impact security decision passing, is serious |
| ARCH-06 | HIGH | MEDIUM | No reason recorded |
| TEST-04 | HIGH | MEDIUM | Fails only when the arbitrator mislabels its confidence against its own scores, and the data to check it is in the verdict |
| TEST-06 | HIGH | MEDIUM | A fabricated verdict requires an agent to break its own instructions; the gate simply can't tell |
| TEST-08 | HIGH | MEDIUM | Narrowed (see below) |
| TEST-09 | HIGH | MEDIUM | The parent writes `override.json` on a human's instruction, so no unattended agent is involved; the check still validates nothing |
| TEST-11 | HIGH | MEDIUM | A codified design choice (DS-22); the risk is real only when the parent skips Wave 6 0c |
| TEST-12 | HIGH | MEDIUM | No reason recorded |
| AI-19 | LOW | MEDIUM | Real gap with a specific trigger, partially caught (narrowed, see below) |
| ARCH-29 | LOW | MEDIUM | The hook's failure line does point at the moderator, but the script's order and message are still wrong |

**Narrowed: 6.**

| Finding | What the verifier removed | What survives |
|---|---|---|
| AI-05 | "The arbitrator isn't told." Each brief already carries an evidence-confidence section, and the arbitrator must read it | A PARTIAL passes as a finished result, and no rule caps confidence when evidence is uneven |
| AI-09 | That the failure is common or silent. It needs five or more moderators with 3–4 options each in one message, and the result is listed for review | Step 4 has no case for a spawn error. The doc text for the limit was confirmed |
| AI-19 | A re-file that drops or renames the winning option id is already caught | Changed labels, changed context and added options slip through |
| ARCH-03 | "Silently": one caller crashes loudly in 17 of 20 trials | The race, the lost entry (20 of 20) and the duplicate id (3 of 20, silent). The hat had reported 15 of 20 lost, 7 with duplicate ids |
| ARCH-14 | The generic `NEEDS_INPUT` row does apply to the moderator | Moderator BLOCKED returns are unhandled, and the 0c re-spawn loop is real |
| TEST-08 | A non-security INCOMPLETE passing is the protocol's design. A security INCOMPLETE with no hardened option already fails, as INVALID (ARCH-10) | A security INCOMPLETE that names a `hardened_default` passes. No signal maps it to `awaiting_human`, and nothing under `/autonomous` reads it |

**Duplicates folded: 3.** V1 saw both the architect and tester hats and marked three pairs. Folding keeps the more
severe rating and the union of agents.

| Folded | Into | Shared defect |
|---|---|---|
| TEST-07 | ARCH-04 | Review reasons have no consumer under `/autonomous` |
| ARCH-07 | TEST-10 | Report exemption keyed on the `agent_state/debates/` path. V1 reproduced it with a direct file, without `..` |
| TEST-15 | ARCH-05 | A verdict isn't bound to the request version it answered |

**Duplicates not folded.** The merge folds only pairs that a verifier marks, so the 85 overstates the number of
distinct problems. The pairs below are my reading and weren't folded:

- **Verified, but by different verifiers, so neither could mark the pair:**
  - AI-01 = ARCH-02 (V2 and V1);
  - AI-03 = ARCH-01 (V2 and V1).
- **An unverified finding restating a verified one:**
  - ARCH-08 restates TEST-11;
  - ARCH-11 restates TEST-05;
  - ARCH-22 restates AI-14;
  - TEST-19 overlaps AI-01/ARCH-02, through a different channel: the verdict file on disk.
- **Both unverified:** AI-04/ARCH-13, AI-16/ARCH-20, AI-10/ARCH-31, AI-06/ARCH-12, AI-13/TEST-22.

**What verification added.**

- **AI-07: both judges could be the same model.** V2 found that on a cybersecurity flag the Opus 5.5 primary also
  falls back to Opus 4.8. Both judges could then run on one model while the file says `fable`.
- **The subagent limit, from Anthropic's sub-agents doc (fetched 2026-09-30).** V2 confirmed the 20-subagent limit
  and its "don't retry" wording, which the architect hat had flagged as unverified. The doc doesn't say whether nested
  subagents count toward the limit.
- **Background spawning.** The same doc says subagents run in the background in interactive fork mode and can't be
  asked for the foreground. That supports the premise of AI-08, but AI-08 itself wasn't in the sample.
- **TEST-14.** V1 ran `promoted()` on the three cases in the evidence, and it returned True for all three.

## 5. Plan

P0 holds every root cause that carries a verified HIGH; within RC1, only the part that removes its HIGH findings. P1
holds the rest of RC1 and the root causes whose verified findings are all MEDIUM. P2 holds the LOW root causes and the
eval. Each item lands with the regression case its findings name, built from V1's scenario table (S01, S01b, S04,
S05, S06, S06b, S07, S07b, S08, S14, S21 and the others) and expecting exit 2.

### P0

| # | Change | Where | Removes | Findings |
|---|---|---|---|---|
| P0-1 | Restrict the `agent_state/debates/` report exemption to the four debate agents and a realpath inside that directory; add test S14 | `verify-gate.sh` | RC5 | TEST-10, ARCH-07 |
| P0-2 | Fail closed on debate files that won't parse or classify. Require a v1 verdict for a v1 request. Recompute totals, gap and confidence, and key the second opinion on the result. Validate second-opinion content, and record the real model id | `debate-status.py`, arbitrator template | RC1 (its four HIGH findings) | TEST-01, TEST-02, AI-02, TEST-04, TEST-05, AI-07 |
| P0-3 | Add a needs-human class that blocks until an override exists. Count security-domain topics in `SECURITY_FAILS`. Have `/autonomous`'s Post-Phase review run `debate-status.py` and set `awaiting_human`. Make the moderator and protocol name that consumer | `debate-status.py`, `verify-gate.sh`, `autonomous.md`, `debate_moderator.md`, `debate-protocol.md` | RC2 | ARCH-04, TEST-07, TEST-03, TEST-13, TEST-08, ARCH-10 |
| P0-4 | Promote the D-NNN after the second opinion returns, and give second-opinion mode an exclusion list | `debate_moderator.md`, `debate_arbitrator.md` | RC4 | AI-01, ARCH-02 |
| P0-5 | Add a lock and a unique tmp file to `remember.sh decide`. Check promotion by the D-NNN's link line. Until both land, run one moderator at a time | `remember.sh`, `debate-status.py`, `develop-orchestrator.md` (interim) | RC6 | ARCH-03, TEST-14 |
| P0-6 | Write one shared return-handling section for every command that spawns agents, with a pass-up rule for sub-orchestrators, rows for moderator BLOCKED and for overrides, 0c before 0b, and a DL-16 lint | shared skill or `agent-common.md`, all spawning commands, `develop-orchestrator.md`, `tests/lib/debate_cases.py` | RC3 | AI-03, ARCH-01, ARCH-14, ARCH-29, ARCH-19 |

### P1

| # | Change | Where | Removes | Findings |
|---|---|---|---|---|
| P1-1 | Remaining content checks: rubric, scores, `presentation_order` and `claims_checked`. A RESOLVED verdict needs research, arguments, a transcript and an arbitrator completion line. Validate overrides and auto-resolved entries | `debate-status.py`, `verify-gate.sh` | RC1 (the rest) | TEST-12, TEST-06, TEST-09, TEST-17 |
| P1-2 | Bind each verdict to its request with `phase` and `request_sha`; a mismatch is stale and pending. Take impact and domain from the request. The moderator re-runs a stale verdict. Restrict the suffix match to legacy files | `debate-status.py`, `debate_moderator.md`, `debate_arbitrator.md`, `debate-protocol.md` | RC7 | ARCH-05, TEST-15, AI-19, TEST-16 |
| P1-3 | Add a `default_taken` field. Make `--check` block a pending non-blocking request. Add a "differs from default" reason. Flip DS-22 | `debate-protocol.md`, `step-0-orient.md`, `debate-status.py`, tests | RC8 | TEST-11, ARCH-06 |
| P1-4 | Treat a PARTIAL as an evidence gap that caps confidence. Budget subagent slots. On a limit error, re-spawn in a later message instead of recording a gap | `debate_moderator.md`, `debate_arbitrator.md`, `develop-orchestrator.md` 0c | RC9 | AI-05, AI-09 |
| P1-5 | Drop `auto-research.md` from the moderator's `skill_packs` | `debate_moderator.md` | RC10 | AI-14 |

### P2

| # | Change | Where | Removes | Findings |
|---|---|---|---|---|
| P2-1 | Report circuit-breaker counts in `debate-status.py --json`. Give completion lines one writer. Pass `PHASE` in child prompts | `debate-status.py`, the four debate agents | RC11 | ARCH-26, ARCH-28 |
| P2-2 | Add the score-pattern regex to eval R5. Then run T-007 at least three times to record a baseline before changing any effort setting (the second part comes from unverified TEST-22 and AI-13) | `agent_state/eval/suite/T-007-debate/` | RC12 | TEST-27 |

**Not in the plan.**

- **The 16 unverified findings outside the root causes.** In particular, the judge-input cluster (11 findings) should
  be verified before anyone acts on it.
- **The four hats that didn't run.** Each run hat's "For other hats" section lists leads for them that aren't covered
  above, all unverified:
  - security: whether the sdlc-guard checks only the command text, so a script could write the ledger;
  - sre: concurrent `execution.jsonl` appends, the moderator's `jq` dependency, a race in `remember.sh add`, and a
    `debate-status.py` encoding edge case.
- **The scoring discrepancy in section 6.**

After P0 lands, a re-run with the same three hats would show the score movement; `/board-review` Step 7 compares the
two runs.

## 6. Method

- **Command and run.** `/board-review` with target group `debate`, run directory `docs/board-review-2026-09-30-debate`,
  commit `77f221c` (from the `sha` file). This was a trial with `--hats ai_engineer,architect,tester`. Four of the seven
  hats didn't run: senior_dev, sre, devops and security.
- **Targets and context.** The four debate agents. Every hat also read `debate-protocol.md`, `debate-status.py`,
  `step-0-orient.md`, `develop-orchestrator.md` and `model-routing.md`.
- **Hats.** Each hat ran as one general-purpose agent with its checklist and the board-review protocol. Each read every
  target in full and reproduced runtime claims in scratch directories outside the repo:
  - tester: 26 fixtures run against the real `verify-gate.sh` and `debate-status.py`;
  - architect: scratch runs of `debate-status.py`, `remember.sh` and `verify-gate.sh`;
  - ai_engineer: Anthropic's documentation, and the local `claude --version` (2.1.285).

  The run files don't record which model the hats used.
- **Verification.** `board-review.py select` builds each verifier's input:
  - every CRITICAL and HIGH, plus a deterministic 25% sample (at least 3) of each hat's MEDIUM and LOW findings, seeded
    on run and hat;
  - severity removed and order shuffled; the verifiers didn't open the hats' files.

  Two verifiers ran, both on model `fable`; V2 reports Fable 5.1 from its system prompt:
  - V1: architect and tester, 31 findings;
  - V2: ai_engineer, 8 findings.
- **Merge.** `board-review.py merge`:
  - confirmed and narrowed findings take the verifier's severity;
  - refuted findings are dropped (there were none);
  - marked duplicates fold into their target;
  - an agent's score under a hat is its worst finding there, from CRITICAL 1 to none 5, and the average is taken
    across hats.

  No earlier debate run exists, so there's no score movement to report. `docs/board-review-2026-09-30` is the
  coding-testing run.

**Finding counts:**

| | CRITICAL | HIGH | MEDIUM | LOW | Total |
|---|---|---|---|---|---|
| Filed by the hats (AI 24, Arch 31, Test 33) | 3 | 20 | 45 | 20 | 88 |
| Sent to verification, at the hat's severity | 3 | 20 | 11 | 5 | 39 |
| After merge (`merged.json` counts) | 0 | 13 | 54 | 18 | 85 |
| ... verified | 0 | 13 | 20 | 3 | 36 |
| ... unverified, at the hat's severity | 0 | 0 | 34 | 15 | 49 |

| Hat | Filed | As filed (C/H/M/L) | Verified | Unverified |
|---|---|---|---|---|
| ai_engineer | 24 | 0 / 3 / 14 / 7 | 8 | 16 |
| architect | 31 | 0 / 7 / 18 / 6 | 13 (12 kept + ARCH-07 folded) | 18 |
| tester | 33 | 3 / 10 / 13 / 7 | 18 (16 kept + TEST-07, TEST-15 folded) | 15 |

**Scoring discrepancy.** `scorecard.md` and the `/board-review` command both describe the score as the worst *verified*
finding. But `board-review.py merge` (line 317) takes the worst of all findings, so MEDIUM and LOW findings that weren't
sampled count at the hat's severity. In this run that decides four cells:

| Cell | Score | Unverified findings behind it | On verified findings alone |
|---|---|---|---|
| debate_advocate, AI | 3 | AI-04, AI-08, AI-13 | 5 |
| debate_advocate, Arch | 3 | ARCH-13 | 4 |
| debate_researcher, AI | 3 | AI-04, AI-08, AI-13, AI-15 | 5 |
| debate_researcher, Arch | 3 | ARCH-13, ARCH-22, ARCH-23 | 4 |

The scores in this README are left as `merged.json` has them. Before runs are compared, either the code or the
description should change.
