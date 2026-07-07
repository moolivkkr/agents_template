---
command: health
description: "Diagnose pipeline state health and optionally repair issues. Checks agent_state/ integrity, manifest validity, gate consistency, and file references."
arguments:
  - name: fix
    required: false
    default: false
    description: "Attempt automatic repair of detected issues"
  - name: phase
    required: false
    description: "Check specific phase only. Omit to check all phases."
  - name: verbose
    required: false
    default: false
    description: "Show detailed check results including passing checks"
---

# /health — Pipeline State Diagnosis and Repair

Checks the integrity of `agent_state/` — manifests, gate files, file references, execution logs, and cross-phase consistency. Produces a health report and optionally repairs detected issues.

**Use when:** Something feels off — `/develop` failed mid-run, `/status` shows stale data, or you suspect corrupted state after a crash, context exhaustion, or interrupted session.

**What it does NOT do:** It does not re-run tests, re-run reviews, or re-implement code. It diagnoses and repairs *state* issues. For *code* issues, use `/diagnose`. For *pipeline failure* investigation, use `/forensics`.

---

## Anti-Rationalization Guard

| Your Internal Reasoning | Correct Response |
|---|---|
| "The manifest looks fine, I'll skip validation" | NO. Parse it, validate every field, check every reference. "Looks fine" is how corrupted state persists for 3 phases. |
| "There are only 2 phases, a full check is overkill" | NO. Cross-phase consistency bugs appear with as few as 2 phases. Run every check. |
| "The orphaned files are probably fine, I'll leave them" | Report them. Let `--fix` clean them if the user wants. Orphaned files are noise that mask real issues. |
| "I'll just check manifests and skip execution logs" | NO. Execution logs reveal interrupted agents, stuck pipelines, and retry storms. Check everything. |
| "The fix is obvious, I'll repair without `--fix` flag" | NO. `/health` is read-only by default. Only repair with explicit `--fix`. Diagnosis without repair is a feature, not a bug. |
| "gate.passed exists so the phase must be healthy" | gate.passed can exist without required reports (this exact bug has been observed). Verify ALL gate prerequisites. |

---

## Session Context Budget

> Full protocol: `.claude/skills/core/context-budget-protocol.md`. Per-step token targets below are specific to this command.

**Read discipline:** Load one phase at a time. Never load all manifests into context simultaneously. Process each phase, write findings, move to the next.

**Per-step targets:**
| Step | Target input tokens | What to load |
|------|---------------------|--------------|
| Step 0 Inventory | ~3K | directory listings only |
| Step 1 Manifest (per phase) | ~8K | manifest.json + manifest_schema.json |
| Step 2 Gate | ~5K | gate files + report file existence checks (not content) |
| Step 3 File refs (per phase) | ~5K | manifest artifact paths + filesystem checks |
| Step 4 Execution logs (per phase) | ~8K | execution.jsonl (may be large) |
| Step 5 Cross-phase | ~10K | summary data from Steps 1-4 (not raw files) |
| Step 6 Report | ~3K | compile findings, write report |

---

## Step 0 — Inventory

```bash
PHASE_ARG="${ARG_PHASE}"
TIMESTAMP=$(date +%Y%m%d%H%M%S)

# List all phases
if [ -n "$PHASE_ARG" ]; then
  PHASES=($PHASE_ARG)
else
  PHASES=$(ls -d agent_state/phases/*/ 2>/dev/null | grep -oP 'phases/\K\d+' | sort -n)
fi

# Sessions directory (if exists)
SESSIONS=$(ls agent_state/sessions/ 2>/dev/null | head -20)

# Workstreams directory (if exists)
WORKSTREAMS=$(ls agent_state/workstreams/ 2>/dev/null | head -20)

# Uncommitted agent_state changes
git status agent_state/ --short
```

Build an inventory:
- Total phases found
- Which phases have `gate.passed`, `gate.forced`, `gate.failed`
- Which phases have `manifest.json`
- Which phases have `execution.jsonl`
- Whether `agent_state/` has uncommitted changes (potential mid-run interruption)

```
Inventory:
  Phases:      ${PHASE_LIST}
  Sessions:    ${SESSION_COUNT} (or "none")
  Workstreams: ${WORKSTREAM_COUNT} (or "none")
  Uncommitted: ${YES_OR_NO} — ${FILE_COUNT} files
```

