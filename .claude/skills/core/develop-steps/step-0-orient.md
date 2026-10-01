<!-- Part of /develop (~/.claude/commands/startup/develop.md). Read when executing this step. -->

## Step 0 — Orient

### Detect current phase
```bash
# Highest N with agent_state/phases/N/gate.passed. No grep -P: macOS grep rejects it (exit 2), which
# left LAST_PASSED empty and silently restarted every project at Phase 1.
LAST_PASSED=0
for g in agent_state/phases/*/gate.passed; do
  n="${g#agent_state/phases/}"; n="${n%/gate.passed}"
  case "$n" in ''|*[!0-9]*) continue ;; esac   # the unmatched glob itself, or a non-numeric dir
  if [ "$n" -gt "$LAST_PASSED" ]; then LAST_PASSED="$n"; fi
done
PHASE="${ARG_PHASE:-$((LAST_PASSED + 1))}"
echo "▶ Running Phase $PHASE"
```

### Initialize Execution Log

```bash
mkdir -p "agent_state/phases/${PHASE:?}"
echo "{\"ts\":\"$(date -u +%Y-%m-%dT%H:%M:%SZ)\",\"event\":\"pipeline_start\",\"phase\":${PHASE},\"attempt\":${ATTEMPT:-1}}" >> "agent_state/phases/${PHASE}/execution.jsonl"
```

### Failure Pattern Detection

Check if previous attempts at this phase failed at specific steps:

```bash
# Check for previous gate.failed files
SEEN_FAILURE=false
for f in "agent_state/phases/${PHASE:?}"/gate.failed*; do
  [ -e "$f" ] || continue
  if [ "$SEEN_FAILURE" = false ]; then echo "⚠ Phase ${PHASE} has previous failure(s):"; SEEN_FAILURE=true; fi
  BLOCKERS=$(python3 -c "import json,sys; d=json.load(open(sys.argv[1])); print(', '.join(b.get('gate_item','?') for b in d.get('blockers',[])))" "$f" 2>/dev/null) \
    || BLOCKERS="(unreadable — open $f)"
  echo "  - $(basename "$f"): blocked by $BLOCKERS"
done
if [ "$SEEN_FAILURE" = true ]; then echo "  → Extra scrutiny will be applied to previously-failing steps"; fi
```

When a step that previously failed is reached:
- Log: `⚠ Step ${STEP} failed in previous attempt — applying extra verification`
- For test steps: run tests TWICE (once normally, once with verbose output)
- For review steps: lower the threshold for BLOCKING (MEDIUM → BLOCKING for previously-failing areas)
- For gate: explicitly verify previously-blocking items are resolved before checking new items

### Phase Lock (Advisory)

Before starting implementation, check for and create a lock:

```bash
LOCK_FILE="agent_state/phases/${PHASE:?}/.lock"
# noclobber makes the create atomic (of two sessions starting at once, one gets the lock) and never
# overwrites a lock someone else holds
if ! ( set -C; printf '%s\n%s\n' "$(whoami)@$(hostname)" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" > "$LOCK_FILE" ) 2>/dev/null; then
  echo "⚠ Phase ${PHASE} is locked by $(head -1 "$LOCK_FILE") since $(sed -n 2p "$LOCK_FILE")"
  echo "  If this is stale, remove with: rm \"$LOCK_FILE\""
  echo "  Proceeding may cause file conflicts in agent_state/phases/${PHASE}/"
  # In --auto mode: STOP. In interactive mode: ask user to confirm.
fi
```

Release lock at the end of Step 6 (gate write):
```bash
rm -f "agent_state/phases/${PHASE}/.lock"
```

This is advisory — it warns but doesn't prevent. Two developers CAN override, but they're warned.
(`/pause` reads the lock to tell that `/develop` was running, so a resumed run meets its own lock.)

### Gate check
If PHASE > 1 and `agent_state/phases/$((PHASE-1))/gate.passed` is missing:
**STOP** — `Phase $((PHASE-1)) gate not found. Run /develop --phase=$((PHASE-1)) first.`

