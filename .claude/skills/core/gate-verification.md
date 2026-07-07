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
# Tests actually exist and run (not just a report claiming they do)
<test_cmd> 2>&1 | tee /tmp/gate_unit.log        # real exit code + counts
grep -c "func Test" <test_dir>/*_test.go         # test functions physically present
# Each claimed TC-* ID is annotated in a real test file
for id in $(claimed_tc_ids); do grep -rq "$id" <test_dir> || echo "⛔ $id claimed but not found"; done
# No suppression sneaked in to force a pass
grep -rE '(\.skip\(|//\s*nolint|@ts-ignore|t\.Skip\()' <changed_test_files> && echo "⚠ suppression present"
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
```

The second clause prevents a high aggregate from masking a fully-failed critical dimension
(e.g. zero acceptance tests). Write `gate_score` + the per-dimension breakdown into
`agent_state/phases/${PHASE}/reports/gate_score.md`.

---

## Layer 3 — Adversarial cross-model verification (high-stakes items)

For the highest-risk claims (security-critical code, tenant isolation, "the bug is fixed"),
run the verification on a **different model** than the one that produced the work — a model
verifying its own output shares its blind spots. Use `model-routing.md` to pick a distinct tier
(e.g. work done by sonnet → verified by opus). The verifier is prompted to **refute**:

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