---

## Step 1 — Manifest Integrity (per phase)

For each phase in `${PHASES}`:

### 1a. Existence and Parse
```bash
MANIFEST="agent_state/phases/${PHASE}/manifest.json"
```

- Does `manifest.json` exist? If not → **CRITICAL: manifest missing**
- Does it parse as valid JSON? (`jq . < manifest.json`) If not → **CRITICAL: manifest is invalid JSON**
- If manifest doesn't exist, skip remaining manifest checks for this phase

### 1b. Schema Validation
Compare manifest against `agent_state/manifest_schema.json`:

- Are all required fields present? (`phase`, `goal`, `started_at`, `completed_at`, `attempt`, `brd_requirements_met`, `test_results`, `artifacts`, `known_issues`, `carried_forward`)
- Are field types correct? (`phase` is integer, `brd_requirements_met` entries match `^(FR|NFR|OBJ)-`)
- Are test_results entries valid? (`status` is one of: `passed`, `failed`, `skipped`)
- Are `known_issues[].severity` values valid? (`critical`, `high`, `medium`, `low`, `gate_override`)

### 1c. Source File References
For each file in `artifacts.code[]`:
- Does the file exist in the codebase?
- If not → **WARNING: manifest references non-existent source file: ${PATH}**

### 1d. Test File References
For each `test_results` entry that has a `report` field:
- Does the referenced report file exist?
- If not → **WARNING: test report referenced but missing: ${PATH}**

### 1e. Component Completeness
For each component entry in the manifest (if components are tracked):
- Does it have source files listed?
- Does it have test files listed?
- Does it have BRD requirements mapped?

Findings per phase:
```
Phase ${PHASE} manifest:
  Exists:     ✅ | ❌
  Valid JSON:  ✅ | ❌
  Schema:      ✅ | ❌ (N violations)
  Source refs:  ✅ | ⚠ (N missing files)
  Test refs:    ✅ | ⚠ (N missing reports)
```

---

## Step 2 — Gate Consistency

For each phase:

### 2a. Gate Prerequisites
If `gate.passed` exists, verify ALL required reports exist:
```bash
REQUIRED_REPORTS=(
  "agent_state/phases/${PHASE}/reports/unit_tests.md"
  "agent_state/phases/${PHASE}/reports/e2e_results.md"
  "agent_state/phases/${PHASE}/reports/code_quality_review.md"
  "agent_state/phases/${PHASE}/reports/acceptance_report.md"
  "agent_state/phases/${PHASE}/reports/collective_feedback.md"
)

# Also check for older naming conventions
ALTERNATE_REPORTS=(
  "agent_state/phases/${PHASE}/reports/integration_tests.md"
  "agent_state/phases/${PHASE}/reports/code_review_I.md"
  "agent_state/phases/${PHASE}/reports/code_review_II.md"
  "agent_state/phases/${PHASE}/reports/security_review.md"
)

MISSING_COUNT=0
for report in "${REQUIRED_REPORTS[@]}"; do
  if [ ! -f "$report" ]; then
    echo "⚠ gate.passed exists but missing: $report"
    MISSING_COUNT=$((MISSING_COUNT + 1))
  fi
done
```

- If gate.passed exists but reports are missing → **CRITICAL: gate passed without evidence**

### 2b. Forced Gate Documentation
If `gate.forced` exists:
- Does it contain a reason? (non-empty file with explanation)
- If empty → **WARNING: gate.forced exists but no reason documented**

### 2c. Gate Timestamp Ordering
Compare gate file timestamps across phases:
- Phase N gate timestamp should be AFTER Phase N-1 gate timestamp
- If not → **WARNING: Phase ${N} gate is older than Phase ${N-1} gate (out-of-order execution?)**

