# Tester hat: debate agents (run 2026-09-30-debate, repo 77f221c)

Targets: `debate_moderator`, `debate_researcher`, `debate_advocate`, `debate_arbitrator`. 33 findings: 3 CRITICAL, 10 HIGH, 13 MEDIUM, 7 LOW (`tester.json`).

I ran every runtime claim on fixtures under `/tmp/board-tester-debate/`:
- `sim.sh` builds 26 fixtures in `fx/`. Each is a complete, otherwise clean implementation phase built with the same `full_phase` helper as `tests/verify-gate.test.sh`, plus one debate defect.
- `sim2.sh` adds the forced-gate case.
- `sim.out` holds the output of the real `verify-gate.sh 1` and `debate-status.py --check` for each fixture.
- Both committed suites pass at this commit (debate 46/46, verify-gate 53/53), even though every hole below is present.

## Verdict: top five problems

1. **The gate can't see a request it fails to parse (TEST-01).** A blocking request with a JSON syntax error, or a typo in its `schema`/`type` marker, is listed as "(ignored: …)". `--check` exits 0 and the gate passes, so the decision is never made. The moderator's own validation query returns nothing for such a request, and its instructions don't cover that case.
2. **Verdict rules are labels the gate trusts, not things it checks (TEST-02, -04, -05, -12).**
   - Leaving out the `schema` key turns off every v2 check: ledger promotion, second opinion, hardened default, status and scores. The arbitrator's own Definition of Done still passes.
   - Writing `"confidence": "HIGH"` on a 0.1-point gap skips the Fable second opinion.
   - An empty `second-opinion.json` (`{}`) clears the second-opinion block.
   - Nothing checks the rubric, the per-option and per-criterion scores, `presentation_order` or `claims_checked`.
3. **A weaker security choice passes, and nobody reads the review notes (TEST-03, -07, -08).**
   - A MEDIUM-confidence security verdict that isn't the hardened default passes, even when the independent Fable judge chose the hardened option.
   - INCOMPLETE verdicts pass.
   - The protocol sends all of these to "the checkpoint". But `/autonomous` reads only `auto-resolved.jsonl`, which the debate path never writes, and Wave 6 step 0c doesn't show review reasons. These notes are emitted but nobody reads them.
4. **A verdict passes even if no debate ran (TEST-06, -09, -18).**
   - A `verdict.json` with no research, arguments, transcript or arbitrator completion line passes, so the requesting agent can unblock itself.
   - A one-key `override.json` silences a pending or invalid request.
   - Empty research briefs and arguments pass. The gate says check (f) validates them, but check (f) never opens a `.md` file.
5. **The debate exemption reopens "the gate passed a FAIL report" (TEST-10).** `verify-gate.sh:359-361` skips report validation for any path that starts with `agent_state/debates/`, and it runs before the test-agent sidecar branch. A `test_runner` with a FAIL sidecar, logged as `agent_state/debates/../phases/1/reports/test_runner.md`, passes the gate (S14). The control with a normal path blocks (S14c). This brings back defect class 1 from the 2026-09-30 run.

Also notable:
- **TEST-11:** a non-blocking request that was never debated passes the gate. The protocol, step-0 and Wave 6 all say it must be debated first, yet tests DS-22 and verify-gate:354 assert that it passes.
- **TEST-13:** a pending security-domain debate can be force-gated under `/autonomous` without per-finding acknowledgement, the pattern SEC-01 closed for security findings.

Status of the 2026-09-30 defect classes for these targets:

| Defect class | Status |
|---|---|
| Gate passed FAIL reports | Reopened through the debates-path exemption (TEST-10) |
| Stale evidence | Analogue present: a verdict isn't bound to the request it answered (TEST-15), and benchmark age isn't recorded (TEST-25) |
| TC counted by string | Not applicable to these agents |
| E2E before deploy | Not applicable to these agents |
| FLAKY routed to re-run | Analogue present: a re-spawned arbitrator overwrites the first verdict (TEST-33) |

## Missing entirely

- **Validating verdict content against the rubric.** Searched `debate-status.py` (`verdict_problems`, `verdict_review`, `blocking_reason`) and `verify-gate.sh` check (f). Neither reads `rubric`, `presentation_order`, `claims_checked` or `gap`, or checks per-criterion scores.
- **Proof of who wrote a verdict.** Nothing ties `verdict.json` to a `debate_arbitrator` run: no line in `execution.jsonl`, and no check in either hook. Debate agents aren't in the roster (`verify-gate.sh` floor lists, lines 224-237).
- **Proof that research and advocacy happened.** No check anywhere for `research-<opt>.md`, `argument-<opt>.md` or `transcript.md`. The only one is a single grep in eval T-007.
- **Binding a verdict to its request.** No request hash or version in the verdict format (`debate-protocol.md:107-139`).
- **A measured eval for the judging agents.** T-007 exists but has never run. The only baseline (`2026-07-07-seed.json`) is unmeasured and has no T-007 entry, and `agent_state/eval/runs/` is empty. T-007 also covers only clear-cut MUST-driven calls (TEST-22, -23, -24).
- **Consumption of debate review reasons under `/autonomous`.** `grep debate-status .claude/commands/autonomous.md` returns no matches (TEST-07).
- **Negative tests.** `tests/lib/debate_cases.py` and `tests/verify-gate.test.sh` have no case for any of the fixtures above (TEST-26). The fixtures in `sim.sh`/`sim2.sh` are ready to port.

Checklist items that don't apply:
- **The right environment (item 4):** debates run against documents and the web, not a deployed build.
- **Oracles (item 6):** T-007 takes its expected answers from seeded BRD rows, not from the agents' output. That part is sound.

## For other hats

- **architect / senior_dev:** The orchestrator's `NEEDS_DECISION` row (`develop-orchestrator.md:284`) handles only a moderator `COMPLETE`. A moderator `BLOCKED` (an active D-NNN already decides it, an invalid request, or the wrong spawn depth) leaves the request pending, with no instruction to withdraw it or send it back. Under `/autonomous` that path ends in the force-gate (TEST-13).
- **security:**
  - The sdlc-guard refused a `docs/DECISIONS.md` write inside a `/tmp` fixture when the command was a one-liner. Earlier, `bash /tmp/board-tester-debate/sim.sh` wrote the same kind of fixture file (`/tmp/.../docs/DECISIONS.md`) without being stopped. The guard appears to inspect the command text rather than the files a script writes, so a script could edit the real ledger. I didn't test this against the repo's ledger, because the repo is read-only for this run.
  - Separately, the protocol says the parent writes `override.json` "when the user overrides". Nothing checks a person's approval, so an agent can write it (see TEST-09).
- **ai_engineer:**
  - `debate_advocate.md:27-29` ("argue for it even if another option looks better") pulls against DoD line 152 ("if the evidence genuinely does not support my assigned option, I say so"). Whether that produces hedged arguments needs an eval.
  - The researcher's "at most 10 web searches" is neither counted nor checked.
  - The effort settings (medium/medium/medium/high) were never measured (TEST-22).
- **sre:** `debate-status.py` reads `docs/DECISIONS.md` with `open()` and no encoding argument (line 222). [unverified: Python 3.7+ coerces the C locale to UTF-8, so this may never happen] A non-UTF-8 locale on CI could make the gate crash, which still blocks (exit not 0 or 2, so "debate-status.py failed"). That's the fail-closed direction, but a confusing failure.
