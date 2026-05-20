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

Reset a phase for re-development. All operations non-destructive — git history preserved via tags.

```
/reset-phase --phase=N         # Soft reset (keep code, archive state)
/reset-phase --phase=N --hard  # Hard reset (reset code to Phase N-1 boundary)
```

---

## Soft Reset (default)

Preserves all code. Agents build on existing implementation during re-development.

### Steps

1. **Safety tag:**
   ```bash
   git tag "phase-${PHASE}-attempt-$(date +%Y%m%d%H%M%S)" -m "Pre-reset snapshot for Phase ${PHASE}"
   ```

2. **Archive current phase state:**
   ```bash
   TIMESTAMP=$(date +%Y%m%d%H%M%S)
   [ -d "agent_state/phases/${PHASE}/reports" ] && mv "agent_state/phases/${PHASE}/reports" "agent_state/phases/${PHASE}/reports.archived-${TIMESTAMP}"
   # Archive agent manifests (exclude reports, test-data)
   ```

3. **Remove gate pass:** `rm -f "agent_state/phases/${PHASE}/gate.passed"`

4. **Clear ready signals:** `rm -f agent_state/phases/${PHASE}/.*_ready`

5. **Archive manifest:** `mv manifest.json manifest.json.archived-${TIMESTAMP}`

6. **Archive debate state:**
   ```bash
   mkdir -p "agent_state/debates/archived-${TIMESTAMP}"
   mv agent_state/debates/*-verdict.json agent_state/debates/*-transcript.md "agent_state/debates/archived-${TIMESTAMP}/" 2>/dev/null
   ```

```
✅ Phase ${PHASE} soft reset complete
  Tagged, archived, gate removed. Code PRESERVED.
  ▶ Next: /develop --phase=${PHASE}
```

---

## Hard Reset (`--hard`)

Resets code to end of Phase N-1. Use when implementation is fundamentally wrong.

**Requires explicit user confirmation. Do NOT proceed without it.**

### Steps (after confirmation)

1. Safety tag (same as soft reset)
2. Archive ALL phase state (same as soft reset steps 2-6)
3. **Reset code to Phase N-1 boundary:**
   ```bash
   PREV_TAG=$(git tag -l "phase-$((PHASE-1))-complete" | head -1)
   [ -z "$PREV_TAG" ] && { echo "No phase-$((PHASE-1))-complete tag. Use soft reset."; exit 1; }
   git reset --soft "$PREV_TAG"  # Preserves staging area for review
   ```
4. Clear reconciliation data: `rm -rf "agent_state/reconciliation/phase-${PHASE}"`

```
✅ Phase ${PHASE} hard reset complete
  Code reset to phase-$((PHASE-1))-complete (staged for review)
  ⚠ Review: git diff --cached
  ▶ Next: /plan --phase=${PHASE} or /develop --phase=${PHASE}
```

---

## Safety Guarantees

1. NEVER deletes git history — always creates tag first
2. Archives, never deletes — timestamped directories
3. Requires confirmation for `--hard`
4. Preserves staging area — `git reset --soft`
5. Idempotent — safe to run twice

---

## Recovery

```bash
# Find pre-reset tag
git tag -l "phase-${PHASE}-attempt-*" | sort | tail -1
# Restore
git reset --hard <tag-name>
mv "agent_state/phases/${PHASE}/reports.archived-${TIMESTAMP}" "agent_state/phases/${PHASE}/reports"
mv "agent_state/phases/${PHASE}/manifest.json.archived-${TIMESTAMP}" "agent_state/phases/${PHASE}/manifest.json"
touch "agent_state/phases/${PHASE}/gate.passed"
```