If `docs/design/phases/${PHASE}/INDEX.md` is missing:
**Auto-run `/plan --phase=${PHASE}` first**, then continue.

### Load previous phase context
Read `agent_state/phases/$((PHASE-1))/manifest.json` (if PHASE > 1):
- Surface `carried_forward[]` issues at the top of the Step 1 audit report
- Note existing code paths, API routes, DB schema from previous phases

### Cross-Phase Contract Validation (Phase > 1)

Before starting Phase N implementation, validate that data contracts are consistent with the previous phase's actual outputs:

1. Read `docs/design/phases/${PHASE}/specs/data-contracts.md`
2. Compare against Phase N-1 manifest's `api_routes` and `artifacts.code` to identify endpoints/fields that changed
3. If `data-contracts.md` references endpoints or fields that were modified, renamed, or removed in Phase N-1:
   - **BLOCKING** — data contracts may be stale. Re-run `/plan --phase=${PHASE}` or manually update `data-contracts.md`.
4. If Phase N specs extend an endpoint from Phase N-1 (e.g., adding fields to an existing response):
   - Verify the existing fields in `data-contracts.md` match what Phase N-1 actually implemented (check the code, not just the spec)
   - If mismatch: surface as `⚠ STALE CONTRACT: data-contracts.md says X, but Phase N-1 code returns Y`
5. **Schema evolution validation** — for endpoints that exist in BOTH Phase N-1 and Phase N contracts:
   - Phase N-1 response shape must be a **subset** of Phase N response shape (additive changes only)
   - If Phase N removes or renames a field from Phase N-1: **BLOCKING** — this breaks Phase N-1 consumers
   - If Phase N changes a field type (e.g., `string` → `number`): **BLOCKING** — type mismatch
   - If Phase N adds new required fields to a request: **WARNING** — Phase N-1 callers won't send them
   - Compare actual TypeScript interfaces from both `data-contracts.md` files, not just endpoint names
   - Surface any breaking changes: `⛔ BREAKING CHANGE: GET /users/:id field 'role' changed from string to enum — Phase N-1 code returns string`

### Breaking Change Detection (HARD BLOCK — not warning)

When comparing Phase N data-contracts.md against Phase N-1 actual implementation:

- **Field REMOVED from response** → ⛔ HARD BLOCK: `Field '${field}' was in Phase ${N-1} response but missing in Phase ${N} contract. This breaks Phase ${N-1} consumers.`
- **Field RENAMED** → ⛔ HARD BLOCK: `Field '${oldName}' renamed to '${newName}'. Phase ${N-1} consumers reference the old name.`
- **Field TYPE CHANGED** → ⛔ HARD BLOCK: `Field '${field}' changed from ${oldType} to ${newType}. Type mismatch.`
- **Field ADDED (optional)** → ✅ OK (additive, backward-compatible)
- **Field ADDED (required to request)** → ⚠ WARNING: Phase ${N-1} callers won't send this field

Hard blocks CANNOT be force-gated. Fix the contract or provide a migration path (deprecated field alias).

```bash
# Quick staleness check — BLOCKING (step 3 above): a stale contract stops the phase
if [ "${PHASE:?}" -gt 1 ]; then
  PREV_MANIFEST="agent_state/phases/$((PHASE-1))/manifest.json"
  CONTRACTS="docs/design/phases/${PHASE}/specs/data-contracts.md"
  if [ -f "$PREV_MANIFEST" ] && [ -f "$CONTRACTS" ]; then
    echo "Validating data contracts against Phase $((PHASE-1)) manifest..."
    # Extract api_routes from previous manifest and verify they still exist in contracts
    python3 - "$PREV_MANIFEST" "$CONTRACTS" "$((PHASE-1))" <<'PY' \
      || { echo "⛔ BLOCKED: data-contracts.md is stale or unreadable — re-run /plan --phase=${PHASE} or update it"; exit 1; }
import json, sys
manifest = json.load(open(sys.argv[1]))
routes = manifest.get('artifacts', {}).get('api_routes', [])
contracts = open(sys.argv[2]).read()
stale = [r for r in routes if r.split()[-1] not in contracts]
if stale:
    print('⚠ STALE CONTRACTS — routes in previous manifest not found in data-contracts.md:')
    for r in stale: print(f'  - {r}')
    sys.exit(1)
print(f'✅ Data contracts consistent with Phase {sys.argv[3]} manifest')
PY
  fi
fi
```

