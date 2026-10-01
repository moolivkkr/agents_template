<!-- Part of /develop (~/.claude/commands/startup/develop.md). Read when executing this step. -->

## Step 0.5 — Implementation Readiness Gate (HARD GATE)

**Before ANY implementation starts, verify these prerequisites.** This prevents wasted implementation cycles when specs are incomplete or misaligned.

```bash
# Check 1: Specs exist for this phase
SPECS_DIR="docs/design/phases/${PHASE:?}/specs"
SPEC_COUNT=0
for s in "$SPECS_DIR"/*.md; do [ -f "$s" ] && SPEC_COUNT=$((SPEC_COUNT + 1)); done
if [ "$SPEC_COUNT" -eq 0 ]; then
  echo "⛔ BLOCKED: No specs found at ${SPECS_DIR}/. Run /plan --phase=${PHASE} first."
  exit 1
fi

# Check 2: phase_context.md exists and is non-trivial
CONTEXT_FILE="docs/design/phases/${PHASE}/phase_context.md"
if [ ! -f "$CONTEXT_FILE" ] || [ "$(wc -l < "$CONTEXT_FILE")" -lt 20 ]; then
  echo "⛔ BLOCKED: phase_context.md missing or too short. Run /plan --phase=${PHASE} first."
  exit 1
fi

# Check 3: VERIFICATION_REPORT.md exists (specs were verified against BRD)
VERIFY_FILE="docs/design/phases/${PHASE}/VERIFICATION_REPORT.md"
if [ ! -f "$VERIFY_FILE" ]; then
  echo "⛔ BLOCKED: No verification report. Run /plan --phase=${PHASE} to verify specs against BRD."
  exit 1
fi

# Check 4: BRD↔Spec reconciliation passed (no unresolved MISSING coverage). brd_spec_reconciler
# "blocks /develop if MISSING coverage found": read its Summary row "| Blocking issues | N |"
RECON_FILE="agent_state/reconciliation/phase-${PHASE}/brd_vs_specs.md"
if [ ! -f "$RECON_FILE" ]; then
  echo "⛔ BLOCKED: no BRD↔Spec reconciliation at ${RECON_FILE}. Run /plan --phase=${PHASE}."
  exit 1
fi
RECON_BLOCKING=$(sed -n -E 's/^\|[[:space:]]*Blocking issues[[:space:]]*\|[[:space:]]*([0-9]+)[[:space:]]*\|.*$/\1/p' "$RECON_FILE" | tail -1)
if [ -z "$RECON_BLOCKING" ] || [ "$RECON_BLOCKING" -gt 0 ]; then
  echo "⛔ BLOCKED: BRD↔Spec reconciliation reports ${RECON_BLOCKING:-an unreadable number of} blocking issue(s) (MISSING coverage) — fix the specs first."
  exit 1
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

> Config blocks checked 2026-09-30 (`bash tests/archetype-compile/config-packs/run.sh --live`): 1 bash block: bash -n (macOS bash 3.2.57) + shellcheck 0.11.0; 1 run in fixture scenarios on macOS bash 3.2.57 (1 also on Linux bash 5.2.37 with GNU tools).
