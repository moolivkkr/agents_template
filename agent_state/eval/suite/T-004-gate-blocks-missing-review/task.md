# T-004 — Gate BLOCKS on a missing review (negative-path enforcement)
Surface: multi-phase gate | Est. cost: ~4 agents | Path: /develop-orchestrator gate (Wave 6)

## Requirement (this is a NEGATIVE test — success = the gate refuses to pass)
Drive a small phase to the gate, but with `security_reviewer` deliberately NOT run (its
`completed` line absent from `execution.jsonl` even though it is in `roster.required`). The correct
framework behavior is to **BLOCK** the gate: `verify-gate.sh` must exit non-zero, the manifest must
NOT end up with `gate.passed==true`, and the block reason must name the missing agent.

This task also seeds a second variant: a `code_review.md` report that still contains an unresolved
`BLOCKING` finding. The gate must BLOCK on that too, naming the report.

## Definition of done
- `verify-gate.sh <phase>` exits non-zero (BLOCK) for the phase.
- The block output names `security_reviewer` as the missing required agent.
- No `gate.passed==true` is written while the roster is incomplete (the "gate.passed without
  evidence" bug does NOT reproduce).
- The unresolved-BLOCKING variant is also blocked and the offending report is named.

## Why this task exists (regression class it guards)
This is the linchpin negative test: it proves the enforcement is real CODE, not prose. If a change
weakens verify-gate.sh (or un-wires it from settings.json), the gate would silently pass an
incomplete roster — this task flips from BLOCK to PASS and the regression is caught by name.
