---
skill: gate-verification
description: Evidence-based, graded, cross-checked phase gate — the checklist and proof requirements that let a phase pass
version: "1.0"
tags:
  - gate
  - verification
  - evidence
  - quality
  - core
---

# Gate Verification Protocol — Evidence-Based, Graded, Cross-Checked

Phase gates historically checked "does the report file exist and mention a non-zero test
count?" That is **binary and trusts the subagent's self-report**. A subagent can write
`unit_tests.md` claiming "42 passing" without the tests existing. This protocol replaces the
binary check with three hardening layers, adapted from Metaswarm (never trust subagent
self-reports; re-verify with file:line + a different model) and ruflo's graded truth-score.

Used by: develop-orchestrator Wave 6, `/accept`, `/review`.

---

## Layer 1 — Independent re-verification with file:line evidence

The **parent/orchestrator** (not the agent being verified) independently confirms each claimed
done-item against the actual repository. Every gate item must resolve to a **file:line citation
or a re-run command output** — never the subagent's word.

Reuse the Evidence Grading Protocol (`backend_audit_agent.md`):

| Grade | Accept for gate? | Requirement |
|-------|------------------|-------------|
| **Confirmed** | ✅ | Parent observed it directly: `grep`/`test`/re-ran the command with file:line |
| **Deduced** | ⚠️ only with a logged chain | Logical chain from confirmed evidence, chain written to the gate report |
| **Hypothesized** | ❌ | Not acceptable to pass a gate — must be upgraded to Confirmed first |

Concrete re-verifications the parent runs itself (do not delegate):
```bash
# Tests actually run — the project's own command, exit code kept (a bare `| tee` would report tee's 0).
# No test:unit row (or no file) is a failure: jq -r would print "null" or nothing, and `bash -c ""` exits 0.
CMD="$(jq -er '.commands["test:unit"] // empty' agent_state/config/verify-commands.json)" \
  || { echo "⛔ no test:unit row in agent_state/config/verify-commands.json"; exit 1; }
PHASE="${PHASE:?}" bash -o pipefail -c "$CMD" 2>&1 | tee /tmp/gate_unit.log; RC=${PIPESTATUS[0]}; echo "exit=$RC"
# TC coverage the deterministic way (names of tests that ran and passed; not grep). An empty
# --diff-base makes tc-inventory skip the weakening check, so a missing base_sha stops here.
BASE="$(cat "agent_state/phases/${PHASE}/base_sha" 2>/dev/null)"
[ -n "$BASE" ] || { echo "⛔ no base_sha for phase ${PHASE}"; exit 1; }
python3 .claude/hooks/tc-inventory.py --phase "${PHASE}" --results "agent_state/phases/${PHASE}/reports/test_results.json" \
  --diff-base "$BASE" --out /tmp/gate_tc.json
# No suppression added to force a pass (tc-inventory's weakening list covers skip/only/removed asserts)
git diff -U0 "$BASE"..HEAD | grep -E '^\+.*(//[[:space:]]*nolint|@ts-ignore|eslint-disable)' && echo "⚠ suppression added"
```

If a claimed item cannot be Confirmed by the parent's own command, the gate **blocks** — the
subagent's report is treated as unproven.

---

## Layer 2 — Graded quality score (replaces binary pass/fail)

Compute a numeric `gate_score ∈ [0,1]` instead of a single boolean. The gate passes only at or
above threshold. This surfaces "technically passing but weak" phases that a binary gate hides.

Default weighted rubric (tune per project in `sdlc-config.json`):

| Dimension | Weight | Scored from |
|-----------|--------|-------------|
| Tests present & green (all tiers, real re-run) | 0.30 | Layer 1 re-run exit codes |
| TC-* coverage (implemented / specified, HIGH+MED) | 0.20 | spec_test_reconciler |
| Coverage % vs target | 0.15 | coverage tool output |
| Review findings resolved (no open HIGH) | 0.15 | code_review + security_review |
| Acceptance use cases passed | 0.15 | acceptance_report.md |
| No suppression/stub/TODO introduced | 0.05 | code_quality_verifier |

```
gate_score = Σ (dimension_score × weight)
PASS if gate_score ≥ 0.90 AND no dimension with weight ≥ 0.15 scored 0
       AND no hard failure (below)
```

The second clause prevents a high aggregate from masking a fully failed critical dimension, for
example zero acceptance tests.

**Hard failures cap the score at 0, whatever the weights say.** Before the board review, one failing
acceptance case out of eight still scored 0.98 and passed (TEST-05). The weights grade *quality among
passing phases*. They never trade a failure for points elsewhere. The hard failures are:
- any failed or flaky test in any tier;
- any HIGH/MEDIUM acceptance case that is FAIL, BLOCKED or UNTESTED;
- any HIGH/MEDIUM TC ID missing or failing in `tc-inventory`;
- any open BLOCKING review finding;
- a deploy that isn't HEALTHY;
- stale evidence.

`verify-gate.sh` enforces the same list deterministically, so Layer 2 can only ever be *stricter*. Write `gate_score` + the per-dimension breakdown into
`agent_state/phases/${PHASE}/reports/gate_score.md`.

---

## Layer 3 — Adversarial cross-model verification (high-stakes items)

For the highest-risk claims (security-critical code, tenant isolation, "the bug is fixed"),
run the verification on a **different model** than the one that produced the work — a model
verifying its own output shares its blind spots. Work is produced on Opus 5.5, so launch the verifier
with `model: fable` (see `model-routing.md`), in a fresh context that did not produce the work. The verifier is prompted to **refute**:

```
"Try to prove this claim is FALSE. Find one counterexample, one uncovered path, or one file:line
that contradicts it. Default to REFUTED if you cannot positively confirm."
```

Majority-refute → the item fails regardless of the gate_score. Reserve Layer 3 for items where
a false pass is expensive; running it on everything is wasteful.

---

## Output

Write `agent_state/phases/${PHASE}/reports/gate_score.md`:
```markdown
# Gate Verification — Phase ${PHASE}
- gate_score: 0.93  (threshold 0.90) → PASS
- Layer 1 (evidence): 12/12 items Confirmed by parent re-run
- Layer 2 (graded): [per-dimension table]
- Layer 3 (cross-model): tenant-isolation claim — verified by opus, NOT refuted
- Blocking issues: none
```
A gate may write `gate.passed` ONLY when Layer 1 has zero unproven items, `gate_score ≥ threshold`,
and no Layer 3 item was refuted.

> Config blocks checked 2026-09-30 (`bash tests/archetype-compile/config-packs/run.sh --live`): 1 bash block: bash -n (macOS bash 3.2.57) + shellcheck 0.11.0; 1 run in fixture scenarios on macOS bash 3.2.57.