### 2d. Stale Incomplete Runs
For each phase WITHOUT `gate.passed`:
- Do report files exist? (evidence of a run that didn't complete)
- Does `execution.jsonl` show a `pipeline_start` without a `pipeline_complete`?
- If reports exist but no gate → **INFO: Phase ${PHASE} has reports but no gate (incomplete run)**

---

## Step 3 — File Reference Integrity

### 3a. Spec References
If `docs/design/phases/${PHASE}/PHASE_PLAN.md` exists:
- For each spec file mentioned: does it exist at the referenced path?
- If not → **WARNING: PHASE_PLAN.md references non-existent spec: ${PATH}**

### 3b. Data Contract Currency
If `docs/design/phases/${PHASE}/specs/data-contracts.md` exists:
- Is its modification time older than the implementation files in the manifest?
- If implementation files are significantly newer → **INFO: data contracts may be stale**

### 3c. Manifest Source Verification
For each source file listed in `manifest.artifacts.code[]`:
- Does it exist in the codebase?
- If not → **CRITICAL: manifest references deleted source file: ${PATH}**
- Has it been modified since the gate was passed? (potential untracked hotfix)
- If modified after gate → **INFO: ${PATH} modified after gate.passed**

### 3d. Orphaned Reports
For each file in `agent_state/phases/${PHASE}/reports/`:
- Is it referenced by the manifest or gate evaluation?
- If not → **INFO: orphaned report file: ${PATH}**
- Check for `*.archived-*` directories — these are expected from `/reset-phase`

---

## Step 4 — Execution Log Analysis

For each phase with `execution.jsonl`:

### 4a. Structural Validity
```bash
EXEC_LOG="agent_state/phases/${PHASE}/execution.jsonl"
```

- Does every line parse as valid JSON?
- If not → **WARNING: execution.jsonl has ${N} malformed lines**

### 4b. Incomplete Entries
For every `"status":"started"` entry:
- Is there a corresponding `"status":"completed"` or `"status":"failed"` entry for the same agent?
- If not → **WARNING: agent ${AGENT} started but never completed/failed (interrupted?)**

### 4c. Duration Anomalies
For every completed entry:
- Duration > 1800s (30 minutes) → **WARNING: ${AGENT} took ${DURATION}s — potential context exhaustion or hang**
- Duration < 1s → **INFO: ${AGENT} completed in <1s — may have short-circuited**

### 4d. Repeated Failures
Count failures per agent:
- Same agent failed >3 times → **WARNING: ${AGENT} failed ${COUNT} times — systemic issue**

### 4e. Pipeline Completion
- Does a `pipeline_complete` entry exist?
- If `pipeline_start` exists but no `pipeline_complete` → **CRITICAL: pipeline started but never completed**

---

## Step 5 — Cross-Phase Consistency

Only runs when checking multiple phases.

### 5a. Artifact Continuity
- Do Phase N manifests reference Phase N-1 artifacts correctly?
- Are base schemas, services, and routes from Phase N-1 present as expected imports in Phase N code?

### 5b. Carried Forward Items
For each `carried_forward[]` item in Phase N-1 manifest:
- Is it acknowledged in Phase N? (either resolved or carried forward again)
- Items carried forward for >2 phases → **WARNING: ${ISSUE} has been carried forward for ${COUNT} phases — may be ignored**

### 5c. Test Count Progression
Compare test counts across phases:
- Unit test total should be non-decreasing (Phase N >= Phase N-1)
- If Phase N has fewer tests than Phase N-1 → **WARNING: test count regression — Phase ${N} has ${COUNT} tests vs Phase ${N-1}'s ${PREV_COUNT}**

### 5d. Requirement Coverage Progression
- `brd_requirements_met[]` should be non-decreasing across phases (once met, not un-met)
- If a requirement was met in Phase N-1 but not listed in Phase N → **WARNING: ${REQ} was met in Phase ${N-1} but not in Phase ${N} — possible regression**

---

## Step 5.5 — Memory Hygiene

Check all persistent memory stores for stale, orphaned, or redundant entries.

### 5.5a. Stale Session Snapshots

```bash
SESSION_BASE="agent_state/sessions"
if [ -d "$SESSION_BASE" ]; then
  NOW=$(date +%s)
  for thread_dir in "$SESSION_BASE"/*/; do
    [ -d "$thread_dir" ] || continue
    THREAD_NAME=$(basename "$thread_dir")
    LATEST="${thread_dir}LATEST.md"
    if [ -f "$LATEST" ]; then
      LATEST_MTIME=$(stat -f %m "$LATEST" 2>/dev/null || stat -c %Y "$LATEST")
      DAYS_OLD=$(( (NOW - LATEST_MTIME) / 86400 ))
      if [ "$DAYS_OLD" -gt 30 ]; then
        echo "WARNING: Session thread '${THREAD_NAME}' is ${DAYS_OLD} days old — likely abandoned"
      elif [ "$DAYS_OLD" -gt 7 ]; then
        echo "INFO: Session thread '${THREAD_NAME}' is ${DAYS_OLD} days old"
      fi

      # Check if paused phase gate has since passed (session is moot)
      PAUSE_PHASE=$(grep "^\- \*\*Phase:\*\*" "$LATEST" | sed 's/.*\*\* //')
      if [ -n "$PAUSE_PHASE" ] && [ -f "agent_state/phases/${PAUSE_PHASE}/gate.passed" ]; then
        echo "INFO: Session '${THREAD_NAME}' paused on Phase ${PAUSE_PHASE}, but that gate has since passed — session is moot"
      fi
    fi

    # Count historical snapshots
    SNAPSHOT_COUNT=$(ls "${thread_dir}"*-pause.md 2>/dev/null | wc -l | tr -d ' ')
    if [ "$SNAPSHOT_COUNT" -gt 10 ]; then
      echo "INFO: Session '${THREAD_NAME}' has ${SNAPSHOT_COUNT} pause snapshots — consider pruning old ones"
    fi
  done
fi
```

### 5.5b. Stale Codebase Knowledge

```bash
CODEBASE_DIR="agent_state/codebase"
if [ -d "$CODEBASE_DIR" ] && [ -f "$CODEBASE_DIR/.last-mapped" ]; then
  MAP_MTIME=$(stat -f %m "$CODEBASE_DIR/.last-mapped" 2>/dev/null || stat -c %Y "$CODEBASE_DIR/.last-mapped")
  NOW=$(date +%s)
  DAYS_OLD=$(( (NOW - MAP_MTIME) / 86400 ))

  # Compare against recent git activity
  COMMITS_SINCE=$(git log --oneline --since="$(date -r $MAP_MTIME '+%Y-%m-%d' 2>/dev/null || date -d @$MAP_MTIME '+%Y-%m-%d')" 2>/dev/null | wc -l | tr -d ' ')
  FILES_CHANGED=$(git diff --name-only "$(git log --format=%H -1 --before="$(date -r $MAP_MTIME '+%Y-%m-%dT%H:%M:%S' 2>/dev/null || date -d @$MAP_MTIME '+%Y-%m-%dT%H:%M:%S')")" HEAD 2>/dev/null | wc -l | tr -d ' ')

  if [ "$DAYS_OLD" -gt 30 ] || [ "$FILES_CHANGED" -gt 50 ]; then
    echo "WARNING: Codebase mapping is ${DAYS_OLD} days old with ${FILES_CHANGED} files changed since — run /map --incremental to refresh"
  elif [ "$DAYS_OLD" -gt 7 ] && [ "$FILES_CHANGED" -gt 20 ]; then
    echo "INFO: Codebase mapping is ${DAYS_OLD} days old with ${FILES_CHANGED} files changed — consider /map --incremental"
  fi
fi
```

### 5.5c. Stale Execution Logs

```bash
for phase_dir in agent_state/phases/*/; do
  [ -d "$phase_dir" ] || continue
  PHASE_NUM=$(basename "$phase_dir")
  EXEC_LOG="${phase_dir}execution.jsonl"

  if [ -f "$EXEC_LOG" ] && [ -f "${phase_dir}gate.passed" ]; then
    LOG_SIZE=$(wc -l < "$EXEC_LOG" | tr -d ' ')
    if [ "$LOG_SIZE" -gt 500 ]; then
      echo "INFO: Phase ${PHASE_NUM} execution.jsonl has ${LOG_SIZE} lines — consider archiving (gate already passed)"
    fi
  fi
done
```

### 5.5d. Orphaned Decision Logs

```bash
if [ -d "agent_state/debates" ]; then
  for debate in agent_state/debates/*.json; do
    [ -f "$debate" ] || continue
    [[ "$debate" == *-verdict.json ]] && continue
    [[ "$debate" == *unresolved.json ]] && continue
    VERDICT="${debate%-*}-verdict.json"
    DEBATE_MTIME=$(stat -f %m "$debate" 2>/dev/null || stat -c %Y "$debate")
    DAYS_OLD=$(( ($(date +%s) - DEBATE_MTIME) / 86400 ))
    if [ ! -f "$VERDICT" ] && [ "$DAYS_OLD" -gt 14 ]; then
      echo "WARNING: Unresolved debate '$(basename $debate)' is ${DAYS_OLD} days old — resolve or archive"
    fi
  done
fi
```

### 5.5e. Ground-Truth Reading Invariant (agent definitions)

Every agent definition MUST reference `docs/PROJECT_FACTS.md` (ground-truth item 0) so spawned
subagents load Tier 0 before acting. A regression here silently blinds agents to retired/renamed
components.

```bash
MISSING_GT=0
for f in $(find .claude/agents -name '*.md' -not -name 'INVENTORY*' -not -name 'AGENT_SCHEMA*'); do
  if ! grep -q "PROJECT_FACTS.md" "$f"; then
    echo "CRITICAL: agent def missing ground-truth reading: $f"
    MISSING_GT=$((MISSING_GT+1))
  fi
done
[ "$MISSING_GT" -eq 0 ] && echo "✓ All agent definitions reference PROJECT_FACTS.md"
# Also verify generated/ copies aren't stale vs templates/ (they ship the ground-truth item):
for t in .claude/agents/templates/*.tmpl.md; do
  g=".claude/agents/generated/$(basename "$t")"
  if [ -f "$g" ] && ! diff -q "$t" "$g" >/dev/null 2>&1; then
    echo "WARNING: generated/$(basename "$g") differs from templates/ — re-sync (/init regenerates it)"
  fi
done
```

### 5.5f. Tier 0 / Tier 0.5 Invariants (facts + decisions)

**Deterministic supersession check** — the framework claims no two `active` facts share a
`(subject, relation)` key. Verify it (this is the mechanized backstop for the "deterministic"
claim in the shared-context protocol):

```bash
FACTS="docs/PROJECT_FACTS.md"
if [ -f "$FACTS" ]; then
  python3 - "$FACTS" << 'PY'
import re, sys
txt = open(sys.argv[1]).read()
# Split into fact blocks by "### F-" headings.
blocks = re.split(r'(?=^### F-)', txt, flags=re.M)
seen = {}
dupes = []
for b in blocks:
    if not b.startswith("### F-"): continue
    if not re.search(r'^- status:\s*active', b, re.M): continue
    subj = (re.search(r'^- subject:\s*(.+)$', b, re.M) or [None,None])[1]
    rel  = (re.search(r'^- relation:\s*(.+)$', b, re.M) or [None,None])[1]
    if subj and rel:
        key = (subj.strip(), rel.strip())
        if key in seen: dupes.append(key)
        seen[key] = True
if dupes:
    print("CRITICAL: two active facts share (subject,relation):", dupes,
          "— supersede one via /remember (deterministic invariant violated)")
else:
    print("✓ Tier 0 supersession invariant holds (no duplicate active subject+relation)")
PY
fi
```

**Decision-ledger aggregation check** — every debate verdict / ADR should have a `D-NNN` entry in
`docs/DECISIONS.md`; a verdict with no ledger entry means the promotion step was skipped and the
decision won't reach new sessions.

```bash
DEC="docs/DECISIONS.md"
if [ -d "agent_state/debates" ] && [ -f "$DEC" ]; then
  for v in agent_state/debates/*-verdict.json; do
    [ -f "$v" ] || continue
    base=$(basename "$v" -verdict.json)
    if ! grep -qi "$base" "$DEC"; then
      echo "WARNING: debate verdict '$base' has no D-NNN entry in docs/DECISIONS.md — not promoted to durable memory"
    fi
  done
fi
```

### Memory Hygiene `--fix` Repairs

When `--fix` is set, apply these safe memory cleanups:

1. **Archive moot sessions** — sessions whose paused phase gate has passed
   ```bash
   mkdir -p "agent_state/sessions/archived-${TIMESTAMP}"
   mv "${thread_dir}" "agent_state/sessions/archived-${TIMESTAMP}/${THREAD_NAME}"
   ```

2. **Prune old session snapshots** — keep only the 5 most recent pause snapshots per thread, move older ones to `archived/`
   ```bash
   ls -t "${thread_dir}"*-pause.md | tail -n +6 | while read f; do
     mv "$f" "${thread_dir}archived/"
   done
   ```

3. **Archive stale execution logs** — for gated phases with >500 lines, compress the log
   ```bash
   gzip -k "${EXEC_LOG}" && mv "${EXEC_LOG}.gz" "${phase_dir}execution.jsonl.archived-${TIMESTAMP}.gz"
   # Keep original — compressed copy is for storage, original still readable
   ```

**Never auto-fix:** stale codebase mappings (must re-run `/map`), unresolved debates (require human judgment).

---

## Step 6 — Report

Compile all findings and write `agent_state/health-report.md`:

```markdown
# Pipeline Health Report
Generated: ${TIMESTAMP}
Scope: ${PHASE_ARG || "all phases"}

## Summary
| Phase | Status | Manifest | Gate | File Refs | Exec Log |
|-------|--------|----------|------|-----------|----------|
| 1     | ✅ HEALTHY | valid | passed, all reports present | all refs OK | complete |
| 2     | ⚠ WARNING | valid | passed, 1 report missing | 2 orphaned reports | 1 incomplete entry |
| 3     | ❌ BROKEN | 3 missing source files | no gate (stale run) | N/A | never completed |

## Issues (${TOTAL_COUNT})

### ❌ CRITICAL (${CRITICAL_COUNT})
- Phase 3: manifest references 3 source files that no longer exist
- Phase 3: pipeline started but never completed

### ⚠ WARNING (${WARNING_COUNT})
- Phase 2: gate.passed exists but acceptance_report.md missing
- Phase 2: execution.jsonl has 1 incomplete agent entry
- Phase 2: 2 orphaned report files in reports/ directory

### ℹ INFO (${INFO_COUNT})
- Phase 1: data-contracts.md older than implementation files
- Phase 2: user_service.go modified after gate.passed

## Cross-Phase
- Carried forward: ${CARRIED_COUNT} items across all phases
- Test progression: ${INCREASING | REGRESSION_DETECTED}
- Requirement coverage: ${MET_COUNT}/${TOTAL_REQ} FR-* requirements met

## Memory Hygiene
- Sessions: ${STALE_SESSION_COUNT} stale, ${MOOT_SESSION_COUNT} moot (phase gate passed)
- Codebase mapping: ${FRESH | STALE (N days, N files changed)}
- Execution logs: ${LARGE_LOG_COUNT} oversized logs (gated phases)
- Debates: ${UNRESOLVED_DEBATE_COUNT} unresolved (${OLD_DEBATE_COUNT} older than 14 days)

## Repair Recommendations
${IF_FIX_NOT_SET}
Run /health --fix to attempt automatic repair of:
- Remove ${N} orphaned report files
- Update manifest to remove ${N} deleted file references
- Mark ${N} incomplete execution entries as "interrupted"
${END_IF}
```

### Console Output

```
Pipeline Health Check
═══════════════════════

  Phase 1:  ✅ HEALTHY (manifest valid, gate passed, all refs OK)
  Phase 2:  ⚠ WARNING (2 orphaned reports, 1 stale file ref)
  Phase 3:  ❌ BROKEN (manifest missing 3 source files, gate has no reports)

  Overall:  ❌ 1 BROKEN, 1 WARNING, 1 HEALTHY

  Issues found: 6
    ❌ CRITICAL: 3 source files referenced in Phase 3 manifest no longer exist
    ❌ CRITICAL: Phase 3 pipeline started but never completed
    ⚠ WARNING: Phase 2 gate.passed exists but acceptance_report.md missing
    ⚠ WARNING: Phase 2 execution.jsonl has 1 incomplete entry
    ℹ INFO: Phase 2 has 2 orphaned report files not in manifest
    ℹ INFO: Phase 1 data-contracts.md may be stale

  Report: agent_state/health-report.md
  Run /health --fix to attempt automatic repair
```

---

## Repair Mode (`--fix`)

When `--fix` flag is set, after completing all diagnostic steps, apply repairs:

### Safe Repairs (automatic)

1. **Remove orphaned reports** — report files in `reports/` not referenced by manifest or gate
   ```bash
   # Move to orphaned/ subdirectory (don't delete)
   mkdir -p "agent_state/phases/${PHASE}/reports/orphaned-${TIMESTAMP}"
   mv "${ORPHANED_FILE}" "agent_state/phases/${PHASE}/reports/orphaned-${TIMESTAMP}/"
   ```

2. **Update manifest — remove dead file references** — entries in `artifacts.code[]` pointing to files that no longer exist
   ```bash
   # Read manifest, filter out non-existent paths, write back
   jq '.artifacts.code = [.artifacts.code[] | select(. as $f | $f | test(".*") and (input_line_number > 0))]' ...
   ```
   Actually: read manifest, check each path, remove entries where file doesn't exist, write updated manifest.

3. **Fix incomplete execution entries** — `started` entries with no `completed`/`failed`
   ```bash
   # Append a synthetic failed entry
   echo '{"ts":"'$(date -u +%Y-%m-%dT%H:%M:%SZ)'","agent":"'${AGENT}'","phase":'${PHASE}',"step":"unknown","status":"failed","error":"interrupted — detected by /health --fix","attempt":1}' >> "${EXEC_LOG}"
   ```

4. **Document missing gate reports** — if gate.passed exists but a required report is missing, add a placeholder report
   ```bash
   # Write a placeholder noting the gap
   cat > "${MISSING_REPORT}" << 'EOF'
   # ${REPORT_NAME} — Not Generated

   > This placeholder was created by `/health --fix` because gate.passed exists
   > but this required report was never generated. This indicates the gate was
   > passed without full evidence.
   >
   > To generate proper evidence, run:
   >   /review --phase=${PHASE}  (for review reports)
   >   /test --phase=${PHASE}    (for test reports)
   EOF
   ```

5. **Archive moot sessions** — session threads whose paused phase gate has since passed
   ```bash
   mkdir -p "agent_state/sessions/archived-${TIMESTAMP}"
   # Move entire thread directory to archive
   mv "${thread_dir}" "agent_state/sessions/archived-${TIMESTAMP}/${THREAD_NAME}"
   ```

6. **Prune old session snapshots** — keep only 5 most recent pause snapshots per active thread
   ```bash
   mkdir -p "${thread_dir}archived"
   ls -t "${thread_dir}"*-pause.md | tail -n +6 | while read f; do
     mv "$f" "${thread_dir}archived/"
   done
   ```

7. **Archive oversized execution logs** — for gated phases with >500 log lines
   ```bash
   gzip -c "${EXEC_LOG}" > "${phase_dir}execution.jsonl.archived-${TIMESTAMP}.gz"
   # Truncate to last 50 entries (keep recent for quick diagnostics)
   tail -50 "${EXEC_LOG}" > "${EXEC_LOG}.tmp" && mv "${EXEC_LOG}.tmp" "${EXEC_LOG}"
   ```

### Unsafe Repairs (NEVER automatic)

- **NEVER delete source code or test files** — even if they appear orphaned
- **NEVER remove gate.passed files** — only add missing evidence
- **NEVER modify git history** — no rebase, no amend, no reset
- **NEVER auto-resolve carried_forward items** — they require human judgment

### Repair Report

After all repairs:
```
Repairs Applied:
  ✅ Moved 2 orphaned reports to reports/orphaned-${TIMESTAMP}/
  ✅ Removed 3 dead file references from Phase 3 manifest
  ✅ Marked 1 incomplete execution entry as interrupted
  ✅ Added 1 placeholder report for Phase 2 acceptance_report.md

  ⚠ Not repaired (requires manual intervention):
    - Phase 3 pipeline never completed — re-run /develop --phase=3
    - Phase 2 acceptance_report.md is a placeholder — run /test --acceptance --phase=2

  Changes are uncommitted. Review with: git diff agent_state/
  Commit with: git add agent_state/ && git commit -m "chore: /health --fix repairs"
```

---

## Rules

- `/health` is **read-only by default** — it diagnoses, it does not modify (unless `--fix`)
- Every finding must have a **severity** (CRITICAL, WARNING, INFO) and a **specific location** (phase, file)
- Never report "everything looks fine" without actually checking — enumerate what was verified
- Orphaned files are moved to a timestamped subdirectory, never deleted
- Manifest repairs remove dead references but never add new ones — only humans and `/develop` add references
- gate.passed is sacred — `/health --fix` never removes it, only adds missing evidence around it
- If `--phase` is specified, skip cross-phase consistency checks (Step 5)
- The health report is cumulative — running `/health` again overwrites `agent_state/health-report.md` with fresh results
- With `--verbose`: include passing checks in the report (not just failures)
- Without `--verbose`: only show failures and the summary line per phase