### Schema Evolution Validation (PHASE > 1)

Before implementation begins, validate schema compatibility across phases:

1. Load ALL previous phases' `data-contracts.md` files (not just N-1 — schema evolution can span multiple phases)
2. Load current phase's `data-contracts.md`
3. For each interface/type that exists in BOTH current and previous phases:
   a. **Field additions:** ALLOWED (backward compatible) — log as INFO
   b. **Field removals:** ⛔ BREAKING CHANGE — route to user for decision:
      - Option A: Add field back (preserve compatibility)
      - Option B: Version the endpoint (create /v2/ route)
      - Option C: Confirm removal (document in manifest as `breaking_changes[]`)
   c. **Type changes:** ⛔ BREAKING CHANGE — same routing as removals
   d. **Array↔Object changes:** ⛔ CRITICAL BREAKING CHANGE — must version endpoint
4. Output: `agent_state/phases/${PHASE}/reports/schema_evolution.md`
5. Add to manifest: `"breaking_changes": [{"field": "...", "action": "removed|type_changed", "resolution": "versioned|confirmed|restored"}]`

```bash
# Schema evolution validation — writes reports/schema_evolution.md (read by Breaking Change
# Propagation below and by the force-gate refusal in Step 6) and BLOCKS on any breaking change
if [ "${PHASE:?}" -gt 1 ]; then
  echo "Validating schema evolution across all previous phases..."
  CURRENT_CONTRACTS="docs/design/phases/${PHASE}/specs/data-contracts.md"
  REPORT="agent_state/phases/${PHASE}/reports/schema_evolution.md"
  SCHEMA_RC=0
  if [ -f "$CURRENT_CONTRACTS" ]; then
    mkdir -p "$(dirname "$REPORT")"
    echo "# Schema evolution — Phase ${PHASE}" > "$REPORT"
    for PREV_PHASE in $(seq 1 $((PHASE - 1))); do
      PREV_CONTRACTS="docs/design/phases/${PREV_PHASE}/specs/data-contracts.md"
      if [ -f "$PREV_CONTRACTS" ]; then
        echo "  Comparing Phase ${PHASE} contracts against Phase ${PREV_PHASE}..."
        # Compare interfaces — field removals and type changes are breaking
        python3 -c "
import re, sys

def parse_interfaces(text):
    interfaces = {}
    current = None
    for line in text.split('\n'):
        m = re.match(r'(?:export\s+)?interface\s+(\w+)', line)
        if m:
            current = m.group(1)
            interfaces[current] = {}
            continue
        if current and re.match(r'\s*}', line):
            current = None
            continue
        if current:
            fm = re.match(r'\s+(\w+)\??\s*:\s*(.+);', line)
            if fm:
                interfaces[current][fm.group(1)] = fm.group(2).strip()
    return interfaces

prev = parse_interfaces(open('$PREV_CONTRACTS').read())
curr = parse_interfaces(open('$CURRENT_CONTRACTS').read())
breaking = []

for iface in prev:
    if iface not in curr:
        continue
    for field, ftype in prev[iface].items():
        if field not in curr[iface]:
            breaking.append(f'⛔ BREAKING: {iface}.{field} REMOVED (was {ftype})')
        elif curr[iface][field] != ftype:
            breaking.append(f'⛔ BREAKING: {iface}.{field} TYPE CHANGED: {ftype} → {curr[iface][field]}')

if breaking:
    print('Schema evolution issues found (Phase ${PREV_PHASE} → Phase ${PHASE}):')
    for b in breaking: print(f'  {b}')
    sys.exit(1)
else:
    print('✅ Schema evolution clean: Phase ${PREV_PHASE} → Phase ${PHASE}')
" >> "$REPORT" 2>&1 || SCHEMA_RC=1   # a crash (unreadable contracts) blocks too
      fi
    done
    cat "$REPORT"
  fi
  if [ "$SCHEMA_RC" -ne 0 ]; then
    echo "⛔ BLOCKED: breaking schema change(s) above (or the check could not run) — route each to the user:"
    echo "   restore the field, version the endpoint, or confirm the removal (manifest breaking_changes[])."
    exit 1
  fi
fi
```

