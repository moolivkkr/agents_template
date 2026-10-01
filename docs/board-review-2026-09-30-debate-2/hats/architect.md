# Architect hat: debate team (run 2026-09-30-debate-2, repo 95fb871)

Targets: `debate_moderator`, `debate_researcher`, `debate_advocate`, `debate_arbitrator`.
34 findings: 0 CRITICAL, 3 HIGH, 20 MEDIUM, 11 LOW (the details are in `architect.json`).

I reproduced every runtime claim against a copy of `.claude/hooks/debate-status.py` and
`remember.sh` in a scratch directory, scenarios S1–S13, which the evidence fields cite.
`bash tests/dependency-graph.test.sh` passes (54/0) and reports no debate-agent IO findings. Its
frontmatter-only view can't see any of the problems below.

The defect classes from the last run are still fixed. Request and verdict names are classified by
content, and every writer uses `<topic>.request.json`. `remember.sh decide` takes a lock. The
moderator waits for its children, and the waiting text matches the current docs.

## Verdict: top five

1. **The gate proves a verdict exists, not that anyone applied it (ARCH-02, ARCH-03).** Wave 6 0c
   dispatches orphaned *blocking* requests and never relaunches the requester. Non-blocking
   requests filed during `/plan` (and `/discuss` and `/design`) have no dispatch until that same
   0c, after the code is built on the default. The 0c remedy then relaunches a spec agent, and
   Wave 5v doesn't re-check spec against code. In both paths, check (f) passes with a decision
   recorded in the ledger and not implemented in the code.
2. **The arbitrator's mandated self-check runs before the moderator writes the transcript the
   checker requires (ARCH-01).** Every first-time RESOLVED debate shows `invalid` to the
   arbitrator, which is told to fix it. It can either write the moderator's file or return a
   status the moderator mishandles. This is an ordering bug in normal use (S1).
3. **Topic-keyed paths are reused across rounds and phases, and nothing ties a round's artifacts
   together (ARCH-05, -08, -09, -20, -22).** A previous round's second opinion blocks a
   clear-cut re-run for a person (S4). An override masks every later change to the request
   (S11). A slug reused in a later phase erases the earlier phase's debate from `--phase N`
   (S7). The promotion check is satisfied by a reversed entry from an earlier round (S12).
   `/worklog` reports an overridden debate as the overridden choice (S9). The root cause is
   one: `request_sha` binds only the verdict, and the second opinion, the override, the ledger
   link and the briefs carry no round identity.
4. **The ledger can't hold "one active decision per topic" (ARCH-06, ARCH-07).** `remember.sh
   decide` has no key and supersedes only when given `--reverses`. The promote step never
   receives `PRIOR DECISION`, reset-phase drops the prior verdict, and adr_agent records its
   own entries. S8 shows two active D-NNN entries for one topic, both linking the same verdict.
5. **The moderator's return and the parents' notion of "open" disagree with the checker
   (ARCH-04, ARCH-12, ARCH-17).** Step 10 maps gate-only states (security second-opinion
   disagreement, missing second opinion, not promoted) to `COMPLETE`, so `/autonomous`
   relaunches on a verdict a person must decide (S2). `/pause` and `/health` each define
   "open" from a different status subset. A debate that stopped after the primary verdict has
   no resume path, because the moderator returns it "as is" and 0c dispatches only pending
   topics.

Next tier: auto-resolved defaults go to three different ledgers, and only one of them reaches
the gate and DECISIONS.md (ARCH-13). A security NEEDS_INPUT default recorded as child-returns
says skips the hardened check (ARCH-14, S13). `/discuss` runs a second decision mechanism that
never reaches the ledger (ARCH-15). Step-3/4 verdicts go to test agents that may not edit
product code (ARCH-16). No project-wide debate check exists at `/accept` (ARCH-18). The depth
guard is missing in projects that already had a settings.json (ARCH-21; the default of 3
layers was checked against code.claude.com/docs/en/sub-agents this session).

## Missing entirely

- **A cleanup step for a re-debated topic** that archives the previous round's research,
  arguments, second opinion and transcript. I looked in debate_moderator step 1, the protocol
  § Files, and reset-phase. Only reset-phase archives, and only for a whole phase.
- **A record that a blocking verdict was applied** (the counterpart of `default_taken`). I
  looked in debate-status.py (gate list :444-482), the protocol § Request and child-returns.
- **A round identity on the second opinion and the override** (request_sha). I looked in the
  protocol formats, arbitrator step 7 and the child-returns override section.
- **A deterministic topic key in the decision ledger.** I looked in remember.sh `decide` and
  the arbitrator step 8. The fact ledger has one (`subject, relation`); the decision ledger
  doesn't.
- **A debate check before implementation starts.** I looked in develop-orchestrator Waves 0–2
  and the ends of `/plan`, `/discuss` and `/design`: none run `debate-status.py`.
- **A whole-project `debate-status --check` before release.** I looked in accept.md's READY
  criteria (:688) and its release-notes step (:715).
- **A resume path for a debate stopped after the primary verdict** (second opinion or promote
  missing). I looked in moderator step 1 and develop-orchestrator 0c.

## For other hats

- **ai_engineer:**
  - Second-opinion independence is enforced by instruction only. The primary verdict is on disk
    while the Fable arbitrator runs. `debate-status.py --json`, which the arbitrator's step 7
    tells it to run, prints the topic's `verdict`, `verdict_label` and `confidence`. Opening the
    request JSON to learn the phase (ARCH-10) shows `initial_reasoning`.
  - Step-3 option D ("the test expectation contradicts the spec") and step-4 option D ask a
    debate to settle a fact, which protocol D9 says a debate can't do.
  - Close HIGH-impact calls have a hard dependency on one model (Fable) with no non-human
    fallback.
- **security:**
  - `/discuss --auto` auto-selects the "recommended option" for security questions; it isn't
    required to take the hardened one.
  - `remember.sh decide` writes `--decision`/`--rationale` verbatim into the ledger. A value
    containing a newline plus `### D-…` or `- link: …` could forge a block that debate-status's
    `decision_blocks()` parses. I didn't reproduce this; it belongs to the security lens.
- **tester:**
  - `tests/lib/make_debate.py` writes the transcript before the verdict, so the suite can't see
    the ordering bug (ARCH-01).
  - No test covers: a stale second opinion on a re-run (S4), an override masking a changed
    request (S11), `promoted()` accepting a reversed block (S12), a security `unresolved.json`
    entry without a domain (S13), or `context` changes not staling a verdict (S5).
- **devops:**
  - `install.sh` and `new-project.sh` never merge framework keys into an existing
    `settings.json` (env, hooks), so the depth cap and the hooks silently don't apply in adopted
    projects.
- **senior_dev:**
  - `debate-status.py --request-sha` reads only `<topic>.request.json`. A legacy-named request
    gets exit 3 instead of a hash, so the moderator can only return BLOCKED for it.
