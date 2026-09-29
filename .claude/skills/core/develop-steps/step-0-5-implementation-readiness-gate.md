<!-- Part of /develop (~/.claude/commands/startup/develop.md). Read when executing this step. -->

## Step 0.5 — Implementation Readiness Gate (HARD GATE)

**Before ANY implementation starts, verify these prerequisites.** This prevents wasted implementation cycles when specs are incomplete or misaligned.

```bash
# Check 1: Specs exist for this phase
SPECS_DIR="docs/design/phases/${PHASE}/specs"
SPEC_COUNT=$(ls ${SPECS_DIR}/*.md 2>/dev/null | wc -l)
if [ "$SPEC_COUNT" -eq 0 ]; then
  echo "⛔ BLOCKED: No specs found at ${SPECS_DIR}/. Run /plan --phase=${PHASE} first."
  exit 1
fi

# Check 2: phase_context.md exists and is non-trivial
CONTEXT_FILE="docs/design/phases/${PHASE}/phase_context.md"
if [ ! -f "$CONTEXT_FILE" ] || [ $(wc -l < "$CONTEXT_FILE") -lt 20 ]; then
  echo "⛔ BLOCKED: phase_context.md missing or too short. Run /plan --phase=${PHASE} first."
  exit 1
fi

# Check 3: VERIFICATION_REPORT.md exists (specs were verified against BRD)
VERIFY_FILE="docs/design/phases/${PHASE}/VERIFICATION_REPORT.md"
if [ ! -f "$VERIFY_FILE" ]; then
  echo "⛔ BLOCKED: No verification report. Run /plan --phase=${PHASE} to verify specs against BRD."
  exit 1
fi

# Check 4: BRD↔Spec reconciliation passed (no unresolved MISSING coverage)
RECON_FILE="agent_state/reconciliation/phase-${PHASE}/brd_vs_specs.md"
if [ -f "$RECON_FILE" ] && grep -q "MISSING" "$RECON_FILE"; then
  echo "⚠ WARNING: BRD↔Spec reconciliation has MISSING coverage. Review before implementing."
fi

# Check 5: data-contracts.md exists (typed API response shapes)
CONTRACTS_FILE="docs/design/phases/${PHASE}/specs/data-contracts.md"
if [ ! -f "$CONTRACTS_FILE" ]; then
  echo "⚠ WARNING: data-contracts.md missing. API↔UI binding errors likely. Run /plan --phase=${PHASE} Step 2b."
fi
```

**If any check fails:** STOP. Do not proceed to Step 1. Surface the specific failure and recommend `/plan --phase=${PHASE}`.

**Anti-rationalization:** "The specs are good enough to start" → No. Incomplete specs produce incomplete implementations that fail at acceptance tests. Fix the specs first.

---