### Breaking Change Propagation

When a breaking change is confirmed (not restored):
1. Identify all previous phases that consume the affected endpoint (check their manifests' `artifacts.api_routes`)
2. For each consuming phase:
   a. Check if consuming phase's tests still pass with the new contract
   b. If tests fail → the breaking change MUST be resolved before proceeding:
      - Version the endpoint (original route stays, new route added)
      - OR update consuming phase's code (cross-phase fix)
3. Log propagation results in `schema_evolution.md`

```bash
# Breaking change propagation — check all consuming phases
if [ "${PHASE:?}" -gt 1 ] && [ -f "agent_state/phases/${PHASE}/reports/schema_evolution.md" ]; then
  # grep -c prints 0 AND exits 1 on no match: "|| echo 0" would make the count "0<newline>0"
  BREAKING_COUNT=$(grep -c "⛔ BREAKING" "agent_state/phases/${PHASE}/reports/schema_evolution.md" || true)
  if [ "$BREAKING_COUNT" -gt 0 ]; then
    echo "⚠ ${BREAKING_COUNT} breaking change(s) detected — checking consuming phases..."
    for PREV_PHASE in $(seq 1 $((PHASE - 1))); do
      PREV_MANIFEST="agent_state/phases/${PREV_PHASE}/manifest.json"
      if [ -f "$PREV_MANIFEST" ]; then
        python3 -c "
import json
manifest = json.load(open('$PREV_MANIFEST'))
routes = manifest.get('artifacts', {}).get('api_routes', [])
if routes:
    print(f'  Phase ${PREV_PHASE} consumes {len(routes)} API routes — verify compatibility')
    for r in routes:
        print(f'    - {r}')
"
      fi
    done
    echo "  → Breaking changes MUST be resolved (version endpoint or update consumers) before proceeding."
    echo "  → Results logged to agent_state/phases/${PHASE}/reports/schema_evolution.md"
  fi
fi
```

### Phase Context Staleness Detection

Before loading `phase_context.md`, verify it's not stale relative to the BRD:

```bash
CONTEXT_FILE="docs/design/phases/${PHASE}/phase_context.md"
BRD_FILE="docs/BRD.md"
# GNU stat first: GNU `stat -f %m` succeeds with file-system info on stdout, which poisoned the
# BSD-first form on Linux; BSD stat rejects -c and prints nothing to stdout
mtime() { stat -c %Y "${1}" 2>/dev/null || stat -f %m "${1}"; }
if [ -f "$CONTEXT_FILE" ] && [ -f "$BRD_FILE" ]; then
  CONTEXT_MTIME=$(mtime "$CONTEXT_FILE")
  BRD_MTIME=$(mtime "$BRD_FILE")
  if [ "$BRD_MTIME" -gt "$CONTEXT_MTIME" ]; then
    echo "⚠ WARNING: BRD was modified AFTER phase_context.md was generated."
    echo "  BRD modified:     $(date -r "$BRD_MTIME" 2>/dev/null || date -d "@$BRD_MTIME")"
    echo "  Context generated: $(date -r "$CONTEXT_MTIME" 2>/dev/null || date -d "@$CONTEXT_MTIME")"
    echo "  Consider re-running /plan --phase=${PHASE} to refresh phase_context.md"
    echo "  Or proceed with caution — new BRD requirements may be missing from this phase."
  fi
fi
```

If staleness detected and the BRD diff includes new FR-* IDs not in `phase_context.md`: **BLOCKING** — re-run `/plan --phase=${PHASE}`.
If staleness detected but BRD changes are editorial (no new FR-*): **WARNING** — proceed with caution.

### Spec Staleness Warning

Before starting implementation, check if phase specs are older than 30 days:

```bash
SPEC_DIR="docs/design/phases/${PHASE}/specs"
mtime() { stat -c %Y "${1}" 2>/dev/null || stat -f %m "${1}"; }   # GNU first (see above)
if [ -d "$SPEC_DIR" ]; then
  NOW=$(date +%s)
  for SPEC in "$SPEC_DIR"/*.md; do
    [ -f "$SPEC" ] || continue
    SPEC_MTIME=$(mtime "$SPEC")
    DAYS_OLD=$(( (NOW - SPEC_MTIME) / 86400 ))
    if [ "$DAYS_OLD" -gt 60 ]; then
      echo "⛔ Phase ${PHASE} spec $(basename "$SPEC") is ${DAYS_OLD} days old — strongly recommend /plan --refresh before /develop"
    elif [ "$DAYS_OLD" -gt 30 ]; then
      echo "⚠ Phase ${PHASE} spec $(basename "$SPEC") is ${DAYS_OLD} days old — consider re-running /plan to refresh"
    fi
  done
fi
```

Neither warning is BLOCKING — user decides whether to proceed. Surface all stale specs together, then continue.

### Start infrastructure
```bash
# Bring up local dev stack from IMPLEMENTATION_GUIDELINES Section 5
# Commands vary per project — read docs/IMPLEMENTATION_GUIDELINES.md for exact commands
docker compose up -d  # (or equivalent from project setup)

# Wait for DB readiness (up to 60s)
# Health check command from IMPLEMENTATION_GUIDELINES
```

### Token/Cost Estimation

Before starting the pipeline, estimate total token usage for this phase. These estimates are **rough order-of-magnitude** — they exist for budgeting and expectation-setting, not precision. Actual usage varies with codebase size, spec complexity, and retry cycles.

**Estimation algorithm:**
1. Count components in phase specs: `NUM_COMPONENTS = count of spec files in docs/design/phases/${PHASE}/specs/` (exclude `data-contracts.md`, `phase_context.md`, and `INDEX.md` from count)
2. Determine if UI phase: `HAS_UI = true if wireframe specs exist`
3. Count previous phases for regression: `PREV_PHASES = PHASE - 1`
4. Base estimates per agent (input + output tokens):

| Agent | Effort (all Opus 5.5) | Estimated Tokens | When |
|-------|-------|-----------------|------|
| backend_audit_agent | medium | ~15K | Always |
| ui_audit_agent | medium | ~15K | If HAS_UI |
| database_agent | high | ~25K x NUM_DB_TABLES | Always |
| migration_agent | high | ~20K | Always |
| backend_developer | high | ~40K x NUM_COMPONENTS | Always |
| api_developer | high | ~35K x NUM_COMPONENTS | Always |
| ui_developer | high | ~45K x NUM_COMPONENTS | If HAS_UI |
| unit_test_agent | medium | ~30K x NUM_COMPONENTS | Always |
| integration_test_agent | medium | ~25K x NUM_COMPONENTS | Always |
| e2e_orchestrator | medium | ~20K | If e2e unlocked |
| acceptance_test_agent | high | ~30K | Always |
| code_reviewer_I | high | ~15K | Always |
| code_reviewer_II | high | ~25K | Always |
| security_reviewer | high | ~30K | Always |
| tenant_isolation_verifier | high | ~20K | Always |
| code_quality_verifier | high | ~10K | Always |
| spec_impl_reconciler | high | ~25K | Always |
| spec_test_reconciler | high | ~15K | Always |
| code_optimizer | medium | ~20K | Always |
| ui_code_optimizer | medium | ~20K | If HAS_UI |
| documentation_agent | medium | ~15K | If docs policy `developer_docs` is on (off in lean) |

5. Calculate total:
   ```text
   TOTAL_TOKENS = sum of all applicable agent estimates

   Example for 3-component backend-only phase:
     Audit: 15K
     DB + Migration: 25K + 20K = 45K
     Implementation: (40K + 35K) x 3 = 225K
     Testing: (30K + 25K) x 3 + 30K = 195K
     Review: 15K + 25K + 30K + 20K + 10K = 100K
     Reconciliation: 25K + 15K = 40K
     Optimization: 20K
     Documentation: 15K
     TOTAL: ~655K tokens

   Example for 5-component full-stack phase:
     All above + UI agents
     TOTAL: ~1.2M tokens
   ```

6. Display estimate:
   ```text
   Phase ${PHASE} Token Estimate
   ──────────────────────────────
   Components: ${NUM_COMPONENTS} (${HAS_UI ? "full-stack" : "backend-only"})
   Agents to run: ${AGENT_COUNT}
   Estimated tokens: ~${TOTAL_TOKENS} (${TOTAL_TOKENS > 1000000 ? "large phase" : "normal"})

   Breakdown:
     Implementation:  ~${IMPL_TOKENS} (${IMPL_PCT}%)
     Testing:         ~${TEST_TOKENS} (${TEST_PCT}%)
     Review:          ~${REVIEW_TOKENS} (${REVIEW_PCT}%)
     Other:           ~${OTHER_TOKENS} (${OTHER_PCT}%)

   Note: These are rough estimates for budgeting. Actual usage depends on
   codebase size, spec complexity, retry cycles, and escalation count.
   ```

7. **Large phase warning:**
   If TOTAL_TOKENS > 1,500,000: surface warning:
   "This phase is estimated at ~${TOTAL_TOKENS} tokens. Consider splitting into smaller phases or running /plan --split to break it down."

8. Add to execution.jsonl:
   ```bash
   echo "{\"ts\":\"$(date -u +%Y-%m-%dT%H:%M:%SZ)\",\"event\":\"estimate\",\"phase\":${PHASE},\"estimated_tokens\":${TOTAL_TOKENS},\"components\":${NUM_COMPONENTS},\"has_ui\":${HAS_UI}}" >> "agent_state/phases/${PHASE}/execution.jsonl"
   ```

---

### Decision Log Protocol

All agents MUST log significant decisions to `agent_state/phases/${PHASE}/decision-log.md` (append-only):

```markdown
## Decision: <short title>
- **Agent:** <agent name>
- **Context:** <what prompted this decision>
- **Options considered:** <what alternatives existed>
- **Decision:** <what was chosen>
- **Rationale:** <why>
- **Impact:** <what this affects downstream>
```

Log when:
- Choosing between alternative implementations
- Deviating from spec (even slightly)
- Making an assumption not in the spec
- Choosing a library, pattern, or approach not prescribed

**Why:** Decisions made by agents in session 3 are invisible in session 7. The decision log creates persistent memory with accountability.

### Spec Amendment Protocol (Intentional Deviations)

When an implementation agent intentionally deviates from a spec:

1. **Log the deviation** in decision-log.md:
   ```text
   ## Spec Deviation: <component> — <what changed>
   - **Spec says:** <original spec behavior>
   - **Implementation does:** <actual behavior>
   - **Rationale:** <why the deviation was necessary>
   - **Impact:** <what downstream artifacts need updating>
   ```

2. **Auto-update the spec** (append, don't overwrite):
   ```markdown
   ## Implementation Notes (auto-generated)
   > ⚠ Deviation from original spec — see decision-log.md
   > - <what changed and why>
   > - Original behavior preserved in section above
   ```

3. **Flag for reconciliation:** spec_impl_reconciler treats documented deviations as ACKNOWLEDGED (not MISSING).

This prevents specs from going stale after implementation while preserving the original design intent.

### Mid-Execution Escalation Protocol

When an agent encounters uncertainty, conflicting options, or missing data:

**LOW impact** (reversible, single-option): continue with `continueWithDefault: true`
```json
{ "type": "escalation", "impact": "LOW", "recommendation": "A", "continueWithDefault": true }
```

**MEDIUM/HIGH impact** (architecture, security, data model): escalate to Debate Team
```json
{
  "type": "debate_request",
  "from_agent": "<agent name>",
  "from_step": "<pipeline step>",
  "decision": "<what needs deciding>",
  "options": [
    { "id": "A", "label": "...", "initial_reasoning": "..." },
    { "id": "B", "label": "...", "initial_reasoning": "..." }
  ],
  "context": "<BRD refs, constraints, what's known>",
  "impact": "HIGH | MEDIUM",
  "domain": "architecture | security | data_model | feature",
  "blocking": true
}
```

Write to `agent_state/debates/<step>-<topic>.json`.

The `debate_moderator` picks it up and runs:
1. **Researchers** (parallel) — gather evidence for each option
2. **Advocates** (parallel, HIGH only) — argue for each option adversarially
3. **Arbitrator** — evaluates all arguments, produces scored verdict

Verdict written to `agent_state/debates/<topic>-verdict.json`. The requesting agent reads it and continues.

**This replaces guessing with researched, debated, scored decisions.**

### Escalation Circuit Breaker

Prevent runaway escalation loops that consume context and time:

- **Max escalations per step:** 3 — if a single step (e.g., Step 2 Implementation) triggers more than 3 debate requests, STOP escalating. Write remaining decisions to `agent_state/debates/unresolved.json` with recommended defaults.
- **In `--auto` mode:** continue with defaults for all unresolved decisions, but flag ALL as `"⚠ AUTO-RESOLVED — may need review"` in the decision log and manifest `known_issues[]`.
- **Security escalation exception:** Escalations with `"domain": "security"` are NEVER auto-resolved. In `--auto` mode, security decisions MUST use the **hardened default** (the option that is MORE restrictive / MORE secure). Log as `"⚠ SECURITY — hardened default applied, review recommended"`. Security escalations include: auth patterns, token storage, IDOR mitigation, encryption, PII handling, CORS/CSRF config, rate limiting. If no clearly hardened default exists → EXIT auto mode for this decision and surface to user.
- **Max total escalations per phase:** 10 — if exceeded, EXIT auto mode entirely. Surface all unresolved decisions to the user with: `"⛔ Phase ${PHASE} exceeded escalation limit (10). Review agent_state/debates/unresolved.json before continuing."`
- **Max escalation depth:** 2 — if a debate triggers another debate (e.g., arbitrator can't decide and re-escalates), the second-level debate auto-resolves with the recommended default (except security — always hardened). A third-level escalation is NEVER allowed.

```json
// agent_state/debates/unresolved.json
{
  "phase": N,
  "unresolved_count": 4,
  "decisions": [
    {
      "topic": "cache_strategy",
      "from_agent": "backend_developer",
      "auto_resolved_with": "A",
      "confidence": "LOW",
      "reason": "escalation_limit_exceeded",
      "needs_review": true
    }
  ]
}
```

### Universal Agent Return Protocol

Every agent spawned during this command MUST end by returning this exact format — nothing more — to the parent conversation:

```text
✅ <agent-name> — <status: complete | blocked | partial>
   Wrote: <output file path>
   Done:  <what was implemented in one line>
   Issues: none | <N blocking / N warning>
```

If the agent encountered blockers, append:
```text
   Blocker: <one-line description> → see <file path> for details
```

**The parent reads the output file to get details. It does NOT ask the agent to reproduce or summarize the file contents.**

### Analysis Paralysis Guard (applies to ALL agents spawned by this command)

If an agent makes **5+ consecutive read-only tool calls** (Read, Grep, Glob, Bash with read-only commands) without any write action (Edit, Write, Bash with write commands), the agent MUST:

1. **Stop exploring** — do not make another read call
2. **State the blocker** — write a 1-line summary of what's preventing action:
   - "Blocker: can't find the file X expected by spec Y"
   - "Blocker: interface mismatch between service and handler"
3. **Take action** — either:
   - Write code to resolve the blocker
   - Write the blocker to the output file and return to the parent with `status: blocked`

**Why:** Agents get stuck in read-loops, consuming context tokens without making progress. 5 consecutive reads without a write is a strong signal of analysis paralysis.

**Exception:** `backend_audit_agent` and `ui_audit_agent` are read-only by design — this guard does NOT apply to audit agents.

---

### Placeholder Convention
Throughout all agent files and commands:
- `${PHASE}` — current phase number (bash variable, numeric)
- `$((PHASE-1))` — previous phase number (bash arithmetic)
- `{{PHASE}}` — when used inside agent `.md` files, means "substitute the current phase number here at runtime"
- `{{PHASE-1}}` — when used inside agent `.md` files, means "substitute the previous phase number (current minus 1) here at runtime"

Agents reading `{{PHASE-1}}` in their instructions should resolve this to `PHASE - 1` before looking up any path.

---

### Agent Context Protocol — Minimal, targeted reads

**Primary context — agents load these, nothing more by default:**

| File | Size | Contains |
|------|------|----------|
| `docs/design/phases/${PHASE}/phase_context.md` | ~6-8K | Complete tech stack, all conventions, security NFRs, full acceptance criteria, what already exists, gate checklist |
| `docs/design/phases/${PHASE}/specs/<own-component>.md` | ~5-10K | Interface contracts, data model, edge cases, test requirements for THIS component only |
| `docs/design/phases/${PHASE}/specs/data-contracts.md` | ~3-5K | Typed TypeScript interfaces for ALL API endpoints — ARRAY vs OBJECT explicit. Source of truth for response shapes. |
| `agent_state/phases/$((PHASE-1))/manifest.json` | ~3-5K | Existing routes, schema, services — what NOT to re-implement |
| `agent_state/codebase/<relevant-focus>.md` | ~5-10K | Persistent codebase knowledge (if `/map` was run). Load focus area matching your role: `tech.md` for stack decisions, `architecture.md` for structure, `quality.md` for patterns, `concerns.md` for known issues. |

**Codebase knowledge loading rule:** If `agent_state/codebase/` exists and contains `.last-mapped`, agents MUST load the focus document relevant to their role. `backend_developer` and `api_developer` load `architecture.md`. `code_reviewer_I` and `code_optimizer` load `quality.md`. `security_reviewer` loads `concerns.md`. `project_planner` and `backend_audit_agent` load ALL focus documents. If the directory does not exist, skip — `/map` is optional but its output is mandatory reading when present.

`phase_context.md` is intentionally complete — it contains the full tech stack, all coding conventions, all security requirements, and all acceptance criteria needed for correct implementation. **It is not a 50-line stub — it is a structured 6-8K extract that replaces the need to load the full BRD and IMPLEMENTATION_GUIDELINES.**

**Escalation (only when phase_context.md leaves something unresolved):**
- More detail on a specific requirement → `docs/BRD.md` — read only the specific FR-* row
- Infra setup commands → `docs/IMPLEMENTATION_GUIDELINES.md §Local Development Setup` only
- Adjacent component's interface → `docs/design/phases/${PHASE}/specs/<other-component>.md`

**Never load:**
- The entire `docs/BRD.md` (except: brd_spec_reconciler, requirements_brd_reconciler, acceptance_test_agent)
- The entire `docs/IMPLEMENTATION_GUIDELINES.md` (except: agent_factory, architecture_orchestrator)
- All spec files at once — load your component's spec only

---

> Config blocks checked 2026-09-30 (`bash tests/archetype-compile/config-packs/run.sh --live`): 12 bash blocks: bash -n (macOS bash 3.2.57) + shellcheck 0.11.0; 9 run in fixture scenarios on macOS bash 3.2.57 (5 also on Linux bash 5.2.37 with GNU tools); 3 JSON blocks parsed.
