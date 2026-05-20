---
command: reset-phase
description: "Reset a phase for re-development with proper state management. Archives current state, creates safety tags, and prepares for a clean re-run."
arguments:
  - name: phase
    required: true
    description: "Phase number to reset (e.g. 1, 2, 3)"
  - name: hard
    required: false
    default: false
    description: "Hard reset — also resets code to end of previous phase. Requires user confirmation."
---

# /reset-phase — Safe Phase Reset for Re-Development

Reset a phase for re-development with proper state management. All operations are non-destructive — git history is always preserved via tags.

## Usage

```
/reset-phase --phase=N         # Soft reset (keep code, archive state)
/reset-phase --phase=N --hard  # Hard reset (reset code to Phase N-1 boundary)
```

---

## Soft Reset (default)

Preserves all code changes. Agents will build on existing implementation during re-development.

### Steps

1. **Safety tag:**
   ```bash
   git tag "phase-${PHASE}-attempt-$(date +%Y%m%d%H%M%S)" -m "Pre-reset snapshot for Phase ${PHASE}"
   ```

2. **Archive current phase state:**
   ```bash
   TIMESTAMP=$(date +%Y%m%d%H%M%S)

   # Archive reports (preserve for comparison)
   if [ -d "agent_state/phases/${PHASE}/reports" ]; then
     mv "agent_state/phases/${PHASE}/reports" "agent_state/phases/${PHASE}/reports.archived-${TIMESTAMP}"
   fi

   # Archive agent manifests
   for agent_dir in agent_state/phases/${PHASE}/*/; do
     if [ -d "$agent_dir" ] && [ "$(basename $agent_dir)" != "reports" ] && [ "$(basename $agent_dir)" != "test-data" ]; then
       mv "$agent_dir" "${agent_dir%.*/}.archived-${TIMESTAMP}/"
     fi
   done
   ```

3. **Remove gate pass:**
   ```bash
   rm -f "agent_state/phases/${PHASE}/gate.passed"
   ```

4. **Clear ready signals:**
   ```bash
   rm -f agent_state/phases/${PHASE}/.*_ready
   ```

5. **Archive manifest (keep for diff comparison):**
   ```bash
   if [ -f "agent_state/phases/${PHASE}/manifest.json" ]; then
     mv "agent_state/phases/${PHASE}/manifest.json" "agent_state/phases/${PHASE}/manifest.json.archived-${TIMESTAMP}"
   fi
   ```

6. **Clear debate state for this phase:**
   ```bash
   # Archive, don't delete — debates contain valuable decision context
   if ls agent_state/debates/*-verdict.json 1>/dev/null 2>&1; then
     mkdir -p "agent_state/debates/archived-${TIMESTAMP}"
     mv agent_state/debates/*-verdict.json "agent_state/debates/archived-${TIMESTAMP}/" 2>/dev/null
     mv agent_state/debates/*-transcript.md "agent_state/debates/archived-${TIMESTAMP}/" 2>/dev/null
   fi
   ```

### After soft reset

```
✅ Phase ${PHASE} soft reset complete

  Tagged:    phase-${PHASE}-attempt-${TIMESTAMP}
  Archived:  reports, manifests, debate verdicts
  Removed:   gate.passed, ready signals
  Code:      PRESERVED (agents will build on existing implementation)

  ▶ Next: /develop --phase=${PHASE}
```

---

## Hard Reset (`--hard`)

Resets code to the state at the end of Phase N-1. Use when the implementation is fundamentally wrong and needs a clean start.

### Confirmation Required

```
⚠ HARD RESET — Phase ${PHASE}

This will:
  1. Create a safety tag (all work preserved in git history)
  2. Archive ALL phase state
  3. Reset code to end of Phase $((PHASE-1))
  4. Preserve staging area for your review

Type "confirm" to proceed, or "cancel" to abort.
```

**Wait for explicit user confirmation. Do NOT proceed without it.**

### Steps (after confirmation)

1. **Safety tag (same as soft reset):**
   ```bash
   git tag "phase-${PHASE}-attempt-$(date +%Y%m%d%H%M%S)" -m "Pre-hard-reset snapshot for Phase ${PHASE}"
   ```

2. **Archive ALL phase state (same as soft reset steps 2-6)**

3. **Reset code to Phase N-1 boundary:**
   ```bash
   # Find the Phase N-1 completion tag
   PREV_TAG=$(git tag -l "phase-$((PHASE-1))-complete" | head -1)

   if [ -z "$PREV_TAG" ]; then
     echo "⚠ No phase-$((PHASE-1))-complete tag found."
     echo "  Available tags: $(git tag -l 'phase-*' | tr '\n' ' ')"
     echo "  Cannot hard reset without a target tag. Use soft reset instead."
     exit 1
   fi

   # Soft reset preserves staging area for review
   git reset --soft "$PREV_TAG"
   echo "Code reset to ${PREV_TAG}. Changes are staged for your review."
   ```

4. **Clear all phase artifacts:**
   ```bash
   # Remove reconciliation data
   rm -rf "agent_state/reconciliation/phase-${PHASE}"

   # Remove phase directory (archived copies still exist)
   # Actually, keep the directory with archived data for reference
   ```

### After hard reset

```
✅ Phase ${PHASE} hard reset complete

  Tagged:    phase-${PHASE}-attempt-${TIMESTAMP}
  Archived:  ALL phase state preserved in archived-${TIMESTAMP} directories
  Code:      Reset to phase-$((PHASE-1))-complete (changes staged for review)

  ⚠ Review staged changes with: git diff --cached
  ⚠ Specs may need updating. Consider running /plan --phase=${PHASE} first.

  ▶ Next: /plan --phase=${PHASE}  (if specs need updating)
  ▶   or: /develop --phase=${PHASE}  (if specs are still valid)
```

---

## Safety Guarantees

1. **NEVER deletes git history** — always creates a tag before any operation
2. **ALWAYS creates a safety tag** — even soft resets create a tagged snapshot
3. **Archives, never deletes** — all previous reports/manifests moved to timestamped directories
4. **Requires confirmation for --hard** — code reset is never automatic
5. **Preserves staging area** — hard reset uses `git reset --soft` so you can review what was removed
6. **Idempotent** — running reset-phase twice on the same phase is safe (second run archives the empty state)

---

## Recovery

If a reset was a mistake:

```bash
# Find the pre-reset tag
git tag -l "phase-${PHASE}-attempt-*" | sort | tail -1

# Restore to that point
git reset --hard <tag-name>

# Restore archived state
TIMESTAMP=<timestamp from tag>
mv "agent_state/phases/${PHASE}/reports.archived-${TIMESTAMP}" "agent_state/phases/${PHASE}/reports"
mv "agent_state/phases/${PHASE}/manifest.json.archived-${TIMESTAMP}" "agent_state/phases/${PHASE}/manifest.json"
touch "agent_state/phases/${PHASE}/gate.passed"
```
